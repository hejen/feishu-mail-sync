from fastapi import APIRouter
from typing import List

from app.models.schemas import ProviderConfig, SyncIntervalUpdate, MessageResponse
from app.providers import get_all_providers

router = APIRouter(prefix="/api/config", tags=["配置管理"])


@router.get("/providers", response_model=List[ProviderConfig])
async def get_providers():
    """获取支持的邮箱提供商配置"""
    return get_all_providers()


@router.put("/sync-interval", response_model=MessageResponse)
async def update_sync_interval(config: SyncIntervalUpdate):
    """设置同步间隔"""
    # 这里可以保存到数据库或配置文件
    # 目前仅返回成功消息
    valid_intervals = [15, 30, 60]
    if config.interval_minutes not in valid_intervals:
        return MessageResponse(
            message=f"无效的同步间隔，可选值: {valid_intervals}",
            success=False
        )
    return MessageResponse(message=f"同步间隔已设置为 {config.interval_minutes} 分钟")
