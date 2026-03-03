from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db, EmailAccount, SyncLog
from app.models.schemas import SyncStatus, SyncLogResponse, MessageResponse
from app.email_sync import sync_account, log_sync

router = APIRouter(prefix="/api/sync", tags=["同步操作"])

# 同步状态（内存中）
sync_status = {
    "is_syncing": False,
    "current_emails": []
}


@router.post("/manual", response_model=MessageResponse)
async def manual_sync(limit: int = None, db: Session = Depends(get_db)):
    """手动触发同步所有账户"""
    if sync_status["is_syncing"]:
        raise HTTPException(status_code=400, detail="正在同步中，请稍候")

    sync_status["is_syncing"] = True
    sync_status["current_emails"] = []

    try:
        accounts = db.query(EmailAccount).filter(EmailAccount.is_active == True).all()

        total_synced = 0
        errors = []

        for account in accounts:
            result = sync_account(account.id, limit=limit)

            if result["success"]:
                total_synced += result["emails_count"]
                sync_status["current_emails"].extend(result.get("emails", []))
                log_sync(account.id, result["emails_count"], "success")
            else:
                errors.append(f"{account.email}: {result['error']}")
                log_sync(account.id, 0, "failed", result["error"])

        if errors:
            return MessageResponse(
                message=f"同步完成，{total_synced} 封新邮件。部分失败: {'; '.join(errors)}",
                success=True
            )
        return MessageResponse(message=f"同步完成，{total_synced} 封新邮件")

    finally:
        sync_status["is_syncing"] = False


@router.post("/manual/{account_id}", response_model=MessageResponse)
async def manual_sync_account(account_id: int, limit: int = None, db: Session = Depends(get_db)):
    """手动同步单个账户"""
    if sync_status["is_syncing"]:
        raise HTTPException(status_code=400, detail="正在同步中，请稍候")

    sync_status["is_syncing"] = True
    sync_status["current_emails"] = []

    try:
        account = db.query(EmailAccount).filter(EmailAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="账户不存在")

        result = sync_account(account_id, limit=limit)

        if result["success"]:
            # 将邮件存储到内存中供前端获取
            sync_status["current_emails"] = result.get("emails", [])
            log_sync(account_id, result["emails_count"], "success")
            return MessageResponse(message=f"同步完成，{result['emails_count']} 封新邮件")
        else:
            log_sync(account_id, 0, "failed", result["error"])
            raise HTTPException(status_code=500, detail=result["error"])
    finally:
        sync_status["is_syncing"] = False


@router.get("/status", response_model=SyncStatus)
async def get_sync_status(db: Session = Depends(get_db)):
    """获取同步状态"""
    accounts = db.query(EmailAccount).all()

    # 获取邮件总数
    from app.database import EmailCache
    total_emails = db.query(EmailCache).count()

    # 获取最近同步时间
    latest_log = db.query(SyncLog).order_by(SyncLog.sync_time.desc()).first()
    last_sync_time = latest_log.sync_time if latest_log else None

    return SyncStatus(
        is_syncing=sync_status["is_syncing"],
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
async def get_sync_logs(limit: int = 20, db: Session = Depends(get_db)):
    """获取同步日志"""
    logs = db.query(SyncLog).order_by(SyncLog.sync_time.desc()).limit(limit).all()
    return logs


@router.get("/emails")
async def get_synced_emails(db: Session = Depends(get_db)):
    """获取已同步的邮件列表（用于前端写入多维表格）"""
    return sync_status.get("current_emails", [])
