# 邮件同步性能优化实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 优化邮件同步逻辑，通过批量获取日期头先排序，再只获取需要的邮件完整内容，大幅减少同步时间。

**Architecture:** 在 `EmailSyncService` 类中新增 `_fetch_dates` 方法批量获取日期头，修改 `fetch_emails` 方法按日期排序后遍历，达到 limit 时提前退出。

**Tech Stack:** Python, imaplib, pytest

---

### Task 1: 新增 `_fetch_dates` 方法

**Files:**
- Modify: `backend/app/email_sync.py` (在 `EmailSyncService` 类中)

**Step 1: 在 `_decode_header` 方法后添加 `_fetch_dates` 方法**

```python
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
                            except Exception:
                                pass
                            break
        except Exception as e:
            logger.warning(f"批量获取日期头失败: {str(e)}")
            continue

    return result
```

**Step 2: 运行语法检查**

Run: `cd backend && python -m py_compile app/email_sync.py`
Expected: 无输出（无错误）

**Step 3: Commit**

```bash
git add backend/app/email_sync.py
git commit -m "feat: add _fetch_dates method for batch fetching email dates"
```

---

### Task 2: 修改 `fetch_emails` 方法

**Files:**
- Modify: `backend/app/email_sync.py:55-108`

**Step 1: 替换 `fetch_emails` 方法**

```python
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
```

**Step 2: 运行语法检查**

Run: `cd backend && python -m py_compile app/email_sync.py`
Expected: 无输出（无错误）

**Step 3: Commit**

```bash
git add backend/app/email_sync.py
git commit -m "refactor: optimize fetch_emails with date-based sorting and early exit"
```

---

### Task 3: 添加单元测试

**Files:**
- Create: `backend/tests/test_email_sync.py`

**Step 1: 创建测试文件**

```python
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from app.email_sync import EmailSyncService
from app.database import EmailAccount


class TestFetchDates:
    """测试 _fetch_dates 方法"""

    @pytest.fixture
    def mock_account(self):
        account = MagicMock(spec=EmailAccount)
        account.id = 1
        account.email = "test@example.com"
        account.imap_server = "imap.test.com"
        account.imap_port = 993
        account.auth_code = "encrypted_code"
        return account

    @pytest.fixture
    def mock_imap(self):
        imap = MagicMock()
        return imap

    def test_fetch_dates_empty_list(self, mock_account):
        """测试空邮件列表"""
        with patch.object(EmailSyncService, '__init__', lambda x, y: None):
            service = EmailSyncService(mock_account)
            service.imap = MagicMock()

            result = service._fetch_dates([])
            assert result == {}

    def test_fetch_dates_single_email(self, mock_account):
        """测试单封邮件日期获取"""
        with patch.object(EmailSyncService, '__init__', lambda x, y: None):
            service = EmailSyncService(mock_account)
            service.imap = MagicMock()

            # 模拟 IMAP 返回
            service.imap.fetch.return_value = (
                "OK",
                [
                    (b'1 (BODY[HEADER.FIELDS (DATE)] {30}', b'Date: Mon, 01 Jan 2024 12:00:00 +0800\r\n\r\n')
                ]
            )

            result = service._fetch_dates([b'1'])
            assert b'1' in result
            assert isinstance(result[b'1'], datetime)

    def test_fetch_dates_multiple_emails(self, mock_account):
        """测试多封邮件日期获取"""
        with patch.object(EmailSyncService, '__init__', lambda x, y: None):
            service = EmailSyncService(mock_account)
            service.imap = MagicMock()

            # 模拟 IMAP 返回多封邮件
            service.imap.fetch.return_value = (
                "OK",
                [
                    (b'1 (BODY[HEADER.FIELDS (DATE)] {30}', b'Date: Mon, 01 Jan 2024 12:00:00 +0800\r\n\r\n'),
                    (b'2 (BODY[HEADER.FIELDS (DATE)] {30}', b'Date: Tue, 02 Jan 2024 12:00:00 +0800\r\n\r\n'),
                ]
            )

            result = service._fetch_dates([b'1', b'2'])
            assert len(result) == 2
            assert b'1' in result
            assert b'2' in result

    def test_fetch_dates_invalid_date(self, mock_account):
        """测试无效日期格式"""
        with patch.object(EmailSyncService, '__init__', lambda x, y: None):
            service = EmailSyncService(mock_account)
            service.imap = MagicMock()

            service.imap.fetch.return_value = (
                "OK",
                [
                    (b'1 (BODY[HEADER.FIELDS (DATE)] {20}', b'Date: invalid date\r\n\r\n')
                ]
            )

            result = service._fetch_dates([b'1'])
            # 无效日期应该被跳过
            assert b'1' not in result

    def test_fetch_dates_imap_error(self, mock_account):
        """测试 IMAP 错误"""
        with patch.object(EmailSyncService, '__init__', lambda x, y: None):
            service = EmailSyncService(mock_account)
            service.imap = MagicMock()
            service.imap.fetch.return_value = ("NO", [])

            result = service._fetch_dates([b'1'])
            assert result == {}
```

**Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_email_sync.py -v`
Expected: 测试通过（因为方法已实现）

**Step 3: Commit**

```bash
git add backend/tests/test_email_sync.py
git commit -m "test: add unit tests for _fetch_dates method"
```

---

### Task 4: 集成测试和验证

**Step 1: 运行所有测试**

Run: `cd backend && python -m pytest tests/ -v`
Expected: 所有测试通过

**Step 2: 手动验证（可选）**

在本地开发环境运行后端，手动触发同步，观察日志输出：
- 应看到 "日期头获取完成" 日志
- 应看到 "已达到限制" 日志（如果邮件数超过 limit）

**Step 3: 最终 Commit**

```bash
git add -A
git commit -m "feat: complete email sync performance optimization"
```

---

## 完成标准

1. `_fetch_dates` 方法正确批量获取日期头
2. `fetch_emails` 方法按日期降序遍历，达到 limit 时退出
3. 所有测试通过
4. 代码已提交到 main 分支
