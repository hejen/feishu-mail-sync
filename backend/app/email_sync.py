import imaplib
import email
import base64
from email.header import decode_header
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging
import traceback

from app.config import settings
from app.database import SessionLocal, EmailAccount, EmailCache, SyncLog
from app.utils.crypto import decrypt

logger = logging.getLogger(__name__)


class EmailSyncService:
    """邮件同步服务"""

    def __init__(self, account: EmailAccount):
        self.account = account
        self.imap = None
        self.decrypted_auth_code = decrypt(account.auth_code)

    def connect(self) -> Tuple[bool, str]:
        """连接 IMAP 服务器"""
        try:
            self.imap = imaplib.IMAP4_SSL(
                self.account.imap_server,
                self.account.imap_port
            )
            return True, "连接成功"
        except Exception as e:
            logger.error(f"连接 IMAP 服务器失败: {str(e)}")
            return False, f"连接失败: {str(e)}"

    def login(self) -> Tuple[bool, str]:
        """登录邮箱"""
        try:
            self.imap.login(self.account.email, self.decrypted_auth_code)
            return True, "登录成功"
        except Exception as e:
            logger.error(f"登录邮箱失败: {str(e)}")
            return False, f"登录失败: 请检查授权码是否正确"

    def disconnect(self):
        """断开连接"""
        if self.imap:
            try:
                self.imap.logout()
            except:
                pass
            self.imap = None

    def fetch_emails(self, days: int = 30, limit: int = None) -> Tuple[List[Dict], str]:
        """获取邮件列表"""
        emails = []
        try:
            # 选择收件箱
            self.imap.select("INBOX")

            # 计算搜索日期
            since_date = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")

            # 搜索邮件
            status, messages = self.imap.search(None, f'(SINCE "{since_date}")')
            if status != "OK":
                return [], "搜索邮件失败"

            email_ids = messages[0].split()
            if not email_ids:
                return [], "没有找到邮件"

            logger.info(f"找到 {len(email_ids)} 封邮件")

            # 批量获取日期头并按日期降序排序
            id_date_map = self._fetch_dates(email_ids)
            sorted_ids = sorted(
                email_ids,
                key=lambda eid: id_date_map.get(eid, datetime.min),
                reverse=True  # 最新的在前
            )
            logger.info(f"日期头获取完成，共 {len(id_date_map)} 封")

            # 获取已同步的邮件 ID
            db = SessionLocal()
            try:
                synced_ids = set(
                    row[0] for row in db.query(EmailCache.message_id).filter(
                        EmailCache.account_id == self.account.id
                    ).all()
                )
            finally:
                db.close()

            # 按日期降序遍历，收集未同步邮件
            for email_id in sorted_ids:
                # 已达到限制，提前退出
                if limit and len(emails) >= limit:
                    logger.info(f"已达到限制 {limit}，停止获取")
                    break

                try:
                    email_data = self._parse_email(email_id)
                    if email_data and email_data["message_id"] not in synced_ids:
                        emails.append(email_data)
                except Exception as e:
                    logger.warning(f"解析邮件失败: {str(e)}")
                    continue

            return emails, f"成功获取 {len(emails)} 封新邮件"

        except Exception as e:
            logger.error(f"获取邮件失败: {str(e)}")
            return [], f"获取邮件失败: {str(e)}"

    def _parse_email(self, email_id: bytes) -> Optional[Dict]:
        """解析单封邮件"""
        status, msg_data = self.imap.fetch(email_id, "(RFC822)")
        if status != "OK":
            return None

        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        # 解析邮件各字段
        subject = self._decode_header(msg.get("Subject", ""))
        sender = self._decode_header(msg.get("From", ""))
        receiver = self._decode_header(msg.get("To", ""))
        date_str = msg.get("Date", "")
        message_id = msg.get("Message-ID", "")

        # 解析日期
        try:
            date_tuple = email.utils.parsedate_tz(date_str)
            if date_tuple:
                date = datetime.fromtimestamp(email.utils.mktime_tz(date_tuple))
            else:
                date = datetime.now()
        except:
            date = datetime.now()

        # 解析正文和附件
        body = ""
        attachments = []
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                if "attachment" in content_disposition:
                    # 附件 - 读取内容并转为 base64
                    filename = part.get_filename()
                    if filename:
                        filename = self._decode_header(filename)
                        content = part.get_payload(decode=True)
                        if content is not None:
                            attachments.append({
                                "filename": filename,
                                "content": base64.b64encode(content).decode('utf-8')
                            })
                        else:
                            logger.warning(f"无法读取附件内容: {filename}")
                elif content_type == "text/plain" and not body:
                    # 纯文本正文
                    try:
                        body = part.get_payload(decode=True).decode(
                            part.get_content_charset() or "utf-8",
                            errors="ignore"
                        )
                    except:
                        body = ""

        return {
            "message_id": message_id,
            "subject": subject,
            "sender": sender,
            "receiver": receiver,
            "date": date,
            "body": body[:5000],  # 限制正文长度
            "attachments": attachments
        }

    def _decode_header(self, header: str) -> str:
        """解码邮件头"""
        if not header:
            return ""
        try:
            decoded_parts = decode_header(header)
            result = []
            for part, charset in decoded_parts:
                if isinstance(part, bytes):
                    result.append(part.decode(charset or "utf-8", errors="ignore"))
                else:
                    result.append(part)
            return "".join(result)
        except:
            return header

    def _fetch_dates(self, email_ids: List[bytes]) -> Dict[bytes, datetime]:
        """批量获取邮件日期头，返回 {email_id: datetime} 映射"""
        if not email_ids:
            return {}

        result = {}

        # 分批处理，避免命令过长（每批 500 个）
        batch_size = 500
        for i in range(0, len(email_ids), batch_size):
            batch = email_ids[i:i + batch_size]
            id_str = b",".join(batch)

            try:
                status, data = self.imap.fetch(id_str, "(BODY.PEEK[HEADER.FIELDS (DATE)])")
                if status != "OK":
                    logger.warning(f"IMAP fetch returned non-OK status for batch {i//batch_size + 1}")
                    continue

                # 解析返回数据
                for item in data:
                    if isinstance(item, tuple):
                        # item 格式: (b'1 (BODY[HEADER.FIELDS (DATE)] {size}', b'Date: ...\r\n\r\n')
                        header = item[1].decode("utf-8", errors="ignore")
                        # 提取 Date 行
                        for line in header.split("\r\n"):
                            if line.lower().startswith("date:"):
                                date_str = line[5:].strip()
                                try:
                                    date_tuple = email.utils.parsedate_tz(date_str)
                                    if date_tuple:
                                        # 使用邮件 ID 作为 key
                                        email_id = item[0].split()[0]
                                        result[email_id] = datetime.fromtimestamp(
                                            email.utils.mktime_tz(date_tuple)
                                        )
                                except Exception as e:
                                    logger.debug(f"解析日期失败: {date_str}, 错误: {str(e)}")
                                break
            except Exception as e:
                logger.warning(f"批量获取日期头失败: {str(e)}")
                continue

        return result


def sync_account(account_id: int, days: int = None, limit: int = None) -> Dict:
    """同步单个邮箱账户"""
    db = SessionLocal()
    result = {
        "success": False,
        "emails_count": 0,
        "error": None
    }

    try:
        # 获取账户
        account = db.query(EmailAccount).filter(EmailAccount.id == account_id).first()
        if not account:
            result["error"] = "账户不存在"
            return result

        if not account.is_active:
            result["error"] = "账户已禁用"
            return result

        # 创建同步服务
        sync_service = EmailSyncService(account)

        # 连接
        success, msg = sync_service.connect()
        if not success:
            result["error"] = msg
            return result

        # 登录
        success, msg = sync_service.login()
        if not success:
            result["error"] = msg
            return result

        # 获取邮件
        days = days or settings.default_sync_days
        emails, msg = sync_service.fetch_emails(days, limit)
        result["emails_count"] = len(emails)

        # 更新同步时间
        account.last_sync_time = datetime.utcnow()
        db.commit()

        result["success"] = True
        result["emails"] = emails

    except Exception as e:
        logger.error(f"同步失败: {str(e)}\n{traceback.format_exc()}")
        result["error"] = str(e)
    finally:
        sync_service.disconnect()
        db.close()

    return result


def log_sync(account_id: int, emails_count: int, status: str, error_message: str = None):
    """记录同步日志"""
    db = SessionLocal()
    try:
        log = SyncLog(
            account_id=account_id,
            emails_count=emails_count,
            status=status,
            error_message=error_message
        )
        db.add(log)
        db.commit()
    finally:
        db.close()
