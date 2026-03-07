# 邮箱同步助手 - 过滤已同步邮件配置功能设计

## 日期
2026-03-07

## 概述

添加一个全局配置选项，允许用户选择是否过滤已同步的邮件。默认不勾选（不过滤），用户可以随时调整此设置。

## 需求

### 用户故事
作为邮箱同步助手的用户，我希望能够控制是否过滤已同步的邮件，这样我可以选择：
- 不过滤：每次都获取最新的邮件（即使之前同步过）
- 过滤：跳过已经同步过的邮件，只同步新邮件

### 成功标准
- [ ] 前端UI显示配置选项（Checkbox）
- [ ] 配置状态保存在 localStorage
- [ ] 同步时配置参数传递到后端
- [ ] 后端根据配置决定是否过滤
- [ ] 不勾选时：重复同步同一封邮件
- [ ] 勾选时：第二次同步不包含已同步邮件

## 设计方案

### 方案选择
**采用方案A：前端传参 + 后端条件过滤**

理由：
- 最简单直接，改动最小
- 用户每次同步可以灵活调整
- 不需要修改数据库结构
- 与现有"每次同步条数"配置方式一致

## 技术设计

### 1. 前端设计

#### 1.1 UI布局
在"每次同步条数"配置项区域旁边添加：

```
┌─────────────────────────────────────────────┐
│  每次同步条数        [过滤已同步邮件] □      │
│  [ - ] [ 100 ] [ + ]   (默认不勾选)         │
│                                              │
│  [立即同步全部]  [添加邮箱账户]              │
└─────────────────────────────────────────────┘
```

#### 1.2 状态管理
```typescript
// App.tsx
const [filterSyncedEmails, setFilterSyncedEmails] = useState<boolean>(() => {
  const saved = localStorage.getItem('filterSyncedEmails')
  return saved === 'true' // 默认 false
})

const handleFilterChange = (checked: boolean) => {
  setFilterSyncedEmails(checked)
  localStorage.setItem('filterSyncedEmails', String(checked))
}
```

#### 1.3 API调用
```typescript
// 修改 API 调用，传递 filter_synced 参数
const handleSyncAll = async () => {
  await api.manualSync(syncLimit, filterSyncedEmails)
}

const handleSyncAccount = async (id: number) => {
  await api.manualSyncAccount(id, syncLimit, filterSyncedEmails)
}
```

### 2. 后端设计

#### 2.1 API参数
```python
# backend/app/routers/sync.py

@router.post("/manual")
async def manual_sync(
    limit: int = None,
    filter_synced: bool = False,  # 新增参数，默认 False
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    # ...
    thread = threading.Thread(
        target=_background_sync_all,
        args=(user_id, account_ids, limit, filter_synced),  # 传递参数
        daemon=True
    )

@router.post("/manual/{account_id}")
async def manual_sync_account(
    account_id: int,
    limit: int = None,
    filter_synced: bool = False,  # 新增参数
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    # ...
    thread = threading.Thread(
        target=_background_sync,
        args=(user_id, account_id, limit, filter_synced),  # 传递参数
        daemon=True
    )
```

#### 2.2 后台任务
```python
# backend/app/routers/sync.py

def _background_sync_all(user_id: str, account_ids: List[int], limit: int, filter_synced: bool):
    # ...
    for idx, account_id in enumerate(account_ids, 1):
        result = sync_account(user_id, account_id, limit=limit, filter_synced=filter_synced)
        # ...

def _background_sync(user_id: str, account_id: int, limit: int, filter_synced: bool):
    # ...
    result = sync_account(user_id, account_id, limit=limit, filter_synced=filter_synced)
    # ...
```

#### 2.3 核心同步逻辑
```python
# backend/app/email_sync.py

def sync_account(user_id: str, account_id: int, days: int = None, 
                 limit: int = None, filter_synced: bool = False) -> Dict:
    # ...
    emails, msg = sync_service.fetch_emails(days, limit, filter_synced)
    # ...

class EmailSyncService:
    def fetch_emails(self, days: int = 30, limit: int = None, 
                     filter_synced: bool = False,
                     progress_callback=None) -> Tuple[List[Dict], str]:
        # ... 搜索邮件代码 ...
        
        emails = []
        checked_count = 0
        
        # 根据配置决定是否过滤
        if filter_synced:
            # 原有逻辑：查询已同步邮件ID进行过滤
            synced_ids = set(
                row[0] for row in db.query(EmailCache.message_id).filter(
                    EmailCache.account_id == self.account.id,
                    EmailCache.user_id == self.user_id
                ).all()
            )
            
            for email_id in reversed(email_ids):
                email_data = self._parse_email(email_id)
                checked_count += 1
                
                if email_data and email_data["message_id"] not in synced_ids:
                    emails.append(email_data)
                    if limit and len(emails) >= limit:
                        break
        else:
            # 新逻辑：不过滤，直接获取最新邮件
            for email_id in reversed(email_ids):
                email_data = self._parse_email(email_id)
                checked_count += 1
                
                if email_data:
                    emails.append(email_data)
                    if limit and len(emails) >= limit:
                        break
        
        return emails, f"成功获取 {len(emails)} 封新邮件（检查了 {checked_count} 封）"
```

### 3. API客户端设计

```typescript
// frontend/src/services/api.ts

export const manualSync = (limit?: number, filterSynced?: boolean) =>
  api.post('/api/sync/manual', { params: { limit, filter_synced: filterSynced } })

export const manualSyncAccount = (id: number, limit?: number, filterSynced?: boolean) =>
  api.post(`/api/sync/manual/${id}`, { params: { limit, filter_synced: filterSynced } })
```

## 数据流

```
用户操作 Checkbox
    ↓
更新 localStorage + React state
    ↓
点击同步按钮
    ↓
API请求携带 filter_synced 参数
    ↓
后端路由接收参数
    ↓
传递给后台线程
    ↓
sync_account() 传递给 EmailSyncService
    ↓
fetch_emails() 根据参数决定过滤逻辑
    ↓
返回邮件列表
    ↓
保存到 EmailCache 表（无论是否过滤都保存）
```

## 错误处理

- **前端**：API调用失败时显示错误消息
- **后端**：参数验证（默认值False），异常捕获
- **一致性**：EmailCache表始终保存同步的邮件（用于统计和历史记录）

## 测试策略

### 1. 前端测试
- 验证Checkbox状态正确保存到 localStorage
- 验证页面刷新后状态正确恢复
- 验证API调用参数正确传递

### 2. API测试
- 验证 filter_synced 参数默认值为 false
- 验证参数正确传递到后台线程

### 3. 同步逻辑测试
**场景1：不勾选（filter_synced=false）**
1. 第一次同步：获取10封邮件
2. 第二次同步：再次获取相同的10封邮件（允许重复）

**场景2：勾选（filter_synced=true）**
1. 第一次同步：获取10封邮件
2. 第二次同步：不包含已同步的邮件（过滤生效）

## 实现清单

### 前端
- [ ] App.tsx: 添加 filterSyncedEmails state
- [ ] App.tsx: 添加 Checkbox UI组件
- [ ] App.tsx: 修改 handleSyncAll 和 handleSyncAccount 传递参数
- [ ] api.ts: 修改 API函数签名添加 filterSynced 参数

### 后端
- [ ] routers/sync.py: manual_sync 添加 filter_synced 参数
- [ ] routers/sync.py: manual_sync_account 添加 filter_synced 参数
- [ ] routers/sync.py: _background_sync_all 添加 filter_synced 参数
- [ ] routers/sync.py: _background_sync 添加 filter_synced 参数
- [ ] email_sync.py: sync_account 添加 filter_synced 参数
- [ ] email_sync.py: EmailSyncService.fetch_emails 添加 filter_synced 参数和条件逻辑

## 注意事项
1. **默认值**：filter_synced 默认为 false（不过滤），保持向后兼容
2. **EmailCache**：无论是否过滤，同步的邮件都保存到 EmailCache 表（用于统计）
3. **用户体验**：配置立即生效，无需重启服务
4. **一致性**：与"每次同步条数"配置的实现方式保持一致
