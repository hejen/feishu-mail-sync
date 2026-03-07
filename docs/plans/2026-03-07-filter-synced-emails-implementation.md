# 过滤已同步邮件功能实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 添加一个配置选项，允许用户选择是否过滤已同步的邮件。默认不勾选，勾选时跳过已同步邮件。

**Architecture:** 前端 localStorage 存储配置，同步时通过 API 参数传递给后端，后端根据参数决定是否查询 EmailCache 进行过滤。

**Tech Stack:** React TypeScript (前端), FastAPI Python (后端), SQLite (数据库), localStorage (配置存储)

---

## Task 1: 后端核心同步逻辑 - 添加 filter_synced 参数支持

**Files:**
- Modify: `backend/app/email_sync.py`
- Test: `backend/tests/test_email_sync.py` (需要创建或更新)

### Step 1: 为 fetch_emails 方法添加 filter_synced 参数

在 `EmailSyncService.fetch_emails` 方法签名中添加 `filter_synced` 参数，并修改查询逻辑。

**修改位置:** `backend/app/email_sync.py` 第 108 行

```python
def fetch_emails(self, days: int = 30, limit: int = None, filter_synced: bool = False, progress_callback=None) -> Tuple[List[Dict], str]:
```

**修改位置:** `backend/app/email_sync.py` 第 135-145 行，将原来的查询逻辑包裹在条件判断中：

```python
# 获取已同步的邮件 ID（按用户隔离)
synced_ids = set()
if filter_synced:  # 只有在勾选时才查询已同步邮件
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
```

### Step 2: 为 sync_account 函数添加 filter_synced 参数

**修改位置:** `backend/app/email_sync.py` 第 329 行

```python
def sync_account(user_id: str, account_id: int, days: int = None, limit: int = None, filter_synced: bool = False) -> Dict:
```

**修改位置:** `backend/app/email_sync.py` 第 373 行，传递参数给 fetch_emails：

```python
emails, msg = sync_service.fetch_emails(days, limit, filter_synced)
```

### Step 3: 运行现有测试确保没有破坏现有功能

```bash
cd backend
pytest tests/ -v
```

预期输出: 所有现有测试通过（如果有测试的话）

### Step 4: 提交后端核心逻辑改动

```bash
git add backend/app/email_sync.py
git commit -m "feat: add filter_synced parameter to email sync logic"
```

---

## Task 2: 后端同步路由 - 传递 filter_synced 参数

**Files:**
- Modify: `backend/app/routers/sync.py`

### Step 1: 为 manual_sync 端点添加 filter_synced 参数

**修改位置:** `backend/app/routers/sync.py` 第 116-120 行

```python
@router.post("/manual", response_model=MessageResponse)
async def manual_sync(
    limit: int = None,
    filter_synced: bool = False,  # 新增参数，默认 False
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
```

**修改位置:** `backend/app/routers/sync.py` 第 151-154 行，传递给后台线程：

```python
thread = threading.Thread(
    target=_background_sync_all,
    args=(user_id, account_ids, limit, filter_synced),
    daemon=True
)
```

### Step 2: 为 manual_sync_account 端点添加 filter_synced 参数

**修改位置:** `backend/app/routers/sync.py` 第 161-165 行

```python
@router.post("/manual/{account_id}", response_model=MessageResponse)
async def manual_sync_account(
    account_id: int,
    limit: int = None,
    filter_synced: bool = False,  # 新增参数
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
```

**修改位置:** `backend/app/routers/sync.py` 第 192-196 行，传递给后台线程：

```python
thread = threading.Thread(
    target=_background_sync,
    args=(user_id, account_id, limit, filter_synced),
    daemon=True
)
```

### Step 3: 更新后台任务函数签名

**修改位置:** `backend/app/routers/sync.py` 第 36 行

```python
def _background_sync(user_id: str, account_id: int, limit: int, filter_synced: bool = False):
```

**修改位置:** `backend/app/routers/sync.py` 第 47 行，传递给 sync_account：

```python
result = sync_account(user_id, account_id, limit=limit, filter_synced=filter_synced)
```

**修改位置:** `backend/app/routers/sync.py` 第 69 行

```python
def _background_sync_all(user_id: str, account_ids: List[int], limit: int, filter_synced: bool = False):
```

**修改位置:** `backend/app/routers/sync.py` 第 87 行，传递给 sync_account：

```python
result = sync_account(user_id, account_id, limit=limit, filter_synced=filter_synced)
```

### Step 4: 测试后端 API

```bash
cd backend
python -c "
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
# 测试不带参数的调用（应使用默认值 False）
response = client.post('/api/sync/manual?limit=10', headers={'X-User-Id': 'test-user'})
print(f'Status: {response.status_code}')
# 测试带 filter_synced=true 的调用
# response = client.post('/api/sync/manual?limit=10&filter_synced=true', headers={'X-User-Id': 'test-user'})
"
```

### Step 5: 提交路由层改动

```bash
git add backend/app/routers/sync.py
git commit -m "feat: add filter_synced parameter to sync endpoints"
```

---

## Task 3: 前端 API 服务 - 添加 filter_synced 参数

**Files:**
- Modify: `frontend/src/services/api.ts`

### Step 1: 读取并理解现有的 API 函数

```bash
cat frontend/src/services/api.ts | grep -A 5 "manualSync"
```

### Step 2: 更新 manualSync 函数签名

**修改位置:** `frontend/src/services/api.ts` 中的 `manualSync` 函数

找到现有的 `manualSync` 函数（可能在第 30-40 行附近），修改为：

```typescript
export async function manualSync(limit: number | null = null, filterSynced: boolean = false) {
  return request.post('/api/sync/manual', null, {
    params: { limit, filter_synced: filterSynced }
  })
}
```

### Step 3: 更新 manualSyncAccount 函数签名

**修改位置:** `frontend/src/services/api.ts` 中的 `manualSyncAccount` 函数

找到现有的 `manualSyncAccount` 函数，修改为：

```typescript
export async function manualSyncAccount(accountId: number, limit: number | null = null, filterSynced: boolean = false) {
  return request.post(`/api/sync/manual/${accountId}`, null, {
    params: { limit, filter_synced: filterSynced }
  })
}
```

### Step 4: 类型检查

```bash
cd frontend
npx tsc --noEmit
```

预期输出: 无类型错误

### Step 5: 提交 API 服务改动

```bash
git add frontend/src/services/api.ts
git commit -m "feat: add filter_synced parameter to sync API calls"
```

---

## Task 4: 前端 UI - 添加 filterSyncedEmails 状态

**Files:**
- Modify: `frontend/src/App.tsx`

### Step 1: 添加 filterSyncedEmails 状态

**修改位置:** `frontend/src/App.tsx` 第 28-41 行（在其他 useState 附近）

```typescript
const [filterSyncedEmails, setFilterSyncedEmails] = useState<boolean>(() => {
  const saved = localStorage.getItem('filterSyncedEmails')
  return saved ? saved === 'true' : false  // 默认 false（不勾选）
})
```

### Step 2: 添加处理函数

**修改位置:** `frontend/src/App.tsx` 在 `handleSyncLimitChange` 函数附近（第 206 行之后）

```typescript
// 处理过滤已同步邮件变更
const handleFilterSyncedChange = (checked: boolean) => {
  setFilterSyncedEmails(checked)
  localStorage.setItem('filterSyncedEmails', String(checked))
}
```

### Step 3: 更新同步调用传递参数

**修改位置:** `frontend/src/App.tsx` 第 153 行

```typescript
await api.manualSync(syncLimit, filterSyncedEmails)
```

**修改位置:** `frontend/src/App.tsx` 第 171 行

```typescript
await api.manualSyncAccount(id, syncLimit, filterSyncedEmails)
```

### Step 4: 类型检查

```bash
cd frontend
npx tsc --noEmit
```

预期输出: 无类型错误

### Step 5: 提交状态管理改动

```bash
git add frontend/src/App.tsx
git commit -m "feat: add filterSyncedEmails state with localStorage persistence"
```

---

## Task 5: 前端 UI - 添加 Checkbox 组件

**Files:**
- Modify: `frontend/src/App.tsx`

### Step 1: 导入 Checkbox 组件

**修改位置:** `frontend/src/App.tsx` 第 2 行，添加 Checkbox 到导入列表

```typescript
import { ConfigProvider, Button, message, Space, InputNumber, Progress, Checkbox } from 'antd'
```

### Step 2: 添加 Checkbox UI

**修改位置:** `frontend/src/App.tsx` 第 269-279 行（在"每次同步条数"输入框下方）

找到这段代码：
```typescript
<div style={{ marginBottom: 16 }}>
  <label style={{ display: 'block', marginBottom: 8 }}>每次同步条数</label>
  <InputNumber
    min={1}
    max={99999}
    value={syncLimit}
    onChange={handleSyncLimitChange}
    style={{ width: '100%' }}
    placeholder="1-99999"
  />
</div>
```

在这段代码后面添加：
```typescript
<div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
  <span>过滤已同步邮件</span>
  <Checkbox
    checked={filterSyncedEmails}
    onChange={(e) => handleFilterSyncedChange(e.target.checked)}
  />
</div>
```

### Step 3: 类型检查

```bash
cd frontend
npx tsc --noEmit
```

预期输出: 无类型错误

### Step 4: 提交 UI 改动

```bash
git add frontend/src/App.tsx
git commit -m "feat: add filter synced emails checkbox UI"
```

---

## Task 6: 端到端测试

### Step 1: 启动后端服务

```bash
cd backend
python run.py
```

预期输出: 服务运行在 http://0.0.0.0:8000

### Step 2: 启动前端服务（新终端）

```bash
cd frontend
npm run dev
```

预期输出: 服务运行在 http://localhost:3000

### Step 3: 测试场景 1 - 不勾选过滤（默认行为）

1. 打开浏览器访问 http://localhost:3000
2. 确认"过滤已同步邮件"复选框**未勾选**
3. 添加一个测试邮箱账户（如果还没有）
4. 点击"立即同步全部"
5. 观察同步结果，记下邮件数量
6. 再次点击"立即同步全部"
7. **预期结果:** 第二次同步获取相同数量的邮件（重复获取）

### Step 4: 测试场景 2 - 勾选过滤

1. 勾选"过滤已同步邮件"复选框
2. 点击"立即同步全部"
3. **预期结果:** 同步完成，新邮件数量为 0（因为没有新邮件）
4. 打开浏览器开发者工具 → Application → Local Storage
5. 确认 `filterSyncedEmails` 值为 `true`

### Step 5: 测试场景 3 - localStorage 持久化

1. 刷新页面
2. **预期结果:** "过滤已同步邮件"复选框仍然处于勾选状态
3. 取消勾选复选框
4. 刷新页面
5. **预期结果:** 复选框处于未勾选状态

### Step 6: 测试场景 4 - 单账户同步

1. 取消勾选"过滤已同步邮件"
2. 点击某个账户的"同步"按钮（单个账户同步）
3. **预期结果:** 单账户同步也遵循过滤设置

### Step 7: 提交测试完成标记

```bash
git commit --allow-empty -m "test: verify filter synced emails feature works correctly"
```

---

## 验收标准

完成以上所有任务后，以下功能应该正常工作：

- [ ] 前端显示"过滤已同步邮件"复选框，默认未勾选
- [ ] 复选框状态正确保存到 localStorage
- [ ] 页面刷新后状态正确恢复
- [ ] 未勾选时，重复同步会获取相同邮件
- [ ] 勾选时，重复同步只获取新邮件
- [ ] 配置影响"同步全部"和单个账户同步
- [ ] 配置更改立即生效，无需重启服务

---

## 相关文档

- 设计文档: `docs/plans/2026-03-07-filter-synced-emails-design.md`
- 项目说明: `CLAUDE.md`
- 后端核心同步: `backend/app/email_sync.py:108-175`
- 后端同步路由: `backend/app/routers/sync.py`
- 前端主组件: `frontend/src/App.tsx`

---

## 注意事项

1. **默认值:** `filter_synced` 默认为 `false`（不过滤），这与需求一致
2. **向后兼容:** 老版本前端不传参数时，后端使用默认值 `false`
3. **EmailCache:** 无论是否过滤，同步的邮件都保存到 EmailCache 表
4. **用户体验:** 配置立即生效，无需重启服务
5. **测试数据:** 建议使用测试邮箱账户进行测试，避免影响真实数据
