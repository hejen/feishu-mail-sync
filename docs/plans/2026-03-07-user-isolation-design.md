# 用户隔离功能设计

> 日期: 2026-03-07
> 状态: 已批准
> 作者: Sisyphus (AI Agent)

## 概述

为飞书邮箱同步助手实现用户隔离功能，确保每个用户只能访问和管理自己的邮箱账户、同步日志和邮件缓存数据。

## 背景

当前系统所有功能没有用户隔离处理：
- 所有用户共享同一套邮箱账户配置
- 同步日志和邮件缓存全局可见
- 存在数据泄露风险

## 设计目标

1. **按用户隔离** - 每个用户独立管理自己的邮箱账户
2. **向后兼容** - 不影响现有功能，本地开发模式正常工作
3. **最小改动** - 采用最简单的实现方案

## 技术方案

### 隔离策略

采用 **userId 作为隔离键**：
- 前端通过 `bitable.bridge.getUserId()` 获取用户标识
- 所有 API 请求通过 `X-User-Id` Header 传递
- 后端基于 `user_id` 字段过滤数据

```
Frontend                          Backend
   │                                │
   │  bitable.bridge.getUserId()    │
   │  ─────────────────────────────►│
   │         userId                 │
   │                                │
   │  API Request + X-User-Id       │
   │  ─────────────────────────────►│  WHERE user_id = ?
   │                                │
```

## 详细设计

### 1. 数据模型变更

#### EmailAccount 表

```python
class EmailAccount(Base):
    __tablename__ = "email_accounts"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(64), index=True, nullable=False)  # 新增
    email = Column(String(255), index=True, nullable=False)
    provider = Column(String(50), nullable=False)
    auth_code = Column(Text, nullable=False)
    imap_server = Column(String(255), nullable=False)
    imap_port = Column(Integer, default=993)
    last_sync_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
```

#### SyncLog 表

```python
class SyncLog(Base):
    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(64), index=True, nullable=False)  # 新增
    account_id = Column(Integer, index=True, nullable=False)
    sync_time = Column(DateTime, default=datetime.utcnow)
    emails_count = Column(Integer, default=0)
    status = Column(String(50), nullable=False)
    error_message = Column(Text, nullable=True)
```

#### EmailCache 表

```python
class EmailCache(Base):
    __tablename__ = "email_cache"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(64), index=True, nullable=False)  # 新增
    account_id = Column(Integer, index=True, nullable=False)
    message_id = Column(String(255), index=True, nullable=False)
    subject = Column(Text, nullable=True)
    sync_time = Column(DateTime, default=datetime.utcnow)
```

#### 唯一约束调整

| 表 | 原约束 | 新约束 |
|---|--------|--------|
| EmailAccount | `email` unique | `(user_id, email)` unique |
| EmailCache | `message_id` unique | `(user_id, message_id)` unique |

### 2. 前端变更

#### 新增 useUserId Hook

```typescript
// src/hooks/useUserId.ts
import { useState, useEffect } from 'react'
import { bitable } from '@lark-base-open/js-sdk'

export function useUserId() {
  const [userId, setUserId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchUserId() {
      try {
        // 检测是否在飞书环境
        if (window === window.top) {
          // 本地开发模式，使用模拟 userId
          setUserId('mock-user-001')
          setLoading(false)
          return
        }

        const id = await bitable.bridge.getUserId()
        setUserId(id)
        setLoading(false)
      } catch (err) {
        setError(err instanceof Error ? err.message : '获取用户ID失败')
        setLoading(false)
      }
    }
    fetchUserId()
  }, [])

  return { userId, loading, error }
}
```

#### API 客户端修改

```typescript
// src/services/api.ts
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 添加请求拦截器，自动注入 X-User-Id
export function setApiUserId(userId: string | null) {
  api.defaults.headers.common['X-User-Id'] = userId || ''
}

export default api
```

#### App.tsx 集成

```typescript
// src/App.tsx (关键变更)
import { useUserId } from './hooks/useUserId'
import { setApiUserId } from './services/api'

function App() {
  const { userId, loading: userIdLoading, error: userIdError } = useUserId()
  
  // userId 变化时同步到 API 客户端
  useEffect(() => {
    if (userId) {
      setApiUserId(userId)
    }
  }, [userId])

  // 等待 userId 加载完成
  if (userIdLoading) {
    return <div>正在加载用户信息...</div>
  }

  if (userIdError) {
    return <div>加载失败: {userIdError}</div>
  }

  // 原有渲染逻辑...
}
```

### 3. 后端 API 变更

#### 新增用户认证依赖

```python
# app/dependencies.py (新文件)
from fastapi import Header, HTTPException
from typing import Optional

async def get_current_user(x_user_id: Optional[str] = Header(None)) -> str:
    """从请求头获取当前用户ID"""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="未提供用户身份信息")
    return x_user_id
```

#### 账户管理接口修改

```python
# app/routers/accounts.py
from app.dependencies import get_current_user

@router.post("", response_model=MessageResponse)
async def create_account(
    account: AccountCreate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)  # 新增
):
    # 检查同一用户下邮箱是否已存在
    existing = db.query(EmailAccount).filter(
        EmailAccount.user_id == user_id,
        EmailAccount.email == account.email
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该邮箱账户已存在")

    # 创建账户时绑定 user_id
    db_account = EmailAccount(
        user_id=user_id,  # 新增
        email=account.email,
        # ... 其他字段
    )

@router.get("", response_model=List[AccountResponse])
async def list_accounts(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)  # 新增
):
    # 只返回当前用户的账户
    accounts = db.query(EmailAccount).filter(
        EmailAccount.user_id == user_id
    ).all()
    return accounts

@router.delete("/{account_id}")
async def delete_account(
    account_id: int,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)  # 新增
):
    # 只能删除自己的账户
    account = db.query(EmailAccount).filter(
        EmailAccount.id == account_id,
        EmailAccount.user_id == user_id
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")
```

### 4. 同步状态隔离

```python
# app/routers/sync.py

# 改为字典，按 userId 隔离
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

### 5. 附件缓存隔离

```python
# app/email_sync.py

# 改为嵌套字典：{ user_id: { message_id: [attachments] } }
_attachment_cache_by_user: Dict[str, Dict[str, List[Dict]]] = {}

def get_cached_attachment(user_id: str, message_id: str, index: int) -> Optional[Dict]:
    """从缓存获取单个附件（按用户隔离）"""
    user_cache = _attachment_cache_by_user.get(user_id, {})
    attachments = user_cache.get(message_id)
    if not attachments or index >= len(attachments):
        return None
    return attachments[index]

def clear_attachment_cache(user_id: str = None):
    """清空附件缓存"""
    if user_id:
        _attachment_cache_by_user.pop(user_id, None)
    else:
        _attachment_cache_by_user.clear()
```

### 6. 数据迁移

```python
# app/database.py

def migrate_to_multi_user():
    """迁移现有数据到多用户模式"""
    from sqlalchemy import text
    
    # 检查是否需要迁移
    result = engine.execute(text("PRAGMA table_info(email_accounts)"))
    columns = [row[1] for row in result.fetchall()]
    
    if 'user_id' not in columns:
        # 添加 user_id 列
        engine.execute(text("ALTER TABLE email_accounts ADD COLUMN user_id VARCHAR(64)"))
        engine.execute(text("ALTER TABLE sync_logs ADD COLUMN user_id VARCHAR(64)"))
        engine.execute(text("ALTER TABLE email_cache ADD COLUMN user_id VARCHAR(64)"))
        
        # 将现有数据分配给默认用户
        engine.execute(text("UPDATE email_accounts SET user_id = 'legacy-user-001'"))
        engine.execute(text("UPDATE sync_logs SET user_id = 'legacy-user-001'"))
        engine.execute(text("UPDATE email_cache SET user_id = 'legacy-user-001'"))
        
        print("数据迁移完成")
```

## 变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `backend/app/dependencies.py` | 新增 | 用户认证依赖 |
| `backend/app/database.py` | 修改 | 添加 user_id 字段、迁移逻辑 |
| `backend/app/routers/accounts.py` | 修改 | 所有接口添加用户隔离 |
| `backend/app/routers/sync.py` | 修改 | 同步状态按用户隔离 |
| `backend/app/routers/config.py` | 修改 | 配置接口添加用户隔离 |
| `backend/app/email_sync.py` | 修改 | 附件缓存按用户隔离 |
| `frontend/src/hooks/useUserId.ts` | 新增 | 用户身份 hook |
| `frontend/src/services/api.ts` | 修改 | 添加 userId 注入 |
| `frontend/src/App.tsx` | 修改 | 集成 useUserId |

## 兼容性

- **本地开发模式**：自动使用 `mock-user-001` 作为 userId
- **现有数据**：迁移时分配给 `legacy-user-001`
- **API 兼容**：所有接口签名不变，仅通过 Header 传递 userId

## 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| 客户端可伪造 userId | HTTPS + 飞书 iframe 限制来源 |
| 数据迁移失败 | 迁移前备份，提供回滚脚本 |
| 内存状态增长 | 定期清理不活跃用户的同步状态 |
