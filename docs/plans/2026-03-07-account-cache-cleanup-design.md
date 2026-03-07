# 账户添加/删除时清理 EmailCache 设计文档

**日期**: 2026-03-07
**状态**: 设计阶段

## 功能概述

在添加或删除邮箱账户时，自动清理该账户关联的 EmailCache 记录，确保数据一致性并防止旧记录干扰新账户的同步操作。

## 需求

### 用户故事
作为邮箱同步助手的用户，当我：
1. **重新添加已删除的邮箱账户**时，不希望看到旧的同步记录干扰
2. **删除邮箱账户**时，希望相关的邮件缓存也被清理，保持数据整洁

### 成功标准
- [ ] 添加账户时清理该 account_id 的所有 EmailCache 记录
- [ ] 删除账户时清理该 account_id 的所有 EmailCache 记录
- [ ] 清理操作失败不影响账户操作本身
- [ ] 清理操作记录日志便于监控

## 设计方案

### 方案选择

**采用方案A：直接在账户操作中清理**

**理由：**
- 简单直接，改动最小
- 逻辑清晰，易于理解和维护
- 与现有账户管理代码在同一位置
- 不需要数据库迁移

## 技术设计

### 1. 架构

在现有的账户管理路由中添加 EmailCache 清理逻辑：
- **添加账户时**：创建账户后，删除该 `account_id` 的所有 EmailCache 记录
- **删除账户时**：删除账户前，先删除对应的 EmailCache 记录

保持数据隔离，所有操作都基于 `user_id` 和 `account_id` 进行。

### 2. 涉及的组件

**修改文件：`backend/app/routers/accounts.py`**

#### 导入更新
```python
from app.database import get_db, EmailAccount, EmailCache  # 添加 EmailCache
import logging  # 添加日志

logger = logging.getLogger(__name__)
```

#### create_account 函数修改

**位置**：第14-48行

**修改点**：在账户创建成功后，清理该账户的缓存记录

```python
@router.post("", response_model=MessageResponse)
async def create_account(
    account: AccountCreate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
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
        user_id=user_id,
        email=account.email,
        provider=account.provider,
        auth_code=encrypt(account.auth_code),
        imap_server=provider_config.imap_server,
        imap_port=provider_config.imap_port
    )
    db.add(db_account)
    db.commit()
    db.refresh(db_account)

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

    return MessageResponse(message="邮箱账户添加成功")
```

#### delete_account 函数修改

**位置**：第63-79行

**修改点**：在删除账户之前，先清理缓存记录

```python
@router.delete("/{account_id}", response_model=MessageResponse)
async def delete_account(
    account_id: int,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    """删除邮箱账户"""
    account = db.query(EmailAccount).filter(
        EmailAccount.id == account_id,
        EmailAccount.user_id == user_id
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

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

    # 删除账户
    db.delete(account)
    db.commit()

    return MessageResponse(message="邮箱账户删除成功")
```

### 3. 数据流

#### 添加账户时的清理流程
```
用户添加邮箱账户
    ↓
检查账户是否已存在（通过 email + user_id）
    ↓
创建 EmailAccount 记录并提交到数据库
    ↓
清理该 account_id 的所有 EmailCache 记录
    ↓
返回成功消息
```

#### 删除账户时的清理流程
```
用户删除邮箱账户
    ↓
查询账户是否存在
    ↓
先删除该账户关联的所有 EmailCache 记录
    ↓
删除 EmailAccount 记录
    ↓
提交事务
    ↓
返回成功消息
```

### 4. 错误处理

**策略：**
1. 清理操作失败时记录日志但不阻止账户操作
2. 删除账户时清理和删除在同一事务中
3. 记录删除的记录数便于监控

**实现：**
- 使用 try-except 包裹清理操作
- 清理失败不影响账户创建/删除
- 记录详细的错误信息

### 5. 日志记录

**日志级别：**
- `logger.info`: 记录清理的记录数
- `logger.error`: 记录清理失败的错误

**日志格式：**
```
清理了账户 {account_id} 的 {count} 条缓存记录
清理缓存失败: {error_message}
```

## 测试策略

### 1. 单元测试

**test_accounts.py**
```python
def test_create_account_clears_cache(db_session):
    """测试添加账户时清理缓存"""
    # 1. 创建账户
    # 2. 添加一些 EmailCache 记录
    # 3. 调用 create_account
    # 4. 验证缓存被清理

def test_delete_account_clears_cache(db_session):
    """测试删除账户时清理缓存"""
    # 1. 创建账户并添加缓存
    # 2. 调用 delete_account
    # 3. 验证缓存被清理
```

### 2. 集成测试

```python
def test_full_lifecycle():
    """测试完整生命周期"""
    # 1. 添加账户 A
    # 2. 同步一些邮件
    # 3. 删除账户 A
    # 4. 验证 EmailCache 为空
    # 5. 重新添加账户 A
    # 6. 同步邮件
    # 7. 验证只有新邮件被同步
```

### 3. 手动测试场景

| 场景 | 操作 | 预期结果 |
|------|------|----------|
| 添加新账户 | 添加从未使用的邮箱 | 账户创建成功，无缓存清理日志 |
| 重新添加账户 | 删除后重新添加同一邮箱 | 账户创建成功，清理旧缓存 |
| 删除有缓存的账户 | 删除已同步过邮件的账户 | 账户删除成功，缓存被清理 |
| 删除无缓存的账户 | 删除从未同步的账户 | 账户删除成功，无缓存清理日志 |

## 实施清单

### 后端
- [ ] 更新 `accounts.py` 导入语句
- [ ] 修改 `create_account` 函数添加清理逻辑
- [ ] 修改 `delete_account` 函数添加清理逻辑
- [ ] 添加日志记录

### 测试
- [ ] 添加单元测试
- [ ] 执行手动测试
- [ ] 验证日志输出

## 注意事项

1. **事务一致性**：删除账户时，清理和删除操作在同一事务中
2. **错误处理**：清理失败不应阻止账户操作
3. **性能影响**：清理操作通常很快，因为 account_id 有索引
4. **数据隔离**：始终基于 `user_id` 和 `account_id` 进行操作
5. **向后兼容**：现有账户不受影响

## 相关文档

- 账户管理路由：`backend/app/routers/accounts.py`
- 数据库模型：`backend/app/database.py`
- EmailCache 表结构：`EmailCache` 类（第45-57行）
