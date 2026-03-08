import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import EmailAccount, EmailCache, get_db
from app.dependencies import get_current_user
from app.models.schemas import AccountCreate, AccountResponse, AccountUpdate, MessageResponse
from app.providers import get_provider_config
from app.utils.crypto import encrypt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/accounts", tags=["账户管理"])


def _clear_email_cache(db: Session, user_id: str, account_id: int) -> int:
    """清理指定账户的邮件缓存记录，返回删除的记录数

    清理失败时不抛出异常，仅记录错误日志，确保不影响账户操作。
    """
    try:
        deleted_count = db.query(EmailCache).filter(
            EmailCache.user_id == user_id,
            EmailCache.account_id == account_id
        ).delete()
        if deleted_count > 0:
            logger.info(f"[user_id={user_id}] 清理账户 {account_id} 的缓存记录: {deleted_count} 条")
        return deleted_count
    except Exception as e:
        logger.error(f"[user_id={user_id}] 清理账户 {account_id} 缓存失败: {str(e)}")
        return 0  # 返回 0 表示没有删除任何记录，但不抛出异常


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

    # 清理该账户可能存在的旧缓存记录（在同一个事务中）
    _clear_email_cache(db, user_id, db_account.id)

    db.commit()
    db.refresh(db_account)

    return MessageResponse(message="邮箱账户添加成功")


@router.get("", response_model=List[AccountResponse])
async def list_accounts(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    """获取当前用户的所有邮箱账户"""
    accounts = db.query(EmailAccount).filter(
        EmailAccount.user_id == user_id
    ).all()
    return accounts


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

    # 清理该账户的缓存记录（在同一个事务中）
    _clear_email_cache(db, user_id, account_id)

    db.delete(account)
    db.commit()

    return MessageResponse(message="邮箱账户删除成功")


@router.put("/{account_id}", response_model=MessageResponse)
async def update_account(
    account_id: int,
    account_update: AccountUpdate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
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
