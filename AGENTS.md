# AGENTS.md

Guide for AI coding agents working in this repository.

## Project Overview

飞书邮箱同步助手 - A dual-stack application that syncs email data to Feishu (Lark) Bitable.

```
feishu-mail-sync/
├── backend/      # Python FastAPI backend
│   ├── app/
│   │   ├── main.py          # FastAPI app entry point
│   │   ├── config.py        # Pydantic settings
│   │   ├── database.py      # SQLAlchemy models
│   │   ├── email_sync.py    # Email sync service
│   │   ├── models/schemas.py # Pydantic request/response schemas
│   │   ├── routers/         # API routers
│   │   ├── utils/           # Utilities (crypto)
│   │   └── providers.py     # Email provider configs
│   ├── tests/               # pytest tests
│   ├── requirements.txt
│   └── .env.example
└── frontend/     # React TypeScript frontend
    ├── src/
    │   ├── components/      # React components
    │   ├── hooks/           # Custom hooks
    │   ├── services/api.ts  # API client
    │   └── types/index.ts   # TypeScript interfaces
    ├── package.json
    └── tsconfig.json
```

---

## Build / Lint / Test Commands

### Backend (Python)

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env

# Run development server
python run.py
# OR
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Run all tests
pytest

# Run all tests with verbose
pytest -v

# Run a single test file
pytest tests/test_api.py

# Run a single test function
pytest tests/test_api.py::test_health_check

# Run tests matching a pattern
pytest -k "account"

# Run with coverage (if pytest-cov installed)
pytest --cov=app tests/
```

### Frontend (TypeScript/React)

```bash
cd frontend

# Install dependencies
npm install

# Run development server (port 3000)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Type check (via build)
npx tsc --noEmit
```

---

## Code Style Guidelines

### Backend (Python)

#### Imports
```python
# Order: standard library → third-party → local imports
# Separate groups with blank lines

import imaplib
import email
from datetime import datetime
from typing import List, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db, EmailAccount
from app.models.schemas import AccountCreate
```

#### Naming Conventions
- **Files**: `snake_case.py` (e.g., `email_sync.py`, `schemas.py`)
- **Classes**: `PascalCase` (e.g., `EmailSyncService`, `AccountCreate`)
- **Functions/Methods**: `snake_case` (e.g., `get_accounts`, `fetch_emails`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `FIELD_MAPPING`)
- **Private methods**: Prefix with `_` (e.g., `_parse_email`, `_decode_header`)
- **Pydantic models**: Descriptive names ending with purpose (e.g., `AccountCreate`, `AccountResponse`, `MessageResponse`)

#### Function Definitions
```python
# Use docstrings (Chinese is acceptable)
def fetch_emails(self, days: int = 30, limit: int = None) -> Tuple[List[Dict], str]:
    """获取邮件列表
    
    Args:
        days: 同步天数
        limit: 限制数量
    
    Returns:
        Tuple of (emails list, message string)
    """
```

#### Error Handling
```python
# Use HTTPException for API errors with appropriate status codes
from fastapi import HTTPException

if not account:
    raise HTTPException(status_code=404, detail="账户不存在")

# Use try/except for service-level operations
try:
    result = some_operation()
except Exception as e:
    logger.error(f"操作失败: {str(e)}")
    return {"error": str(e)}
finally:
    cleanup()
```

#### Database Patterns
```python
# Use dependency injection for database sessions
@router.get("", response_model=List[AccountResponse])
async def list_accounts(db: Session = Depends(get_db)):
    accounts = db.query(EmailAccount).all()
    return accounts

# Always close sessions in finally blocks when using SessionLocal directly
db = SessionLocal()
try:
    # operations
    db.commit()
finally:
    db.close()
```

#### Pydantic Schemas
```python
class AccountCreate(BaseModel):
    """创建邮箱账户请求"""
    email: str
    auth_code: str
    provider: str  # Comment for enum-like fields


class AccountResponse(BaseModel):
    """邮箱账户响应"""
    id: int
    email: str
    last_sync_time: Optional[datetime]
    
    class Config:
        from_attributes = True  # Enable ORM mode
```

---

### Frontend (TypeScript/React)

#### Imports
```typescript
// Order: React → Third-party → Local components → Local types/utilities
// Use type imports for types

import { useState, useEffect, useCallback } from 'react'
import { Button, message } from 'antd'
import { SyncOutlined } from '@ant-design/icons'

import { StatusPanel } from './components/StatusPanel'
import * as api from './services/api'
import type { Account, SyncStatus } from './types'
```

#### Naming Conventions
- **Files**: `PascalCase.tsx` for components, `camelCase.ts` for utilities
- **Components**: `PascalCase` (e.g., `StatusPanel`, `AccountList`)
- **Hooks**: `use` prefix (e.g., `useBitable`, `useState`)
- **Interfaces/Types**: `PascalCase` (e.g., `Account`, `SyncStatus`)
- **Constants**: `UPPER_SNAKE_CASE` or `camelCase` for object configs

#### TypeScript Patterns
```typescript
// Use interfaces for data shapes
export interface Account {
  id: number
  email: string
  provider: string
  last_sync_time: string | null
  is_active: boolean
}

// Use type for unions/intersections
export type SyncStatus = 'idle' | 'syncing' | 'completed' | 'failed'

// Prefer type imports
import type { Account } from '../types'

// Use Optional for nullable fields
last_sync_time: string | null
```

#### React Component Pattern
```typescript
interface Props {
  accounts: Account[]
  loading: boolean
  onSync: (id: number) => void
}

function AccountList({ accounts, loading, onSync }: Props) {
  const [selectedId, setSelectedId] = useState<number | null>(null)
  
  const handleSync = useCallback((id: number) => {
    onSync(id)
  }, [onSync])
  
  return (
    // JSX
  )
}

export default AccountList
```

#### API Calls
```typescript
// Use async/await with try/catch
const handleSync = async () => {
  try {
    const res = await api.manualSync(limit)
    message.success(res.data.message)
  } catch (err: any) {
    message.error(err.response?.data?.detail || '同步失败')
  }
}
```

#### State Management
```typescript
// Initialize with proper types
const [accounts, setAccounts] = useState<Account[]>([])
const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null)

// Use useCallback for handlers passed as props
const loadData = useCallback(async () => {
  // ...
}, [dependency])
```

---

## Environment Configuration

### Backend (.env)
```bash
DEBUG=true
DATABASE_URL=sqlite:///./email_sync.db
ENCRYPTION_KEY=your-secret-key-32-bytes-long!!
DEFAULT_SYNC_DAYS=30
MAX_RETRY_COUNT=3
```

### Frontend
- API base URL is relative (`/api`) - expects Nginx proxy in production
- Dev server runs on port 3000 with `X-Frame-Options: ALLOWALL` for iframe embedding

---

## Key Patterns

### API Router Structure
```python
router = APIRouter(prefix="/api/accounts", tags=["账户管理"])

@router.post("", response_model=MessageResponse)
@router.get("", response_model=List[AccountResponse])
@router.delete("/{account_id}", response_model=MessageResponse)
@router.put("/{account_id}", response_model=MessageResponse)
```

### Feishu SDK Integration
- Use `@lark-base-open/js-sdk` for Bitable operations
- Check environment with `bitable.base.getActiveTable()` 
- Mock mode for local development (check iframe context)

### Testing Patterns
```python
# Use TestClient for API tests
from fastapi.testclient import TestClient

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200

# Use fixtures for common setup
@pytest.fixture
def mock_account():
    account = MagicMock(spec=EmailAccount)
    account.email = "test@example.com"
    return account
```

---

## Important Notes

1. **Chinese comments/docstrings are acceptable** - The codebase uses Chinese for domain-specific terminology
2. **No ESLint/Prettier config** - Follow existing code style in each file
3. **Strict TypeScript** - `strict: true`, `noUnusedLocals: true`, `noUnusedParameters: true`
4. **No test command in package.json** - Use `pytest` directly in backend
5. **Auth codes are encrypted** - Always use `encrypt()`/`decrypt()` from `app.utils.crypto`

## 使用语言
- 用中文回答