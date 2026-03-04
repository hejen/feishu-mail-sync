# 邮件同步性能优化设计

## 背景

当前邮件同步逻辑在处理大量未同步邮件时效率低下：
- 先 fetch 所有邮件的完整内容
- 再在内存中过滤和排序
- 最后截取 limit 数量返回

如果有 7000 封未同步邮件，limit 只需要 50 封，当前会完整 fetch 全部 7000 封。

## 优化目标

- 减少总体同步时间
- 主要场景：同步最近新邮件，未同步数量较少
- 策略：只取最新的 N 封未同步邮件

## 设计方案

### 核心思路

先批量获取轻量级日期头进行排序，再只对需要的邮件获取完整内容。

### 流程

```
1. 搜索日期范围内的所有邮件 ID
2. 批量获取所有邮件的日期头（1-3秒）
3. 解析日期并按降序排序（最新在前）
4. 获取已同步 ID 集合
5. 遍历排序后的列表：
   - 跳过已同步的邮件
   - 对未同步邮件获取完整内容
   - 达到 limit 时立即停止
6. 返回结果（无需额外排序）
```

### 效果对比

| 场景 | 当前耗时 | 优化后耗时 |
|------|----------|------------|
| 7000 封邮件，limit=50 | fetch 7000 封（几分钟） | 获取日期头 + fetch 50 封（10-20秒） |
| 100 封邮件，10 封未同步，limit=50 | fetch 100 封 | 获取日期头 + fetch 10 封 |
| 10000 封邮件，5 封未同步，limit=50 | fetch 10000 封 | 获取日期头 + fetch 5 封 |

### 代码改动

#### 文件：`backend/app/email_sync.py`

**新增方法**：`_fetch_dates`

批量获取邮件日期头，返回 `{email_id: datetime}` 映射。

```python
def _fetch_dates(self, email_ids: List[bytes]) -> Dict[bytes, datetime]:
    """批量获取邮件日期头"""
    if not email_ids:
        return {}

    # 构建 ID 列表字符串
    id_str = b",".join(email_ids)

    # 获取日期头
    status, data = self.imap.fetch(id_str, "(BODY.PEEK[HEADER.FIELDS (DATE)])")

    result = {}
    if status == "OK":
        for i in range(0, len(data), 2):
            email_id = data[i][0].split()[0]
            header = data[i][1].decode("utf-8", errors="ignore")
            # 解析日期
            date_str = header.replace("Date:", "").strip()
            try:
                date_tuple = email.utils.parsedate_tz(date_str)
                if date_tuple:
                    result[email_id] = datetime.fromtimestamp(
                        email.utils.mktime_tz(date_tuple)
                    )
            except:
                pass

    return result
```

**修改方法**：`fetch_emails`

按日期排序后遍历，达到 limit 时提前退出。

## 风险

- 获取日期头增加约 1-3 秒开销（可接受）
- 极端情况：所有邮件都已同步，仍需获取日期头（但不会 fetch 完整内容）

## 测试计划

1. 单元测试：`_fetch_dates` 方法
2. 集成测试：完整同步流程
3. 性能测试：对比 7000 封邮件场景的耗时
