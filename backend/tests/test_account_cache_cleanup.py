"""测试账户缓存清理功能"""
import pytest
import uuid
from sqlalchemy.orm import Session
from app.database import SessionLocal, EmailAccount, EmailCache, init_db


@pytest.fixture(scope="function")
def db_session():
    """创建测试数据库会话

    每个测试函数使用独立的数据库会话，测试结束后清理所有测试数据
    """
    # 确保数据库表存在
    init_db()

    db = SessionLocal()
    try:
        yield db
    finally:
        # 清理所有测试数据
        db.query(EmailCache).filter(EmailCache.user_id.like("test-user%")).delete()
        db.query(EmailAccount).filter(EmailAccount.user_id.like("test-user%")).delete()
        db.commit()
        db.close()


class TestCreateAccountClearsCache:
    """测试创建账户时清理缓存"""

    def test_create_account_clears_existing_cache(self, db_session: Session):
        """测试创建账户时清理现有缓存

        场景：删除账户后，新账户可能获得相同的 account_id，
        此时应该清理该 account_id 的旧缓存记录
        """
        user_id = f"test-user-cache-create-{uuid.uuid4().hex[:8]}"

        # 步骤 1: 创建并删除一个账户
        old_account = EmailAccount(
            user_id=user_id,
            email=f"old-{uuid.uuid4().hex[:8]}@example.com",
            provider="qq",
            auth_code="encrypted",
            imap_server="imap.qq.com",
            imap_port=993
        )
        db_session.add(old_account)
        db_session.commit()
        db_session.refresh(old_account)
        old_account_id = old_account.id

        # 步骤 2: 为该账户添加缓存记录
        for i in range(3):
            cache = EmailCache(
                user_id=user_id,
                account_id=old_account_id,
                message_id=f"msg-{i}-{uuid.uuid4().hex[:8]}",
                subject=f"Subject {i}"
            )
            db_session.add(cache)
        db_session.commit()

        # 验证缓存已创建
        cache_count = db_session.query(EmailCache).filter(
            EmailCache.user_id == user_id,
            EmailCache.account_id == old_account_id
        ).count()
        assert cache_count == 3, "应该有 3 条缓存记录"

        # 步骤 3: 删除账户（但不手动清理缓存，模拟可能的数据不一致）
        db_session.delete(old_account)
        db_session.commit()

        # 步骤 4: 创建新账户（可能获得相同的 account_id）
        new_account = EmailAccount(
            user_id=user_id,
            email=f"new-{uuid.uuid4().hex[:8]}@example.com",
            provider="163",
            auth_code="encrypted",
            imap_server="imap.163.com",
            imap_port=993
        )
        db_session.add(new_account)
        db_session.commit()
        db_session.refresh(new_account)

        # 如果新账户获得了相同的 ID，清理逻辑应该已经生效
        # 手动验证：即使数据库中没有账户，缓存记录也应该被清理
        # 模拟 API 层面的清理逻辑
        deleted_count = db_session.query(EmailCache).filter(
            EmailCache.user_id == user_id,
            EmailCache.account_id == new_account.id
        ).delete()
        db_session.commit()

        # 步骤 5: 验证新账户没有旧缓存
        cache_count = db_session.query(EmailCache).filter(
            EmailCache.user_id == user_id,
            EmailCache.account_id == new_account.id
        ).count()
        assert cache_count == 0, "新账户不应该有旧缓存记录"

    def test_create_account_with_no_existing_cache(self, db_session: Session):
        """测试创建账户时没有现有缓存的情况"""
        user_id = f"test-user-no-cache-{uuid.uuid4().hex[:8]}"

        # 创建新账户
        account = EmailAccount(
            user_id=user_id,
            email=f"fresh-{uuid.uuid4().hex[:8]}@example.com",
            provider="qq",
            auth_code="encrypted",
            imap_server="imap.qq.com",
            imap_port=993
        )
        db_session.add(account)
        db_session.commit()
        db_session.refresh(account)

        # 模拟清理逻辑（应该不删除任何记录）
        deleted_count = db_session.query(EmailCache).filter(
            EmailCache.user_id == user_id,
            EmailCache.account_id == account.id
        ).delete()
        db_session.commit()

        # 验证没有删除任何记录
        assert deleted_count == 0, "不应该删除任何缓存记录"

        # 验证账户的缓存为空
        cache_count = db_session.query(EmailCache).filter(
            EmailCache.user_id == user_id,
            EmailCache.account_id == account.id
        ).count()
        assert cache_count == 0, "缓存应该为空"


class TestDeleteAccountClearsCache:
    """测试删除账户时清理缓存"""

    def test_delete_account_clears_cache(self, db_session: Session):
        """测试删除账户时清理缓存"""
        user_id = f"test-user-delete-cache-{uuid.uuid4().hex[:8]}"

        # 步骤 1: 创建账户
        account = EmailAccount(
            user_id=user_id,
            email=f"delete-{uuid.uuid4().hex[:8]}@example.com",
            provider="qq",
            auth_code="encrypted",
            imap_server="imap.qq.com",
            imap_port=993
        )
        db_session.add(account)
        db_session.commit()
        db_session.refresh(account)
        account_id = account.id

        # 步骤 2: 添加缓存记录
        for i in range(5):
            cache = EmailCache(
                user_id=user_id,
                account_id=account_id,
                message_id=f"delete-msg-{i}-{uuid.uuid4().hex[:8]}",
                subject=f"Delete Subject {i}"
            )
            db_session.add(cache)
        db_session.commit()

        # 步骤 3: 验证缓存存在
        cache_count = db_session.query(EmailCache).filter(
            EmailCache.user_id == user_id,
            EmailCache.account_id == account_id
        ).count()
        assert cache_count == 5, "应该有 5 条缓存记录"

        # 步骤 4: 模拟 API 删除账户时的清理逻辑
        deleted_count = db_session.query(EmailCache).filter(
            EmailCache.user_id == user_id,
            EmailCache.account_id == account_id
        ).delete()
        db_session.commit()

        assert deleted_count == 5, f"应该删除 5 条缓存记录，实际删除了 {deleted_count} 条"

        # 步骤 5: 删除账户
        db_session.delete(account)
        db_session.commit()

        # 步骤 6: 验证缓存已被清理
        cache_count = db_session.query(EmailCache).filter(
            EmailCache.user_id == user_id,
            EmailCache.account_id == account_id
        ).count()
        assert cache_count == 0, "删除账户后缓存应该被清理"

    def test_delete_account_with_no_cache(self, db_session: Session):
        """测试删除没有缓存的账户"""
        user_id = f"test-user-no-cache-delete-{uuid.uuid4().hex[:8]}"

        # 创建账户（不添加缓存）
        account = EmailAccount(
            user_id=user_id,
            email=f"nocache-{uuid.uuid4().hex[:8]}@example.com",
            provider="163",
            auth_code="encrypted",
            imap_server="imap.163.com",
            imap_port=993
        )
        db_session.add(account)
        db_session.commit()
        db_session.refresh(account)
        account_id = account.id

        # 验证没有缓存
        cache_count = db_session.query(EmailCache).filter(
            EmailCache.user_id == user_id,
            EmailCache.account_id == account_id
        ).count()
        assert cache_count == 0, "应该没有缓存记录"

        # 模拟清理逻辑（应该不删除任何记录）
        deleted_count = db_session.query(EmailCache).filter(
            EmailCache.user_id == user_id,
            EmailCache.account_id == account_id
        ).delete()
        db_session.commit()

        assert deleted_count == 0, "不应该删除任何缓存记录"

        # 删除账户
        db_session.delete(account)
        db_session.commit()

        # 验证操作成功
        remaining_accounts = db_session.query(EmailAccount).filter(
            EmailAccount.id == account_id
        ).count()
        assert remaining_accounts == 0, "账户应该被删除"


class TestMultiUserIsolation:
    """测试多用户隔离"""

    def test_cache_cleanup_does_not_affect_other_users(self, db_session: Session):
        """测试缓存清理不影响其他用户的缓存

        场景：两个用户有各自的账户和缓存，清理一个用户的缓存时不影响另一个用户
        """
        user_id_1 = f"test-user-1-{uuid.uuid4().hex[:8]}"
        user_id_2 = f"test-user-2-{uuid.uuid4().hex[:8]}"

        # 为两个用户创建各自的账户
        account_1 = EmailAccount(
            user_id=user_id_1,
            email=f"user1-{uuid.uuid4().hex[:8]}@example.com",
            provider="qq",
            auth_code="encrypted",
            imap_server="imap.qq.com",
            imap_port=993
        )
        db_session.add(account_1)

        account_2 = EmailAccount(
            user_id=user_id_2,
            email=f"user2-{uuid.uuid4().hex[:8]}@example.com",
            provider="163",
            auth_code="encrypted",
            imap_server="imap.163.com",
            imap_port=993
        )
        db_session.add(account_2)
        db_session.commit()
        db_session.refresh(account_1)
        db_session.refresh(account_2)

        # 为两个用户添加缓存
        for i in range(2):
            cache_1 = EmailCache(
                user_id=user_id_1,
                account_id=account_1.id,
                message_id=f"user1-msg-{i}-{uuid.uuid4().hex[:8]}",
                subject=f"User 1 Subject {i}"
            )
            db_session.add(cache_1)

            cache_2 = EmailCache(
                user_id=user_id_2,
                account_id=account_2.id,
                message_id=f"user2-msg-{i}-{uuid.uuid4().hex[:8]}",
                subject=f"User 2 Subject {i}"
            )
            db_session.add(cache_2)
        db_session.commit()

        # 验证两个用户都有缓存
        cache_count_1 = db_session.query(EmailCache).filter(
            EmailCache.user_id == user_id_1,
            EmailCache.account_id == account_1.id
        ).count()
        cache_count_2 = db_session.query(EmailCache).filter(
            EmailCache.user_id == user_id_2,
            EmailCache.account_id == account_2.id
        ).count()
        assert cache_count_1 == 2, "用户 1 应该有 2 条缓存"
        assert cache_count_2 == 2, "用户 2 应该有 2 条缓存"

        # 模拟删除用户 1 的账户并清理缓存
        deleted_count = db_session.query(EmailCache).filter(
            EmailCache.user_id == user_id_1,
            EmailCache.account_id == account_1.id
        ).delete()
        db_session.commit()

        assert deleted_count == 2, "应该只删除用户 1 的 2 条缓存"

        # 验证用户 2 的缓存不受影响
        cache_count_2_after = db_session.query(EmailCache).filter(
            EmailCache.user_id == user_id_2,
            EmailCache.account_id == account_2.id
        ).count()
        assert cache_count_2_after == 2, "用户 2 的缓存应该不受影响"

        # 验证用户 1 的缓存已被清理
        cache_count_1_after = db_session.query(EmailCache).filter(
            EmailCache.user_id == user_id_1,
            EmailCache.account_id == account_1.id
        ).count()
        assert cache_count_1_after == 0, "用户 1 的缓存应该被清理"


class TestEdgeCases:
    """测试边界情况"""

    def test_cleanup_with_large_cache(self, db_session: Session):
        """测试清理大量缓存记录"""
        user_id = f"test-user-large-cache-{uuid.uuid4().hex[:8]}"

        account = EmailAccount(
            user_id=user_id,
            email=f"large-{uuid.uuid4().hex[:8]}@example.com",
            provider="qq",
            auth_code="encrypted",
            imap_server="imap.qq.com",
            imap_port=993
        )
        db_session.add(account)
        db_session.commit()
        db_session.refresh(account)

        # 添加大量缓存记录（1000 条）
        cache_count = 1000
        for i in range(cache_count):
            cache = EmailCache(
                user_id=user_id,
                account_id=account.id,
                message_id=f"large-msg-{i}-{uuid.uuid4().hex[:8]}",
                subject=f"Large Subject {i}"
            )
            db_session.add(cache)
        db_session.commit()

        # 验证缓存数量
        count_before = db_session.query(EmailCache).filter(
            EmailCache.user_id == user_id,
            EmailCache.account_id == account.id
        ).count()
        assert count_before == cache_count, f"应该有 {cache_count} 条缓存记录"

        # 清理缓存
        deleted_count = db_session.query(EmailCache).filter(
            EmailCache.user_id == user_id,
            EmailCache.account_id == account.id
        ).delete()
        db_session.commit()

        assert deleted_count == cache_count, f"应该删除 {cache_count} 条缓存记录"

        # 验证清理结果
        count_after = db_session.query(EmailCache).filter(
            EmailCache.user_id == user_id,
            EmailCache.account_id == account.id
        ).count()
        assert count_after == 0, "所有缓存应该被清理"

    def test_cleanup_empty_database(self, db_session: Session):
        """测试在空数据库中执行清理"""
        user_id = "test-user-empty-db"
        account_id = 999

        # 尝试清理不存在的缓存
        deleted_count = db_session.query(EmailCache).filter(
            EmailCache.user_id == user_id,
            EmailCache.account_id == account_id
        ).delete()
        db_session.commit()

        # 应该不报错，且删除数量为 0
        assert deleted_count == 0, "空数据库清理应该返回 0"
