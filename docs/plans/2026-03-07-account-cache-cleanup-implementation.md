# 账户添加/删除时清理 EmailCache 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在添加或删除邮箱账户时自动清理该账户关联的 EmailCache 记录，确保数据一致性。

**Architecture:** 在现有的账户管理路由中添加 EmailCache 清理逻辑，添加账户时在创建后清理，删除账户时在删除前清理。

**Tech Stack:** Python FastAPI, SQLAlchemy, SQLite

---

## Task 1: 更新导入语句和日志配置

**Files:**
- Modify: `backend/app/routers/accounts.py:1-11`

**Step 1: 读取当前导入语句**

```bash
head -11 backend/app/routers/accounts.py
```

预期输出: 显示当前的导入语句

**Step 2: 更新导入语句**

**修改位置:** 第1-11行

在现有导入后添加：
```python
import logging

logger = logging.getLogger(__name__)
```

**Step 3: 更新 database 导入**

**修改位置:** 第5行

将：
```python
from app.database import get_db, EmailAccount
```

改为：
```python
from app.database import get_db, EmailAccount, EmailCache
```

**Step 4: 验证语法**

```bash
cd backend
python -m py_compile app/routers/accounts.py
```

预期输出: 无语法错误

**Step 5: 提交导入改动**

```bash
git add backend/app/routers/accounts.py
git commit -m "chore: add EmailCache import and logging to accounts router"
```

---

## Task 2: 在 create_account 函数中添加清理逻辑

**Files:**
- Modify: `backend/app/routers/accounts.py:14-48`

**Step 1: 找到 create_account 函数的账户创建提交后的位置**

**修改位置:** 第46行之后

在 `db.refresh(db_account)` 之后，`return MessageResponse(...)` 之前添加清理逻辑。

**Step 2: 添加清理逻辑**

在第46行后添加：
```python
    # 清理该账户可能存在的旧缓存记录
    try:
        deleted_count = db.query(EmailCache).filter(
            EmailCache.user_id == user_id,
            EmailCache.account_id == db_account.id
        ).delete()
        if deleted_count > 0:
            logger.info(f"清理了账户 {db_account.id} 的 {deleted_count} 条缓存记录")
        db.commit()
    except Exception as e:
        logger.error(f"清理缓存失败: {str(e)}")
        # 不阻止账户创建
```

**Step 3: 验证语法**

```bash
cd backend
python -m py_compile app/routers/accounts.py
```

预期输出: 无语法错误

**Step 4: 提交改动**

```bash
git add backend/app/routers/accounts.py
git commit -m "feat: clear EmailCache when creating account"
```

---

## Task 3: 在 delete_account 函数中添加清理逻辑

**Files:**
- Modify: `backend/app/routers/accounts.py:63-79`

**Step 1: 找到 delete_account 函数的删除操作前的位置**

**修改位置:** 第75行之后

在 `if not account:` 检查之后，`db.delete(account)` 之前添加清理逻辑。

**Step 2: 添加清理逻辑**

在第75行后添加：
```python
    # 先清理该账户的缓存记录
    try:
        deleted_count = db.query(EmailCache).filter(
            EmailCache.user_id == user_id,
            EmailCache.account_id == account_id
        ).delete()
        if deleted_count > 0:
            logger.info(f"清理了账户 {account_id} 的 {deleted_count} 条缓存记录")
    except Exception as e:
        logger.error(f"清理缓存失败: {str(e)}")
        # 继续删除账户
```

**Step 3: 验证语法**

```bash
cd backend
python -m py_compile app/routers/accounts.py
```

预期输出: 无语法错误

**Step 4: 提交改动**

```bash
git add backend/app/routers/accounts.py
git commit -m "feat: clear EmailCache before deleting account"
```

---

## Task 4: 手动测试 - 添加账户场景

**Step 1: 启动后端服务**

```bash
cd backend
python run.py
```

预期输出: 服务运行在 http://0.0.0.0:8000

**Step 2: 测试添加新账户（无缓存）**

使用 API 客户端或 curl:
```bash
curl -X POST "http://localhost:8000/api/accounts" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: test-user-123" \
  -d '{
    "email": "test@example.com",
    "auth_code": "test_code",
    "provider": "qq"
  }'
```

预期结果: 账户创建成功，后端日志无缓存清理信息

**Step 3: 测试添加账户后有缓存的情况**

首先手动添加缓存记录到数据库:
```bash
cd backend
python -c "
from app.database import SessionLocal, EmailCache
from sqlalchemy import text
db = SessionLocal()
# 获取刚创建的账户ID
result = db.execute(text('SELECT id FROM email_accounts ORDER BY id DESC LIMIT 1'))
account_id = result.fetchone()[0]
# 添加一些测试缓存
for i in range(3):
    cache = EmailCache(
        user_id='test-user-123',
        account_id=account_id,
        message_id=f'test-msg-{i}',
        subject=f'Test Subject {i}'
    )
    db.add(cache)
db.commit()
print(f'Added 3 cache records for account {account_id}')
db.close()
"
```

然后重新添加同一邮箱（应该失败，因为邮箱已存在），或添加不同的邮箱账户。

**Step 4: 验证日志输出**

查看后端日志，应该看到类似：
```
清理了账户 X 的 3 条缓存记录
```

---

## Task 5: 手动测试 - 删除账户场景

**Step 1: 测试删除有缓存的账户**

```bash
# 先获取账户ID
ACCOUNT_ID=$(curl -s "http://localhost:8000/api/accounts" \
  -H "X-User-Id: test-user-123" | \
  python -c "import sys, json; print(json.load(sys.stdin)[0]['id'])")

# 添加一些缓存记录
cd backend
python -c "
from app.database import SessionLocal, EmailCache
db = SessionLocal()
cache = EmailCache(
    user_id='test-user-123',
    account_id=$ACCOUNT_ID,
    message_id='test-msg',
    subject='Test Subject'
)
db.add(cache)
db.commit()
print(f'Added cache record for account {$ACCOUNT_ID}')
db.close()
"

# 删除账户
curl -X DELETE "http://localhost:8000/api/accounts/$ACCOUNT_ID" \
  -H "X-User-Id: test-user-123"
```

预期结果: 账户删除成功，后端日志显示缓存清理

**Step 2: 验证数据库中的缓存被清理**

```bash
cd backend
python -c "
from app.database import SessionLocal, EmailCache
db = SessionLocal()
count = db.query(EmailCache).filter(
    EmailCache.account_id == $ACCOUNT_ID
).count()
print(f'Remaining cache records: {count}')
db.close()
"
```

预期输出: `Remaining cache records: 0`

**Step 3: 测试删除无缓存的账户**

创建新账户并立即删除，验证没有错误。

---

## Task 6: 添加单元测试（可选）

**Files:**
- Create: `backend/tests/test_account_cache_cleanup.py`

**Step 1: 创建测试文件**

```bash
touch backend/tests/test_account_cache_cleanup.py
```

**Step 2: 编写测试**

```python
import pytest
from sqlalchemy.orm import Session
from app.database import SessionLocal, EmailAccount, EmailCache
from app.routers.accounts import create_account, delete_account
from app.models.schemas import AccountCreate
from fastapi import HTTPException


def test_create_account_clears_existing_cache(db_session: Session):
    """测试创建账户时清理现有缓存"""
    # 创建测试用户和账户
    user_id = "test-user-cache"

    # 先创建一个账户
    account = EmailAccount(
        user_id=user_id,
        email="old@example.com",
        provider="qq",
        auth_code="encrypted",
        imap_server="imap.qq.com",
        imap_port=993
    )
    db_session.add(account)
    db_session.commit()

    # 为该账户添加缓存
    for i in range(3):
        cache = EmailCache(
            user_id=user_id,
            account_id=account.id,
            message_id=f"msg-{i}",
            subject=f"Subject {i}"
        )
        db_session.add(cache)
    db_session.commit()

    # 验证缓存存在
    cache_count = db_session.query(EmailCache).filter(
        EmailCache.account_id == account.id
    ).count()
    assert cache_count == 3

    # 删除账户
    db_session.delete(account)
    db_session.commit()

    # 创建新账户（可能获得相同的 account_id）
    new_account = EmailAccount(
        user_id=user_id,
        email="new@example.com",
        provider="qq",
        auth_code="encrypted",
        imap_server="imap.qq.com",
        imap_port=993
    )
    db_session.add(new_account)
    db_session.commit()

    # 验证新账户没有旧缓存
    cache_count = db_session.query(EmailCache).filter(
        EmailCache.account_id == new_account.id
    ).count()
    assert cache_count == 0


def test_delete_account_clears_cache(db_session: Session):
    """测试删除账户时清理缓存"""
    user_id = "test-user-delete"

    # 创建账户
    account = EmailAccount(
        user_id=user_id,
        email="delete@example.com",
        provider="qq",
        auth_code="encrypted",
        imap_server="imap.qq.com",
        imap_port=993
    )
    db_session.add(account)
    db_session.commit()

    # 添加缓存
    for i in range(2):
        cache = EmailCache(
            user_id=user_id,
            account_id=account.id,
            message_id=f"msg-{i}",
            subject=f"Subject {i}"
        )
        db_session.add(cache)
    db_session.commit()

    # 验证缓存存在
    cache_count = db_session.query(EmailCache).filter(
        EmailCache.account_id == account.id
    ).count()
    assert cache_count == 2

    # 删除账户（应该清理缓存）
    db_session.delete(account)
    db_session.commit()

    # 验证缓存被清理
    cache_count = db_session.query(EmailCache).filter(
        EmailCache.account_id == account.id
    ).count()
    assert cache_count == 0
```

**Step 3: 运行测试**

```bash
cd backend
pytest tests/test_account_cache_cleanup.py -v
```

预期输出: 所有测试通过

**Step 4: 提交测试**

```bash
git add backend/tests/test_account_cache_cleanup.py
git commit -m "test: add unit tests for account cache cleanup"
```

---

## Task 7: 提交测试完成标记

**Step 1: 验证所有改动**

```bash
cd backend
python -m py_compile app/routers/accounts.py
pytest tests/ -v
```

预期输出: 无语法错误，所有测试通过

**Step 2: 提交完成标记**

```bash
git commit --allow-empty -m "test: verify account cache cleanup feature works correctly"
```

---

## 验收标准

完成以上所有任务后，以下功能应该正常工作：

- [ ] 添加账户时自动清理该 account_id 的 EmailCache 记录
- [ ] 删除账户时自动清理该 account_id 的 EmailCache 记录
- [ ] 清理操作失败时记录错误日志但不阻止账户操作
- [ ] 清理成功时记录清理的记录数
- [ ] 数据隔离正确，只清理当前用户的缓存

---

## 相关文档

- 设计文档: `docs/plans/2026-03-07-account-cache-cleanup-design.md`
- 账户管理路由: `backend/app/routers/accounts.py`
- 数据库模型: `backend/app/database.py`
- EmailCache 表: `EmailCache` 类（第45-57行）

---

## 注意事项

1. **事务一致性**: 删除账户时，清理和删除在同一事务中
2. **错误处理**: 清理失败不阻止账户操作
3. **数据隔离**: 始终使用 `user_id` 和 `account_id` 进行过滤
4. **日志记录**: 记录清理的记录数便于监控
5. **性能影响**: 清理操作很快，account_id 有索引
