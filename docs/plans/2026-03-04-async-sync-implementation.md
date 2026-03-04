# 异步同步 + 进度查询 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将同步接口改为异步模式，支持后台执行和进度查询，避免大量邮件同步时超时。

**Architecture:** 使用 Python threading 在后台执行同步任务，前端轮询 `/api/sync/progress` 获取进度。附件处理逻辑保持不变。

**Tech Stack:** Python threading, FastAPI, React

---

### Task 1: 后端 - 更新同步状态数据结构

**Files:**
- Modify: `backend/app/routers/sync.py`

**Step 1: 更新 sync_status 数据结构**

找到 `sync_status` 变量定义，替换为：

```python
# 同步状态（内存中）
sync_status = {
    "is_syncing": False,
    "current_emails": [],
    "progress": {
        "total": 0,
        "current": 0,
        "status": "idle",  # idle/syncing/completed/failed
        "message": "",
        "error": None
    }
}
```

**Step 2: 添加进度更新辅助函数**

在 `sync_status` 定义后添加：

```python
def update_progress(current: int, total: int, message: str = ""):
    """更新同步进度"""
    sync_status["progress"]["current"] = current
    sync_status["progress"]["total"] = total
    sync_status["progress"]["message"] = message


def reset_progress():
    """重置进度状态"""
    sync_status["progress"] = {
        "total": 0,
        "current": 0,
        "status": "idle",
        "message": "",
        "error": None
    }
```

**Step 3: 验证语法**

Run: `cd backend && python -m py_compile app/routers/sync.py`
Expected: 无输出（无错误）

**Step 4: Commit**

```bash
git add backend/app/routers/sync.py
git commit -m "refactor: update sync_status structure for async sync"
```

---

### Task 2: 后端 - 添加后台同步任务函数

**Files:**
- Modify: `backend/app/routers/sync.py`

**Step 1: 添加 threading 导入和后台同步函数**

在文件顶部添加导入：

```python
import threading
```

在 `reset_progress()` 函数后添加后台同步函数：

```python
def _background_sync(account_id: int, limit: int, db_url: str):
    """后台同步任务"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # 创建新的数据库会话（线程安全）
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        sync_status["progress"]["status"] = "syncing"
        sync_status["progress"]["message"] = "正在连接邮箱..."

        # 获取账户
        account = db.query(EmailAccount).filter(EmailAccount.id == account_id).first()
        if not account:
            sync_status["progress"]["status"] = "failed"
            sync_status["progress"]["error"] = "账户不存在"
            return

        if not account.is_active:
            sync_status["progress"]["status"] = "failed"
            sync_status["progress"]["error"] = "账户已禁用"
            return

        # 执行同步（带进度回调）
        result = sync_account_with_progress(
            account.id,
            limit=limit,
            db=db,
            progress_callback=update_progress
        )

        if result["success"]:
            sync_status["current_emails"] = result.get("emails", [])
            sync_status["progress"]["status"] = "completed"
            sync_status["progress"]["message"] = f"同步完成，共 {result['emails_count']} 封邮件"
            log_sync(account_id, result["emails_count"], "success")
        else:
            sync_status["progress"]["status"] = "failed"
            sync_status["progress"]["error"] = result["error"]
            sync_status["progress"]["message"] = f"同步失败: {result['error']}"
            log_sync(account_id, 0, "failed", result["error"])

    except Exception as e:
        sync_status["progress"]["status"] = "failed"
        sync_status["progress"]["error"] = str(e)
        sync_status["progress"]["message"] = f"同步异常: {str(e)}"
    finally:
        sync_status["is_syncing"] = False
        db.close()
```

**Step 2: 验证语法**

Run: `cd backend && python -m py_compile app/routers/sync.py`
Expected: 无输出（无错误）

**Step 3: Commit**

```bash
git add backend/app/routers/sync.py
git commit -m "feat: add background sync task function"
```

---

### Task 3: 后端 - 添加带进度回调的同步函数

**Files:**
- Modify: `backend/app/email_sync.py`

**Step 1: 添加 sync_account_with_progress 函数**

在文件末尾添加：

```python
def sync_account_with_progress(account_id: int, days: int = None, limit: int = None,
                                db=None, progress_callback=None) -> Dict:
    """同步单个邮箱账户（带进度回调）"""
    from app.config import settings

    result = {
        "success": False,
        "emails_count": 0,
        "error": None
    }

    # 如果没有传入 db，创建新的会话
    if db is None:
        db = SessionLocal()
        should_close_db = True
    else:
        should_close_db = False

    sync_service = None

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
        emails, msg = sync_service.fetch_emails(days, limit, progress_callback)
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
        if sync_service:
            sync_service.disconnect()
        if should_close_db:
            db.close()

    return result
```

**Step 2: 验证语法**

Run: `cd backend && python -m py_compile app/email_sync.py`
Expected: 无输出（无错误）

**Step 3: Commit**

```bash
git add backend/app/email_sync.py
git commit -m "feat: add sync_account_with_progress function"
```

---

### Task 4: 后端 - 修改 fetch_emails 支持进度回调

**Files:**
- Modify: `backend/app/email_sync.py`

**Step 1: 修改 fetch_emails 方法签名**

将：

```python
def fetch_emails(self, days: int = 30, limit: int = None) -> Tuple[List[Dict], str]:
```

改为：

```python
def fetch_emails(self, days: int = 30, limit: int = None, progress_callback=None) -> Tuple[List[Dict], str]:
```

**Step 2: 在循环中调用进度回调**

在反向遍历邮件的循环中，添加进度更新。找到：

```python
            # 反向遍历邮件 ID（新邮件 ID 更大，从最大开始遍历）
            # 这样可以快速获取最新邮件，无需获取日期头
            checked_count = 0
            for email_id in reversed(email_ids):
```

在循环开始前添加：

```python
            total_to_check = len(email_ids)
```

在循环内，`checked_count += 1` 后添加：

```python
                    if progress_callback:
                        progress_callback(checked_count, total_to_check, f"正在处理 {checked_count}/{total_to_check}")
```

**Step 3: 验证语法**

Run: `cd backend && python -m py_compile app/email_sync.py`
Expected: 无输出（无错误）

**Step 4: Commit**

```bash
git add backend/app/email_sync.py
git commit -m "feat: add progress callback to fetch_emails"
```

---

### Task 5: 后端 - 修改同步接口为异步模式

**Files:**
- Modify: `backend/app/routers/sync.py`

**Step 1: 修改 manual_sync_account 接口**

将 `manual_sync_account` 函数改为：

```python
@router.post("/manual/{account_id}", response_model=MessageResponse)
async def manual_sync_account(account_id: int, limit: int = None, db: Session = Depends(get_db)):
    """手动同步单个账户（异步）"""
    if sync_status["is_syncing"]:
        raise HTTPException(status_code=400, detail="正在同步中，请稍候")

    account = db.query(EmailAccount).filter(EmailAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    # 重置状态
    sync_status["is_syncing"] = True
    sync_status["current_emails"] = []
    reset_progress()
    clear_attachment_cache()

    # 获取数据库 URL 用于新线程
    from app.config import settings
    db_url = settings.database_url

    # 启动后台线程
    thread = threading.Thread(
        target=_background_sync,
        args=(account_id, limit, db_url),
        daemon=True
    )
    thread.start()

    return MessageResponse(message="同步任务已启动，请轮询 /api/sync/progress 获取进度")
```

**Step 2: 验证语法**

Run: `cd backend && python -m py_compile app/routers/sync.py`
Expected: 无输出（无错误）

**Step 3: Commit**

```bash
git add backend/app/routers/sync.py
git commit -m "feat: make manual_sync_account async with background thread"
```

---

### Task 6: 后端 - 添加进度查询接口

**Files:**
- Modify: `backend/app/routers/sync.py`

**Step 1: 添加进度查询接口**

在 `get_synced_emails` 接口前添加：

```python
@router.get("/progress")
async def get_sync_progress():
    """获取同步进度"""
    return sync_status["progress"]
```

**Step 2: 验证语法**

Run: `cd backend && python -m py_compile app/routers/sync.py`
Expected: 无输出（无错误）

**Step 3: Commit**

```bash
git add backend/app/routers/sync.py
git commit -m "feat: add /api/sync/progress endpoint"
```

---

### Task 7: 后端 - 修复数据库配置

**Files:**
- Modify: `backend/app/config.py`

**Step 1: 确保数据库 URL 可访问**

检查 `Settings` 类是否有 `database_url` 属性，如果没有则添加：

```python
class Settings(BaseSettings):
    # ... 现有配置 ...
    database_url: str = "sqlite:///./email_sync.db"
```

**Step 2: 验证语法**

Run: `cd backend && python -m py_compile app/config.py`
Expected: 无输出（无错误）

**Step 3: Commit**

```bash
git add backend/app/config.py
git commit -m "fix: ensure database_url is accessible in config"
```

---

### Task 8: 前端 - 添加进度轮询逻辑

**Files:**
- Modify: `frontend/src/services/api.ts`

**Step 1: 添加进度查询接口**

在文件末尾添加：

```typescript
export interface SyncProgress {
  total: number
  current: number
  status: 'idle' | 'syncing' | 'completed' | 'failed'
  message: string
  error: string | null
}

export const getSyncProgress = () =>
  api.get<SyncProgress>('/sync/progress')
```

**Step 2: Commit**

```bash
git add frontend/src/services/api.ts
git commit -m "feat: add getSyncProgress API"
```

---

### Task 9: 前端 - 修改同步组件显示进度

**Files:**
- Modify: `frontend/src/components/SyncPanel.tsx`（或相关同步组件）

**Step 1: 添加进度状态和轮询逻辑**

在组件中添加：

```typescript
const [progress, setProgress] = useState<SyncProgress | null>(null)
const [isPolling, setIsPolling] = useState(false)

// 轮询进度
useEffect(() => {
  if (!isPolling) return

  const interval = setInterval(async () => {
    try {
      const response = await getSyncProgress()
      setProgress(response.data)

      if (response.data.status === 'completed' || response.data.status === 'failed') {
        setIsPolling(false)
        if (response.data.status === 'completed') {
          // 获取邮件并写入表格
          const emailsResponse = await getSyncedEmails()
          // ... 写入表格逻辑
        }
      }
    } catch (err) {
      console.error('获取进度失败:', err)
    }
  }, 1000)

  return () => clearInterval(interval)
}, [isPolling])

// 修改同步按钮处理
const handleSync = async () => {
  await manualSyncAccount(accountId, limit)
  setIsPolling(true)
  setProgress({ total: 0, current: 0, status: 'syncing', message: '开始同步...', error: null })
}
```

**Step 2: 添加进度条 UI**

```tsx
{progress && progress.status === 'syncing' && (
  <div className="sync-progress">
    <Progress
      percent={progress.total > 0 ? Math.round((progress.current / progress.total) * 100) : 0}
      status="active"
    />
    <span>{progress.message}</span>
  </div>
)}
```

**Step 3: 构建前端**

Run: `cd frontend && npm run build`
Expected: 构建成功

**Step 4: Commit**

```bash
git add frontend/src/
git commit -m "feat: add sync progress polling and UI"
```

---

### Task 10: 集成测试

**Step 1: 运行后端测试**

Run: `cd backend && python -m pytest tests/ -v`
Expected: 所有测试通过

**Step 2: 手动测试流程**

1. 访问前端页面
2. 点击"同步"按钮
3. 观察进度条更新
4. 同步完成后检查邮件列表

**Step 3: 最终提交**

```bash
git add -A
git commit -m "feat: complete async sync with progress polling"
git push origin main
```

---

## 完成标准

1. `/api/sync/manual/{account_id}` 立即返回，不阻塞
2. `/api/sync/progress` 返回实时进度
3. 前端显示进度条
4. 同步完成后邮件列表可正常获取
5. 附件按需获取功能正常
