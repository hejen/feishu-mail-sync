import threading

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db, EmailAccount, SyncLog
from app.models.schemas import SyncStatus, SyncLogResponse, MessageResponse
from app.email_sync import sync_account, log_sync, get_cached_attachment, clear_attachment_cache

router = APIRouter(prefix="/api/sync", tags=["同步操作"])

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


def _background_sync(account_id: int, limit: int):
    """后台同步任务（在线程中执行）"""
    from app.email_sync import sync_account

    try:
        sync_status["progress"]["status"] = "syncing"
        sync_status["progress"]["message"] = "正在连接邮箱..."

        # 执行同步
        result = sync_account(account_id, limit=limit)

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


@router.post("/manual", response_model=MessageResponse)
async def manual_sync(limit: int = None, db: Session = Depends(get_db)):
    """手动触发同步所有账户"""
    if sync_status["is_syncing"]:
        raise HTTPException(status_code=400, detail="正在同步中，请稍候")

    sync_status["is_syncing"] = True
    sync_status["current_emails"] = []
    clear_attachment_cache()  # 清空旧缓存

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
    """手动同步单个账户（异步模式）"""
    if sync_status["is_syncing"]:
        raise HTTPException(status_code=400, detail="正在同步中，请稍候")

    account = db.query(EmailAccount).filter(EmailAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    # 重置状态
    sync_status["is_syncing"] = True
    sync_status["current_emails"] = []
    reset_progress()

    # 启动后台线程
    thread = threading.Thread(
        target=_background_sync,
        args=(account_id, limit),
        daemon=True
    )
    thread.start()

    return MessageResponse(message="同步任务已启动，请轮询 /api/sync/progress 获取进度")


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
    """获取已同步的邮件列表（用于前端写入多维表格）

    注意：附件只返回元信息（filename, size, type），不包含 content。
    需要通过 /api/sync/attachment/{message_id}/{index} 接口按需获取附件内容。
    """
    return sync_status.get("current_emails", [])


@router.get("/attachment/{message_id}/{index}")
async def get_attachment(message_id: str, index: int):
    """获取单个附件的内容

    Args:
        message_id: 邮件的 Message-ID（需要 URL 编码）
        index: 附件索引（从 0 开始）

    Returns:
        附件信息，包含 content（base64 编码）
    """
    attachment = get_cached_attachment(message_id, index)
    if not attachment:
        raise HTTPException(
            status_code=404,
            detail=f"附件不存在或已过期（message_id={message_id}, index={index}）"
        )
    return attachment
