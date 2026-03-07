import threading
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db, EmailAccount, SyncLog, EmailCache
from app.models.schemas import SyncStatus, SyncLogResponse, MessageResponse
from app.email_sync import sync_account, log_sync, get_cached_attachment, clear_attachment_cache
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/sync", tags=["同步操作"])

# 同步状态（按用户隔离）
sync_status_by_user: Dict[str, dict] = {}


def get_user_sync_status(user_id: str) -> dict:
    """获取用户的同步状态"""
    if user_id not in sync_status_by_user:
        sync_status_by_user[user_id] = {
            "is_syncing": False,
            "current_emails": [],
            "progress": {
                "total": 0,
                "current": 0,
                "status": "idle",
                "message": "",
                "error": None
            }
        }
    return sync_status_by_user[user_id]


def _background_sync(user_id: str, account_id: int, limit: int, filter_synced: bool = False):
    """后台同步任务（在线程中执行）"""
    user_status = get_user_sync_status(user_id)

    try:
        user_status["progress"]["status"] = "syncing"
        user_status["progress"]["message"] = "正在连接邮箱..."
        user_status["progress"]["total"] = 1
        user_status["progress"]["current"] = 0

        # 执行同步
        result = sync_account(user_id, account_id, limit=limit, filter_synced=filter_synced)

        if result["success"]:
            user_status["current_emails"] = result.get("emails", [])
            user_status["progress"]["status"] = "completed"
            user_status["progress"]["message"] = f"同步完成，共 {result['emails_count']} 封邮件"
            user_status["progress"]["current"] = 1
            log_sync(user_id, account_id, result["emails_count"], "success")
        else:
            user_status["progress"]["status"] = "failed"
            user_status["progress"]["error"] = result["error"]
            user_status["progress"]["message"] = f"同步失败: {result['error']}"
            log_sync(user_id, account_id, 0, "failed", result["error"])

    except Exception as e:
        user_status["progress"]["status"] = "failed"
        user_status["progress"]["error"] = str(e)
        user_status["progress"]["message"] = f"同步异常: {str(e)}"
    finally:
        user_status["is_syncing"] = False


def _background_sync_all(user_id: str, account_ids: List[int], limit: int, filter_synced: bool = False):
    """后台同步所有账户任务（在线程中执行）"""
    user_status = get_user_sync_status(user_id)

    try:
        user_status["progress"]["status"] = "syncing"
        user_status["progress"]["message"] = "正在连接邮箱..."
        user_status["progress"]["total"] = len(account_ids)
        user_status["progress"]["current"] = 0

        total_synced = 0
        errors = []
        total_accounts = len(account_ids)

        for idx, account_id in enumerate(account_ids, 1):
            # 更新进度：正在同步第 N 个账户
            user_status["progress"]["message"] = f"正在同步账户 {idx}/{total_accounts}..."

            result = sync_account(user_id, account_id, limit=limit, filter_synced=filter_synced)

            if result["success"]:
                total_synced += result["emails_count"]
                user_status["current_emails"].extend(result.get("emails", []))
                log_sync(user_id, account_id, result["emails_count"], "success")
            else:
                errors.append(f"账户 {idx}: {result['error']}")
                log_sync(user_id, account_id, 0, "failed", result["error"])

            # 更新进度：已处理 N 个账户
            user_status["progress"]["current"] = idx

        # 同步完成
        user_status["progress"]["status"] = "completed"
        if errors:
            user_status["progress"]["message"] = f"同步完成，{total_synced} 封新邮件。部分失败: {'; '.join(errors)}"
            user_status["progress"]["error"] = "; ".join(errors)
        else:
            user_status["progress"]["message"] = f"同步完成，共 {total_synced} 封邮件"

    except Exception as e:
        user_status["progress"]["status"] = "failed"
        user_status["progress"]["error"] = str(e)
        user_status["progress"]["message"] = f"同步异常: {str(e)}"
    finally:
        user_status["is_syncing"] = False


@router.post("/manual", response_model=MessageResponse)
async def manual_sync(
    limit: int = None,
    filter_synced: bool = False,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    """手动触发同步所有账户（异步模式）"""
    user_status = get_user_sync_status(user_id)

    if user_status["is_syncing"]:
        raise HTTPException(status_code=400, detail="正在同步中，请稍候")

    # 获取活跃账户
    accounts = db.query(EmailAccount).filter(
        EmailAccount.user_id == user_id,
        EmailAccount.is_active == True
    ).all()

    if not accounts:
        raise HTTPException(status_code=400, detail="没有可同步的账户")

    # 重置状态
    user_status["is_syncing"] = True
    user_status["current_emails"] = []
    user_status["progress"] = {
        "total": len(accounts),
        "current": 0,
        "status": "idle",
        "message": "",
        "error": None
    }
    clear_attachment_cache(user_id)

    # 启动后台线程
    account_ids = [acc.id for acc in accounts]
    thread = threading.Thread(
        target=_background_sync_all,
        args=(user_id, account_ids, limit, filter_synced),
        daemon=True
    )
    thread.start()

    return MessageResponse(message="同步任务已启动，请轮询 /api/sync/progress 获取进度")


@router.post("/manual/{account_id}", response_model=MessageResponse)
async def manual_sync_account(
    account_id: int,
    limit: int = None,
    filter_synced: bool = False,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    """手动同步单个账户（异步模式）"""
    user_status = get_user_sync_status(user_id)
    
    if user_status["is_syncing"]:
        raise HTTPException(status_code=400, detail="正在同步中，请稍候")

    account = db.query(EmailAccount).filter(
        EmailAccount.id == account_id,
        EmailAccount.user_id == user_id
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")

    # 重置状态
    user_status["is_syncing"] = True
    user_status["current_emails"] = []
    user_status["progress"] = {
        "total": 0,
        "current": 0,
        "status": "idle",
        "message": "",
        "error": None
    }

    # 启动后台线程
    thread = threading.Thread(
        target=_background_sync,
        args=(user_id, account_id, limit, filter_synced),
        daemon=True
    )
    thread.start()

    return MessageResponse(message="同步任务已启动，请轮询 /api/sync/progress 获取进度")


@router.get("/status", response_model=SyncStatus)
async def get_sync_status(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    """获取同步状态"""
    accounts = db.query(EmailAccount).filter(
        EmailAccount.user_id == user_id
    ).all()

    # 获取邮件总数
    total_emails = db.query(EmailCache).filter(
        EmailCache.user_id == user_id
    ).count()

    # 获取最近同步时间
    latest_log = db.query(SyncLog).filter(
        SyncLog.user_id == user_id
    ).order_by(SyncLog.sync_time.desc()).first()
    last_sync_time = latest_log.sync_time if latest_log else None
    
    user_status = get_user_sync_status(user_id)

    return SyncStatus(
        is_syncing=user_status["is_syncing"],
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
async def get_sync_logs(
    limit: int = 20, 
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    """获取同步日志"""
    logs = db.query(SyncLog).filter(
        SyncLog.user_id == user_id
    ).order_by(SyncLog.sync_time.desc()).limit(limit).all()
    return logs


@router.get("/progress")
async def get_sync_progress(user_id: str = Depends(get_current_user)):
    """获取同步进度

    Returns:
        {
            "total": 总邮件数,
            "current": 已处理数,
            "status": "idle" | "syncing" | "completed" | "failed",
            "message": 状态消息,
            "error": 错误信息（如果有）
        }
    """
    user_status = get_user_sync_status(user_id)
    return user_status["progress"]


@router.get("/emails")
async def get_synced_emails(user_id: str = Depends(get_current_user)):
    """获取已同步的邮件列表（用于前端写入多维表格）

    注意：附件只返回元信息（filename, size, type），不包含 content。
    需要通过 /api/sync/attachment/{message_id}/{index} 接口按需获取附件内容。
    """
    user_status = get_user_sync_status(user_id)
    return user_status.get("current_emails", [])


@router.get("/attachment/{message_id}/{index}")
async def get_attachment(
    message_id: str, 
    index: int,
    user_id: str = Depends(get_current_user)
):
    """获取单个附件的内容

    Args:
        message_id: 邮件的 Message-ID（需要 URL 编码）
        index: 附件索引（从 0 开始）

    Returns:
        附件信息，包含 content（base64 编码）
    """
    attachment = get_cached_attachment(user_id, message_id, index)
    if not attachment:
        raise HTTPException(
            status_code=404,
            detail=f"附件不存在或已过期（message_id={message_id}, index={index}）"
        )
    return attachment
