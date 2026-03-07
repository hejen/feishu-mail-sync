# 用户隔离功能实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现用户隔离功能，确保每个用户只能访问和管理自己的邮箱账户、同步日志和邮件缓存数据。

**Architecture:** 前端通过 `bitable.bridge.getUserId()` 获取用户标识，所有 API 请求通过 `X-User-Id` Header 传递，后端基于 `user_id` 字段过滤数据。采用 TDD 方式，先写测试再实现。

**Tech Stack:** Python FastAPI, SQLAlchemy, React, TypeScript, @lark-base-open/js-sdk

---

## Phase 1: 后端基础设施

### Task 1: 创建用户认证依赖

**Files:**
- Create: `backend/app/dependencies.py`
- Test: `backend/tests/test_dependencies.py`

**Step 1: 写失败测试**

```python
# backend/tests/test_dependencies.py
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user


def test_get_current_user_with_valid_header():
    """测试有效的 X-User-Id header"""
    app = FastAPI()
    
    @app.get("/test")
    async def test_endpoint(user_id: str = pytest.usefixtures("get_current_user")):
        return {"user_id": user_id}
    
    # 简单测试函数本身
    from unittest.mock import AsyncMock
    
    async def test():
        user_id = await get_current_user(x_user_id="user-123")
        assert user_id == "user-123"
    
    import asyncio
    asyncio.run(test())


def test_get_current_user_missing_header():
    """测试缺少 X-User-Id header 时抛出异常"""
    import asyncio
    from fastapi import HTTPException
    
    async def test():
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(x_user_id=None)
        assert exc_info.value.status_code == 401
    
    asyncio.run(test())
```

**Step 2: 运行测试验证失败**

Run: `cd backend && pytest tests/test_dependencies.py -v`
Expected: FAIL (module not found)

**Step 3: 创建依赖模块**

```python
# backend/app/dependencies.py
"""用户认证依赖"""
from fastapi import Header, HTTPException
from typing import Optional


async def get_current_user(x_user_id: Optional[str] = Header(None)) -> str:
    """从请求头获取当前用户ID
    
    Args:
        x_user_id: X-User-Id 请求头
        
    Returns:
        用户ID字符串
        
    Raises:
        HTTPException: 未提供用户身份信息时返回 401
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="未提供用户身份信息")
    return x_user_id
```

**Step 4: 运行测试验证通过**

Run: `cd backend && pytest tests/test_dependencies.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/dependencies.py backend/tests/test_dependencies.py
git commit -m "feat: add user authentication dependency"
```

---

### Task 2: 数据库模型添加 user_id 字段

**Files:**
- Modify: `backend/app/database.py`
- Test: `backend/tests/test_database.py`

**Step 1: 写失败测试**

```python
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
```

**Step 2: 运行测试验证失败**

Run: `cd backend && pytest tests/test_database.py -v`
Expected: FAIL (user_id field not defined)

**Step 3: 修改数据库模型**

```python
# backend/app/database.py
# 在文件顶部添加 UniqueConstraint 导入
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, UniqueConstraint

# 修改 EmailAccount 类
class EmailAccount(Base):
    """邮箱账户表"""
    __tablename__ = "email_accounts"
    __table_args__ = (
        UniqueConstraint('user_id', 'email', name='uq_user_email'),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String(64), index=True, nullable=False)  # 新增
    email = Column(String(255), index=True, nullable=False)  # 移除 unique=True
    provider = Column(String(50), nullable=False)
    auth_code = Column(Text, nullable=False)  # 加密存储
    imap_server = Column(String(255), nullable=False)
    imap_port = Column(Integer, nullable=False, default=993)
    last_sync_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)


# 修改 SyncLog 类
class SyncLog(Base):
    """同步记录表"""
    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String(64), index=True, nullable=False)  # 新增
    account_id = Column(Integer, index=True, nullable=False)
    sync_time = Column(DateTime, default=datetime.utcnow)
    emails_count = Column(Integer, default=0)
    status = Column(String(50), nullable=False)  # success, failed, partial
    error_message = Column(Text, nullable=True)


# 修改 EmailCache 类
class EmailCache(Base):
    """邮件缓存表 - 避免重复同步"""
    __tablename__ = "email_cache"
    __table_args__ = (
        UniqueConstraint('user_id', 'message_id', name='uq_user_message'),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String(64), index=True, nullable=False)  # 新增
    account_id = Column(Integer, index=True, nullable=False)
    message_id = Column(String(255), index=True, nullable=False)  # 移除 unique=True
    subject = Column(Text, nullable=True)
    sync_time = Column(DateTime, default=datetime.utcnow)
```

**Step 4: 运行测试验证通过**

Run: `cd backend && pytest tests/test_database.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/database.py backend/tests/test_database.py
git commit -m "feat: add user_id field to database models"
```

---

### Task 3: 添加数据迁移逻辑

**Files:**
- Modify: `backend/app/database.py`

**Step 1: 添加迁移函数**

在 `database.py` 文件末尾添加：

```python
# backend/app/database.py (在文件末尾添加)

def migrate_to_multi_user():
    """迁移现有数据到多用户模式
    
    为现有数据库添加 user_id 字段，并将现有数据分配给默认用户。
    仅在检测到缺少 user_id 字段时执行迁移。
    """
    from sqlalchemy import text, inspect
    
    inspector = inspect(engine)
    
    # 检查表是否存在
    if 'email_accounts' not in inspector.get_table_names():
        print("数据库表不存在，跳过迁移")
        return
    
    # 检查是否已有 user_id 列
    columns = [col['name'] for col in inspector.get_columns('email_accounts')]
    
    if 'user_id' in columns:
        print("user_id 字段已存在，跳过迁移")
        return
    
    print("开始迁移数据到多用户模式...")
    
    with engine.connect() as conn:
        # 添加 user_id 列
        conn.execute(text("ALTER TABLE email_accounts ADD COLUMN user_id VARCHAR(64)"))
        conn.execute(text("ALTER TABLE sync_logs ADD COLUMN user_id VARCHAR(64)"))
        conn.execute(text("ALTER TABLE email_cache ADD COLUMN user_id VARCHAR(64)"))
        conn.commit()
        
        # 将现有数据分配给默认用户
        conn.execute(text("UPDATE email_accounts SET user_id = 'legacy-user-001'"))
        conn.execute(text("UPDATE sync_logs SET user_id = 'legacy-user-001'"))
        conn.execute(text("UPDATE email_cache SET user_id = 'legacy-user-001'"))
        conn.commit()
    
    print("数据迁移完成")
```

**Step 2: 修改 init_db 函数调用迁移**

```python
# backend/app/database.py (修改 init_db 函数)

def init_db():
    """初始化数据库"""
    # 先尝试迁移现有数据
    migrate_to_multi_user()
    # 创建新表（如果不存在）
    Base.metadata.create_all(bind=engine)
```

**Step 3: Commit**

```bash
git add backend/app/database.py
git commit -m "feat: add database migration for user_id field"
```

---

## Phase 2: 后端 API 改造

### Task 4: 修改账户管理接口 - 创建账户

**Files:**
- Modify: `backend/app/routers/accounts.py`
- Test: `backend/tests/test_api.py`

**Step 1: 写失败测试**

```python
# backend/tests/test_api.py (添加到现有文件末尾)

def test_create_account_requires_user_id():
    """测试创建账户需要 X-User-Id header"""
    response = client.post("/api/accounts", json={
        "email": "test@example.com",
        "auth_code": "test123",
        "provider": "qq"
    })
    # 应该返回 401 未授权
    assert response.status_code == 401


def test_create_account_with_user_id():
    """测试带用户ID创建账户"""
    response = client.post("/api/accounts", 
        json={
            "email": "test2@example.com",
            "auth_code": "test123",
            "provider": "qq"
        },
        headers={"X-User-Id": "test-user-001"}
    )
    assert response.status_code == 200
    assert "成功" in response.json()["message"]


def test_create_duplicate_account_same_user():
    """测试同一用户不能创建重复邮箱"""
    # 先创建一个
    client.post("/api/accounts", 
        json={
            "email": "dup@example.com",
            "auth_code": "test123",
            "provider": "qq"
        },
        headers={"X-User-Id": "user-001"}
    )
    # 再创建相同的
    response = client.post("/api/accounts", 
        json={
            "email": "dup@example.com",
            "auth_code": "test123",
            "provider": "qq"
        },
        headers={"X-User-Id": "user-001"}
    )
    assert response.status_code == 400


def test_create_same_email_different_users():
    """测试不同用户可以创建相同邮箱"""
    # 用户1创建
    response1 = client.post("/api/accounts", 
        json={
            "email": "shared@example.com",
            "auth_code": "test123",
            "provider": "qq"
        },
        headers={"X-User-Id": "user-001"}
    )
    assert response1.status_code == 200
    
    # 用户2创建相同邮箱
    response2 = client.post("/api/accounts", 
        json={
            "email": "shared@example.com",
            "auth_code": "test456",
            "provider": "qq"
        },
        headers={"X-User-Id": "user-002"}
    )
    assert response2.status_code == 200
```

**Step 2: 运行测试验证失败**

Run: `cd backend && pytest tests/test_api.py -v -k "account"`
Expected: FAIL (401 expected but got 200)

**Step 3: 修改 accounts.py - 导入依赖**

```python
# backend/app/routers/accounts.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db, EmailAccount
from app.models.schemas import AccountCreate, AccountResponse, AccountUpdate, MessageResponse
from app.providers import get_provider_config
from app.utils.crypto import encrypt
from app.dependencies import get_current_user  # 新增
```

**Step 4: 修改 create_account 接口**

```python
# backend/app/routers/accounts.py (修改 create_account 函数)

@router.post("", response_model=MessageResponse)
async def create_account(
    account: AccountCreate, 
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)  # 新增
):
    """添加邮箱账户"""
    # 检查同一用户下邮箱是否已存在
    existing = db.query(EmailAccount).filter(
        EmailAccount.user_id == user_id,
        EmailAccount.email == account.email
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该邮箱账户已存在")

    # 获取提供商配置
    try:
        provider_config = get_provider_config(account.provider)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 创建账户
    db_account = EmailAccount(
        user_id=user_id,  # 新增
        email=account.email,
        provider=account.provider,
        auth_code=encrypt(account.auth_code),
        imap_server=provider_config.imap_server,
        imap_port=provider_config.imap_port
    )
    db.add(db_account)
    db.commit()
    db.refresh(db_account)

    return MessageResponse(message="邮箱账户添加成功")
```

**Step 5: 运行测试验证通过**

Run: `cd backend && pytest tests/test_api.py -v -k "account"`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/routers/accounts.py backend/tests/test_api.py
git commit -m "feat: add user isolation to create account API"
```

---

### Task 5: 修改账户管理接口 - 查询和删除

**Files:**
- Modify: `backend/app/routers/accounts.py`
- Test: `backend/tests/test_api.py`

**Step 1: 写失败测试**

```python
# backend/tests/test_api.py (添加到文件末尾)

def test_list_accounts_isolated_by_user():
    """测试账户列表按用户隔离"""
    # 用户1创建账户
    client.post("/api/accounts", 
        json={"email": "user1@example.com", "auth_code": "test123", "provider": "qq"},
        headers={"X-User-Id": "user-001"}
    )
    # 用户2创建账户
    client.post("/api/accounts", 
        json={"email": "user2@example.com", "auth_code": "test123", "provider": "qq"},
        headers={"X-User-Id": "user-002"}
    )
    
    # 用户1查询，只能看到自己的
    response1 = client.get("/api/accounts", headers={"X-User-Id": "user-001"})
    assert response1.status_code == 200
    emails1 = [acc["email"] for acc in response1.json()]
    assert "user1@example.com" in emails1
    assert "user2@example.com" not in emails1
    
    # 用户2查询，只能看到自己的
    response2 = client.get("/api/accounts", headers={"X-User-Id": "user-002"})
    assert response2.status_code == 200
    emails2 = [acc["email"] for acc in response2.json()]
    assert "user2@example.com" in emails2
    assert "user1@example.com" not in emails2


def test_delete_account_requires_ownership():
    """测试只能删除自己的账户"""
    # 用户1创建账户
    create_resp = client.post("/api/accounts", 
        json={"email": "owner@example.com", "auth_code": "test123", "provider": "qq"},
        headers={"X-User-Id": "owner-user"}
    )
    
    # 获取账户ID
    list_resp = client.get("/api/accounts", headers={"X-User-Id": "owner-user"})
    account_id = list_resp.json()[0]["id"]
    
    # 用户2尝试删除用户1的账户
    delete_resp = client.delete(f"/api/accounts/{account_id}", headers={"X-User-Id": "other-user"})
    assert delete_resp.status_code == 404  # 对于其他用户，账户"不存在"
    
    # 用户1可以删除自己的账户
    delete_resp2 = client.delete(f"/api/accounts/{account_id}", headers={"X-User-Id": "owner-user"})
    assert delete_resp2.status_code == 200
```

**Step 2: 运行测试验证失败**

Run: `cd backend && pytest tests/test_api.py -v -k "list_accounts or delete_account"`
Expected: FAIL

**Step 3: 修改 list_accounts 和 delete_account**

```python
# backend/app/routers/accounts.py (修改两个函数)

@router.get("", response_model=List[AccountResponse])
async def list_accounts(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)  # 新增
):
    """获取所有邮箱账户"""
    accounts = db.query(EmailAccount).filter(
        EmailAccount.user_id == user_id
    ).all()
    return accounts


@router.delete("/{account_id}", response_model=MessageResponse)
async def delete_account(
    account_id: int, 
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)  # 新增
):
    """删除邮箱账户"""
    account = db.query(EmailAccount).filter(
        EmailAccount.id == account_id,
        EmailAccount.user_id == user_id
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    db.delete(account)
    db.commit()
    return MessageResponse(message="邮箱账户删除成功")
```

**Step 4: 修改 update_account**

```python
# backend/app/routers/accounts.py (修改 update_account 函数)

@router.put("/{account_id}", response_model=MessageResponse)
async def update_account(
    account_id: int,
    account_update: AccountUpdate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)  # 新增
):
    """更新邮箱账户"""
    account = db.query(EmailAccount).filter(
        EmailAccount.id == account_id,
        EmailAccount.user_id == user_id
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    if account_update.auth_code is not None:
        account.auth_code = encrypt(account_update.auth_code)
    if account_update.is_active is not None:
        account.is_active = account_update.is_active

    db.commit()
    return MessageResponse(message="邮箱账户更新成功")
```

**Step 5: 运行测试验证通过**

Run: `cd backend && pytest tests/test_api.py -v -k "list_accounts or delete_account"`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/routers/accounts.py backend/tests/test_api.py
git commit -m "feat: add user isolation to list/delete/update account APIs"
```

---

### Task 6: 修改同步接口

**Files:**
- Modify: `backend/app/routers/sync.py`
- Modify: `backend/app/email_sync.py`
- Test: `backend/tests/test_api.py`

**Step 1: 写失败测试**

```python
# backend/tests/test_api.py (添加到文件末尾)

def test_sync_status_requires_user_id():
    """测试同步状态需要用户ID"""
    response = client.get("/api/sync/status")
    assert response.status_code == 401


def test_sync_status_isolated_by_user():
    """测试同步状态按用户隔离"""
    # 用户1创建账户
    client.post("/api/accounts", 
        json={"email": "sync1@example.com", "auth_code": "test123", "provider": "qq"},
        headers={"X-User-Id": "sync-user-001"}
    )
    # 用户2创建账户
    client.post("/api/accounts", 
        json={"email": "sync2@example.com", "auth_code": "test123", "provider": "qq"},
        headers={"X-User-Id": "sync-user-002"}
    )
    
    # 用户1查询状态
    response1 = client.get("/api/sync/status", headers={"X-User-Id": "sync-user-001"})
    assert response1.status_code == 200
    account_emails1 = [acc["email"] for acc in response1.json()["accounts"]]
    assert "sync1@example.com" in account_emails1
    assert "sync2@example.com" not in account_emails1


def test_sync_logs_isolated_by_user():
    """测试同步日志按用户隔离"""
    response = client.get("/api/sync/logs", headers={"X-User-Id": "log-user-001"})
    assert response.status_code == 200
```

**Step 2: 运行测试验证失败**

Run: `cd backend && pytest tests/test_api.py -v -k "sync_status or sync_logs"`
Expected: FAIL

**Step 3: 修改 sync.py - 添加导入和用户状态管理**

```python
# backend/app/routers/sync.py (修改文件开头)
import threading
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db, EmailAccount, SyncLog
from app.models.schemas import SyncStatus, SyncLogResponse, MessageResponse
from app.email_sync import sync_account, log_sync, get_cached_attachment, clear_attachment_cache
from app.dependencies import get_current_user  # 新增

router = APIRouter(prefix="/api/sync", tags=["同步操作"])

# 同步状态（按用户隔离）
sync_status_by_user: Dict[str, dict] = {}


def get_user_sync_status(user_id: str) -> dict:
    """获取用户的同步状态"""
    if user_id not in sync_status_by_user:
        sync_status_by_user[user_id] = {
            "is_syncing": False,
            "current_emails": [],
            "progress": {
                "total": 0,
                "current": 0,
                "status": "idle",
                "message": "",
                "error": None
            }
        }
    return sync_status_by_user[user_id]
```

**Step 4: 修改 sync.py 所有接口**

```python
# backend/app/routers/sync.py (替换所有接口函数)

def _background_sync(user_id: str, account_id: int, limit: int):
    """后台同步任务（在线程中执行）"""
    from app.email_sync import sync_account
    
    user_status = get_user_sync_status(user_id)

    try:
        user_status["progress"]["status"] = "syncing"
        user_status["progress"]["message"] = "正在连接邮箱..."

        # 执行同步
        result = sync_account(user_id, account_id, limit=limit)

        if result["success"]:
            user_status["current_emails"] = result.get("emails", [])
            user_status["progress"]["status"] = "completed"
            user_status["progress"]["message"] = f"同步完成，共 {result['emails_count']} 封邮件"
            log_sync(user_id, account_id, result["emails_count"], "success")
        else:
            user_status["progress"]["status"] = "failed"
            user_status["progress"]["error"] = result["error"]
            user_status["progress"]["message"] = f"同步失败: {result['error']}"
            log_sync(user_id, account_id, 0, "failed", result["error"])

    except Exception as e:
        user_status["progress"]["status"] = "failed"
        user_status["progress"]["error"] = str(e)
        user_status["progress"]["message"] = f"同步异常: {str(e)}"
    finally:
        user_status["is_syncing"] = False


@router.post("/manual", response_model=MessageResponse)
async def manual_sync(
    limit: int = None, 
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    """手动触发同步所有账户"""
    user_status = get_user_sync_status(user_id)
    
    if user_status["is_syncing"]:
        raise HTTPException(status_code=400, detail="正在同步中，请稍候")

    user_status["is_syncing"] = True
    user_status["current_emails"] = []
    clear_attachment_cache(user_id)

    try:
        accounts = db.query(EmailAccount).filter(
            EmailAccount.user_id == user_id,
            EmailAccount.is_active == True
        ).all()

        total_synced = 0
        errors = []

        for account in accounts:
            result = sync_account(user_id, account.id, limit=limit)

            if result["success"]:
                total_synced += result["emails_count"]
                user_status["current_emails"].extend(result.get("emails", []))
                log_sync(user_id, account.id, result["emails_count"], "success")
            else:
                errors.append(f"{account.email}: {result['error']}")
                log_sync(user_id, account.id, 0, "failed", result["error"])

        if errors:
            return MessageResponse(
                message=f"同步完成，{total_synced} 封新邮件。部分失败: {'; '.join(errors)}",
                success=True
            )
        return MessageResponse(message=f"同步完成，{total_synced} 封新邮件")

    finally:
        user_status["is_syncing"] = False


@router.post("/manual/{account_id}", response_model=MessageResponse)
async def manual_sync_account(
    account_id: int, 
    limit: int = None, 
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    """手动同步单个账户（异步模式）"""
    user_status = get_user_sync_status(user_id)
    
    if user_status["is_syncing"]:
        raise HTTPException(status_code=400, detail="正在同步中，请稍候")

    account = db.query(EmailAccount).filter(
        EmailAccount.id == account_id,
        EmailAccount.user_id == user_id
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    # 重置状态
    user_status["is_syncing"] = True
    user_status["current_emails"] = []
    user_status["progress"] = {
        "total": 0,
        "current": 0,
        "status": "idle",
        "message": "",
        "error": None
    }

    # 启动后台线程
    thread = threading.Thread(
        target=_background_sync,
        args=(user_id, account_id, limit),
        daemon=True
    )
    thread.start()

    return MessageResponse(message="同步任务已启动，请轮询 /api/sync/progress 获取进度")


@router.get("/status", response_model=SyncStatus)
async def get_sync_status(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    """获取同步状态"""
    accounts = db.query(EmailAccount).filter(
        EmailAccount.user_id == user_id
    ).all()

    # 获取邮件总数
    from app.database import EmailCache
    total_emails = db.query(EmailCache).filter(
        EmailCache.user_id == user_id
    ).count()

    # 获取最近同步时间
    latest_log = db.query(SyncLog).filter(
        SyncLog.user_id == user_id
    ).order_by(SyncLog.sync_time.desc()).first()
    last_sync_time = latest_log.sync_time if latest_log else None
    
    user_status = get_user_sync_status(user_id)

    return SyncStatus(
        is_syncing=user_status["is_syncing"],
        last_sync_time=last_sync_time,
        total_emails=total_emails,
        accounts=[
            {
                "email": acc.email,
                "status": "active" if acc.is_active else "inactive",
                "last_sync": acc.last_sync_time
            }
            for acc in accounts
        ]
    )


@router.get("/logs", response_model=List[SyncLogResponse])
async def get_sync_logs(
    limit: int = 20, 
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    """获取同步日志"""
    logs = db.query(SyncLog).filter(
        SyncLog.user_id == user_id
    ).order_by(SyncLog.sync_time.desc()).limit(limit).all()
    return logs


@router.get("/progress")
async def get_sync_progress(user_id: str = Depends(get_current_user)):
    """获取同步进度"""
    user_status = get_user_sync_status(user_id)
    return user_status["progress"]


@router.get("/emails")
async def get_synced_emails(user_id: str = Depends(get_current_user)):
    """获取已同步的邮件列表"""
    user_status = get_user_sync_status(user_id)
    return user_status.get("current_emails", [])


@router.get("/attachment/{message_id}/{index}")
async def get_attachment(
    message_id: str, 
    index: int,
    user_id: str = Depends(get_current_user)
):
    """获取单个附件的内容"""
    attachment = get_cached_attachment(user_id, message_id, index)
    if not attachment:
        raise HTTPException(
            status_code=404,
            detail=f"附件不存在或已过期（message_id={message_id}, index={index}）"
        )
    return attachment
```

**Step 5: 运行测试验证通过**

Run: `cd backend && pytest tests/test_api.py -v -k "sync"`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/routers/sync.py backend/tests/test_api.py
git commit -m "feat: add user isolation to sync APIs"
```

---

### Task 7: 修改 email_sync.py 支持用户隔离

**Files:**
- Modify: `backend/app/email_sync.py`

**Step 1: 修改附件缓存为按用户隔离**

```python
# backend/app/email_sync.py (修改文件开头)

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

# 附件缓存：{user_id: {message_id: [{filename, size, type, content}, ...]}}
# 按用户隔离
_attachment_cache_by_user: Dict[str, Dict[str, List[Dict]]] = {}
```

**Step 2: 修改 get_cached_attachment 和 clear_attachment_cache 函数**

```python
# backend/app/email_sync.py (修改文件末尾的函数)

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
```

**Step 3: 修改 EmailSyncService 类的 _parse_email 方法**

在 `_parse_email` 方法中，修改缓存附件的代码：

```python
# backend/app/email_sync.py (在 _parse_email 方法中修改)

# 找到这一行（约第200-202行）：
#         if attachment_full:
#             _attachment_cache[message_id] = attachment_full

# 替换为：
        # 注意：附件缓存现在需要在 fetch_emails 中处理，因为这里没有 user_id
        # 将附件数据存储到返回结果中，由调用方缓存
```

实际上，更好的方式是让 `_parse_email` 返回附件数据，然后在 `fetch_emails` 中缓存。但这需要较大改动。

更简单的方案：给 `EmailSyncService` 添加 `user_id` 属性。

**Step 4: 修改 EmailSyncService 类**

```python
# backend/app/email_sync.py (修改 EmailSyncService 类)

class EmailSyncService:
    """邮件同步服务"""

    def __init__(self, account: EmailAccount, user_id: str = None):
        self.account = account
        self.user_id = user_id or "unknown"
        self.imap = None
        self.decrypted_auth_code = decrypt(account.auth_code)
```

**Step 5: 修改 _parse_email 方法使用 user_id**

```python
# backend/app/email_sync.py (修改 _parse_email 方法末尾)

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
```

**Step 6: 修改 fetch_emails 方法**

```python
# backend/app/email_sync.py (修改 fetch_emails 方法中的查询)

    def fetch_emails(self, days: int = 30, limit: int = None, progress_callback=None) -> Tuple[List[Dict], str]:
        # ... 前面代码不变 ...
        
        # 获取已同步的邮件 ID（按用户隔离）
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
        
        # ... 后面代码不变 ...
```

**Step 7: 修改 sync_account 和 log_sync 函数**

```python
# backend/app/email_sync.py (修改 sync_account 函数签名和实现)

def sync_account(user_id: str, account_id: int, days: int = None, limit: int = None) -> Dict:
    """同步单个邮箱账户

    Args:
        user_id: 用户ID
        account_id: 账户ID
        days: 同步天数
        limit: 限制数量

    Returns:
        同步结果字典
    """
    db = SessionLocal()
    result = {
        "success": False,
        "emails_count": 0,
        "error": None
    }

    try:
        # 获取账户
        account = db.query(EmailAccount).filter(
            EmailAccount.id == account_id,
            EmailAccount.user_id == user_id
        ).first()
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
        if 'sync_service' in locals():
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
```

**Step 8: 运行所有测试验证**

Run: `cd backend && pytest tests/ -v`
Expected: PASS

**Step 9: Commit**

```bash
git add backend/app/email_sync.py
git commit -m "feat: add user isolation to email sync service"
```

---

## Phase 3: 前端改造

### Task 8: 创建 useUserId Hook

**Files:**
- Create: `frontend/src/hooks/useUserId.ts`

**Step 1: 创建 useUserId Hook**

```typescript
// frontend/src/hooks/useUserId.ts
import { useState, useEffect } from 'react'
import { bitable } from '@lark-base-open/js-sdk'

export interface UseUserIdResult {
  userId: string | null
  loading: boolean
  error: string | null
}

/**
 * 获取当前用户ID的 Hook
 * 
 * 在飞书环境中通过 SDK 获取真实用户ID，
 * 本地开发模式下使用模拟用户ID。
 */
export function useUserId(): UseUserIdResult {
  const [userId, setUserId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchUserId() {
      try {
        // 检测是否在飞书环境（iframe 中）
        if (window === window.top) {
          // 本地开发模式，使用模拟 userId
          console.log('[useUserId] 本地开发模式，使用模拟用户ID')
          setUserId('mock-user-001')
          setLoading(false)
          return
        }

        // 尝试从飞书 SDK 获取用户ID
        const id = await bitable.bridge.getUserId()
        console.log('[useUserId] 获取用户ID成功:', id)
        setUserId(id)
        setLoading(false)
      } catch (err) {
        console.error('[useUserId] 获取用户ID失败:', err)
        setError(err instanceof Error ? err.message : '获取用户ID失败')
        setLoading(false)
      }
    }
    
    fetchUserId()
  }, [])

  return { userId, loading, error }
}
```

**Step 2: Commit**

```bash
git add frontend/src/hooks/useUserId.ts
git commit -m "feat: add useUserId hook for user identification"
```

---

### Task 9: 修改 API 客户端添加 userId 注入

**Files:**
- Modify: `frontend/src/services/api.ts`

**Step 1: 添加 setApiUserId 函数**

```typescript
// frontend/src/services/api.ts (修改文件)

import axios from 'axios'
import type { Account, AccountCreate, SyncStatus, SyncLog, Provider, MessageResponse, Email } from '../types'

// 后端 API 地址（使用相对路径，由 Nginx 代理）
const API_BASE = '/api'

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
})

/**
 * 设置 API 请求的用户ID
 * 所有后续请求都会自动携带 X-User-Id header
 * 
 * @param userId - 用户ID，传入 null 则清除
 */
export function setApiUserId(userId: string | null): void {
  if (userId) {
    api.defaults.headers.common['X-User-Id'] = userId
    console.log('[API] 设置用户ID:', userId)
  } else {
    delete api.defaults.headers.common['X-User-Id']
    console.log('[API] 清除用户ID')
  }
}

// ===== 账户管理 =====
export const getAccounts = () =>
  api.get<Account[]>('/accounts')

// ... 其余代码保持不变 ...
```

**Step 2: Commit**

```bash
git add frontend/src/services/api.ts
git commit -m "feat: add setApiUserId function to inject user header"
```

---

### Task 10: 集成 useUserId 到 App.tsx

**Files:**
- Modify: `frontend/src/App.tsx`

**Step 1: 添加导入和 hook 调用**

```typescript
// frontend/src/App.tsx (修改导入部分)
import { useState, useEffect, useCallback, useRef } from 'react'
import { ConfigProvider, Button, message, Space, InputNumber, Progress } from 'antd'
import { PlusOutlined, SyncOutlined } from '@ant-design/icons'
import zhCN from 'antd/locale/zh_CN'

import { StatusPanel } from './components/StatusPanel'
import { AccountList } from './components/AccountList'
import { SyncLogs } from './components/SyncLogs'
import { AddAccountModal } from './components/AddAccountModal'
import { useBitable } from './hooks/useBitable'
import { useUserId } from './hooks/useUserId'  // 新增
import * as api from './services/api'
import { setApiUserId } from './services/api'  // 新增
import type { Account, SyncStatus, SyncLog, Provider } from './types'
import type { SyncProgress } from './services/api'
```

**Step 2: 在 App 组件中添加 useUserId**

```typescript
// frontend/src/App.tsx (在 App 函数开头添加)

function App() {
  // 用户身份
  const { userId, loading: userIdLoading, error: userIdError } = useUserId()
  
  // 同步 userId 到 API 客户端
  useEffect(() => {
    if (userId) {
      setApiUserId(userId)
    }
  }, [userId])

  // 原有状态
  const [accounts, setAccounts] = useState<Account[]>([])
  // ... 其余状态保持不变 ...
```

**Step 3: 添加用户加载状态处理**

```typescript
// frontend/src/App.tsx (在 return 语句之前添加)

  // 等待用户身份加载
  if (userIdLoading) {
    return (
      <ConfigProvider locale={zhCN}>
        <div style={{ padding: 16, maxWidth: 400, margin: '0 auto', textAlign: 'center' }}>
          正在加载用户信息...
        </div>
      </ConfigProvider>
    )
  }

  // 用户身份加载失败
  if (userIdError) {
    return (
      <ConfigProvider locale={zhCN}>
        <div style={{ padding: 16, maxWidth: 400, margin: '0 auto', textAlign: 'center', color: 'red' }}>
          加载失败: {userIdError}
        </div>
      </ConfigProvider>
    )
  }

  // 没有用户ID（不应该发生）
  if (!userId) {
    return (
      <ConfigProvider locale={zhCN}>
        <div style={{ padding: 16, maxWidth: 400, margin: '0 auto', textAlign: 'center', color: 'red' }}>
          无法获取用户身份
        </div>
      </ConfigProvider>
    )
  }
```

**Step 4: 运行前端类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 5: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: integrate useUserId hook into App component"
```

---

## Phase 4: 集成测试

### Task 11: 更新现有测试以支持用户隔离

**Files:**
- Modify: `backend/tests/test_api.py`

**Step 1: 修改现有测试添加 X-User-Id header**

```python
# backend/tests/test_api.py (修改现有测试)

from fastapi.testclient import TestClient
import pytest

from app.main import app

client = TestClient(app)

# 默认测试用户
TEST_USER_ID = "test-user-001"
TEST_HEADERS = {"X-User-Id": TEST_USER_ID}


def test_health_check():
    """测试健康检查接口（无需用户ID）"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_get_providers():
    """测试获取邮箱提供商列表（无需用户ID）"""
    response = client.get("/api/config/providers")
    assert response.status_code == 200
    providers = response.json()
    assert len(providers) == 4
    assert any(p["value"] == "qq" for p in providers)


def test_get_accounts_empty():
    """测试获取空账户列表"""
    response = client.get("/api/accounts", headers=TEST_HEADERS)
    assert response.status_code == 200
    assert response.json() == []


def test_create_account_invalid_provider():
    """测试创建账户 - 无效提供商"""
    response = client.post("/api/accounts", 
        json={
            "email": "test@example.com",
            "auth_code": "test123",
            "provider": "invalid"
        },
        headers=TEST_HEADERS
    )
    assert response.status_code == 400


def test_get_sync_status():
    """测试获取同步状态"""
    response = client.get("/api/sync/status", headers=TEST_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "is_syncing" in data
    assert "total_emails" in data
    assert "accounts" in data


def test_get_sync_logs():
    """测试获取同步日志"""
    response = client.get("/api/sync/logs", headers=TEST_HEADERS)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_api_requires_user_id():
    """测试需要用户ID的接口"""
    # 账户列表
    assert client.get("/api/accounts").status_code == 401
    # 同步状态
    assert client.get("/api/sync/status").status_code == 401
    # 同步日志
    assert client.get("/api/sync/logs").status_code == 401
```

**Step 2: 运行所有测试**

Run: `cd backend && pytest tests/ -v`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/tests/test_api.py
git commit -m "test: update existing tests to support user isolation"
```

---

### Task 12: 运行完整测试套件

**Step 1: 运行后端测试**

Run: `cd backend && pytest tests/ -v --tb=short`
Expected: All tests pass

**Step 2: 运行前端类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 3: 手动测试本地开发模式**

1. 启动后端: `cd backend && python run.py`
2. 启动前端: `cd frontend && npm run dev`
3. 访问 http://localhost:3000
4. 验证显示"正在加载用户信息..."后正常显示界面
5. 验证可以添加、查看、删除账户

**Step 4: Commit 最终状态**

```bash
git add -A
git commit -m "feat: complete user isolation implementation

- Add user_id field to all database models
- Add user authentication dependency
- Modify all API endpoints to filter by user_id
- Modify sync service to support user isolation
- Add useUserId hook for frontend
- Integrate user ID into API client

Closes: User isolation design doc"
```

---

## 变更清单总结

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `backend/app/dependencies.py` | 新增 | 用户认证依赖 |
| `backend/app/database.py` | 修改 | 添加 user_id 字段、迁移逻辑 |
| `backend/app/routers/accounts.py` | 修改 | 所有接口添加用户隔离 |
| `backend/app/routers/sync.py` | 修改 | 同步状态按用户隔离 |
| `backend/app/email_sync.py` | 修改 | 附件缓存按用户隔离 |
| `backend/tests/test_dependencies.py` | 新增 | 依赖测试 |
| `backend/tests/test_database.py` | 新增 | 数据库模型测试 |
| `backend/tests/test_api.py` | 修改 | 更新现有测试 |
| `frontend/src/hooks/useUserId.ts` | 新增 | 用户身份 hook |
| `frontend/src/services/api.ts` | 修改 | 添加 userId 注入 |
| `frontend/src/App.tsx` | 修改 | 集成 useUserId |

---

## 验收标准

- [ ] 所有后端测试通过
- [ ] 前端 TypeScript 编译无错误
- [ ] 本地开发模式正常工作（使用 mock-user-001）
- [ ] 用户只能看到自己的邮箱账户
- [ ] 用户只能操作自己的数据
- [ ] 现有数据迁移到 legacy-user-001
