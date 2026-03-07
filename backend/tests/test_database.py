# backend/tests/test_database.py
"""测试数据库模型"""
import pytest
from app.database import EmailAccount, SyncLog, EmailCache


def test_email_account_has_user_id():
    """测试 EmailAccount 有 user_id 字段"""
    account = EmailAccount(
        user_id="user-123",
        email="test@example.com",
        provider="qq",
        auth_code="encrypted",
        imap_server="imap.qq.com",
        imap_port=993
    )
    assert hasattr(account, 'user_id')
    assert account.user_id == "user-123"


def test_sync_log_has_user_id():
    """测试 SyncLog 有 user_id 字段"""
    log = SyncLog(
        user_id="user-123",
        account_id=1,
        status="success"
    )
    assert hasattr(log, 'user_id')
    assert log.user_id == "user-123"


def test_email_cache_has_user_id():
    """测试 EmailCache 有 user_id 字段"""
    cache = EmailCache(
        user_id="user-123",
        account_id=1,
        message_id="<test@example.com>"
    )
    assert hasattr(cache, 'user_id')
    assert cache.user_id == "user-123"
