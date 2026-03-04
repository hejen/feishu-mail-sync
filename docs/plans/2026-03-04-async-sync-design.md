# 异步同步 + 进度查询设计

## 背景

当前 `/api/sync/manual` 是同步阻塞接口，同步大量邮件（500+）时会超时。需要改为异步模式，支持任意数量的邮件同步。

## 设计目标

- 同步请求立即返回，不阻塞
- 前端可查询同步进度
- 支持任意数量邮件同步
- 附件处理逻辑保持不变

## 架构设计

### 接口变更

| 接口 | 方法 | 变更 |
|------|------|------|
| `/api/sync/manual` | POST | 立即返回，后台执行同步 |
| `/api/sync/manual/{account_id}` | POST | 同上 |
| `/api/sync/progress` | GET | **新增** 返回同步进度 |
| `/api/sync/emails` | GET | 不变 |
| `/api/sync/attachment/{message_id}/{index}` | GET | 不变 |

### 数据结构

```python
sync_status = {
    "is_syncing": bool,
    "current_emails": [],  # 已同步的邮件列表
    "progress": {
        "total": int,       # 总邮件数
        "current": int,     # 已处理数
        "status": str,      # idle/syncing/completed/failed
        "message": str,     # 状态消息
        "error": str|None   # 错误信息
    }
}
```

### 流程

```
前端                              后端
  |                                 |
  |-- POST /sync/manual ---------> | 立即返回，启动后台线程
  |                                 |
  |-- GET /sync/progress --------> | 返回进度
  |   (每 1 秒轮询)                 |
  |                                 |
  |-- ... status == completed ...  |
  |                                 |
  |-- GET /sync/emails ----------> | 返回邮件列表
  |                                 |
  |-- GET /sync/attachment/... --> | 按需获取附件
```

## 实现细节

### 后端改动

**文件：`backend/app/routers/sync.py`**

1. 使用 `threading.Thread` 启动后台同步任务
2. 新增 `get_sync_progress` 接口
3. 同步过程中实时更新 `sync_status["progress"]`

**文件：`backend/app/email_sync.py`**

1. `sync_account` 增加 `progress_callback` 参数
2. 每处理一封邮件调用回调更新进度
3. 附件缓存逻辑保持不变

### 前端改动

**文件：`frontend/src/hooks/useSync.ts`**

1. 调用同步接口后开始轮询进度
2. 显示进度条 UI
3. 完成后获取邮件列表并写入表格

## 附件处理（保持不变）

- 同步时附件内容缓存到 `_attachment_cache`
- `/api/sync/emails` 只返回附件元信息 `{filename, size, type}`
- `/api/sync/attachment/{message_id}/{index}` 返回完整附件内容

## 注意事项

1. 服务重启会丢失同步进度（内存状态）
2. 同一时间只能有一个同步任务
3. 附件缓存在同步完成后仍可用，直到下次同步开始
