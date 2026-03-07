import imaplib
import email
import base64
import mimetypes
from email.header import decode_header
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging
import traceback

from app.config import settings
from app.database import SessionLocal, EmailAccount, EmailCache, SyncLog
from app.utils.crypto import decrypt

logger = logging.getLogger(__name__)

# 附件缓存：{user_id: {message_id: [{filename, size, type, content}, ...]}
# 按用户隔离
_attachment_cache_by_user: Dict[str, Dict[str, List[Dict]]] = {}


def cache_attachment(user_id: str, message_id: str, attachments: List[Dict]):
    """缓存附件（按用户隔离）

    Args:
        user_id: 用户ID
        message_id: 邮件 Message-ID
        attachments: 附件列表
    """
    if user_id not in _attachment_cache_by_user:
        _attachment_cache_by_user[user_id] = {}
    _attachment_cache_by_user[user_id][message_id] = attachments


def clear_attachment_cache(user_id: str = None):
    """清空附件缓存（按用户隔离）

    Args:
        user_id: 指定用户ID则只清空该用户的缓存
否则清空全部
    """
    global _attachment_cache_by_user
    if user_id:
        _attachment_cache_by_user.pop(user_id, None)
    else:
        _attachment_cache_by_user = {}


def get_cached_attachment(user_id: str, message_id: str, index: int) -> Optional[Dict]:
    """从缓存获取单个附件（按用户隔离）

    Args:
        user_id: 用户ID
        message_id: 邮件 Message-ID
        index: 附件索引（从 0 开始）

    Returns:
        附件信息（包含 content），如果不存在返回 None
    """
    user_cache = _attachment_cache_by_user.get(user_id, {})
    attachments = user_cache.get(message_id)
    if not attachments:
        return None
    if index < 0 or index >= len(attachments):
        return None
    return attachments[index]


class EmailSyncService:
    """邮件同步服务"""

    def __init__(self, account: EmailAccount, user_id: str = None):
        self.account = account
        self.user_id = user_id
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

    def fetch_emails(self, days: int = 30, limit: int = None, progress_callback=None) -> Tuple[List[Dict], str]:
        """获取邮件列表

        优化策略：IMAP 邮件 ID 通常是递增的，新邮件 ID 更大。
        因此反向遍历（从最大 ID 开始）可以快速获取最新邮件，无需获取日期头。
        """
        emails = []
        try:
            # 选择收件箱
            status, _ = self.imap.select("INBOX")
            if status != "OK":
                return [], "无法选择收件箱"

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

            # 获取已同步的邮件 ID（按用户隔离)
            db = SessionLocal()
            try:
                synced_ids = set(
                    row[0] for row in db.query(EmailCache.message_id).filter(
                        EmailCache.account_id == self.account.id,
                        EmailCache.user_id == self.user_id
                    ).all()
                )
            finally:
                db.close()

            # 反向遍历邮件 ID（新邮件 ID 更大，从最大开始遍历）
            # 这样可以快速获取最新邮件，无需获取日期头
            checked_count = 0
            for email_id in reversed(email_ids):
                try:
                    email_data = self._parse_email(email_id)
                    checked_count += 1

                    # 更新进度
                    if progress_callback:
                        progress_callback(checked_count, len(email_ids))

                    if email_data and email_data["message_id"] not in synced_ids:
                        emails.append(email_data)
                        # 已达到限制，提前退出
                        if limit and len(emails) >= limit:
                            logger.info(f"已达到限制 {limit}，检查了 {checked_count} 封邮件后停止")
                            break

                except Exception as e:
                    logger.warning(f"解析邮件失败: {str(e)}")
                    continue

            return emails, f"成功获取 {len(emails)} 封新邮件（检查了 {checked_count} 封）"

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
        attachment_meta = []  # 只包含元信息，返回给前端
        attachment_full = []  # 包含完整内容，存入缓存

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                if "attachment" in content_disposition:
                    # 附件 - 读取内容并缓存
                    filename = part.get_filename()
                    if filename:
                        filename = self._decode_header(filename)
                        content = part.get_payload(decode=True)
                        if content is not None:
                            # 获取或猜测 MIME 类型
                            mime_type, _ = mimetypes.guess_type(filename)
                            if not mime_type:
                                mime_type = content_type or "application/octet-stream"

                            # 完整附件数据（存入缓存）
                            attachment_full.append({
                                "filename": filename,
                                "size": len(content),
                                "type": mime_type,
                                "content": base64.b64encode(content).decode('utf-8')
                            })
                            # 元信息（返回给前端）
                            attachment_meta.append({
                                "filename": filename,
                                "size": len(content),
                                "type": mime_type
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

        # 缓存附件内容（按 user_id + message_id）
        if attachment_full:
            cache_attachment(self.user_id, message_id, attachment_full)

        return {
            "message_id": message_id,
            "subject": subject,
            "sender": sender,
            "receiver": receiver,
            "date": date,
            "body": body[:5000],  # 限制正文长度
            "attachments": attachment_meta  # 只返回元信息
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
                        # 验证 item[0] 是否有效
                        parts = item[0].split()
                        if not parts:
                            continue
                        email_id = parts[0]
                        header = item[1].decode("utf-8", errors="ignore")
                        # 提取 Date 行
                        for line in header.split("\r\n"):
                            if line.lower().startswith("date:"):
                                date_str = line[5:].strip()
                                try:
                                    date_tuple = email.utils.parsedate_tz(date_str)
                                    if date_tuple:
                                        # 使用邮件 ID 作为 key
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


def sync_account(user_id: str, account_id: int, days: int = None, limit: int = None) -> Dict:
    """同步单个邮箱账户
    
    Args:
        user_id: 用户ID
        account_id: 账户ID
        days: 同步天数
        limit: 限制数量
    """
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
        sync_service = EmailSyncService(account, user_id)

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


def log_sync(user_id: str, account_id: int, emails_count: int, status: str, error_message: str = None):
    """记录同步日志
    
    Args:
        user_id: 用户ID
        account_id: 账户ID
        emails_count: 邮件数量
        status: 状态
        error_message: 错误信息
    """
    db = SessionLocal()
    try:
        log = SyncLog(
            user_id=user_id,
            account_id=account_id,
            emails_count=emails_count,
            status=status,
            error_message=error_message
        )
        db.add(log)
        db.commit()
    finally:
        db.close()


def get_cached_attachment(user_id: str, message_id: str, index: int) -> Optional[Dict]:
    """从缓存获取单个附件（按用户隔离）

    Args:
        user_id: 用户ID
        message_id: 邮件 Message-ID
        index: 附件索引（从 0 开始）

    Returns:
        附件信息（包含 content），如果不存在返回 None
    """
    user_cache = _attachment_cache_by_user.get(user_id, {})
    attachments = user_cache.get(message_id)
    if not attachments:
        return None
    if index < 0 or index >= len(attachments):
        return None
    return attachments[index]


def clear_attachment_cache(user_id: str = None):
    """清空附件缓存

    Args:
        user_id: 指定用户ID则只清空该用户的缓存，否则清空全部
    """
    global _attachment_cache_by_user
    if user_id:
        _attachment_cache_by_user.pop(user_id, None)
    else:
        _attachment_cache_by_user = {}
