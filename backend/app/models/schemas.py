from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


# ===== 邮箱账户相关 =====

class AccountCreate(BaseModel):
    """创建邮箱账户请求"""
    email: str
    auth_code: str
    provider: str  # qq, 163, 126, feishu


class AccountResponse(BaseModel):
    """邮箱账户响应"""
    id: int
    email: str
    provider: str
    imap_server: str
    imap_port: int
    last_sync_time: Optional[datetime]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AccountUpdate(BaseModel):
    """更新邮箱账户请求"""
    auth_code: Optional[str] = None
    is_active: Optional[bool] = None


# ===== 同步相关 =====

class SyncStatus(BaseModel):
    """同步状态"""
    is_syncing: bool
    last_sync_time: Optional[datetime]
    total_emails: int
    accounts: List[dict]


class SyncLogResponse(BaseModel):
    """同步日志响应"""
    id: int
    account_id: int
    sync_time: datetime
    emails_count: int
    status: str
    error_message: Optional[str]

    class Config:
        from_attributes = True


# ===== 配置相关 =====

class ProviderConfig(BaseModel):
    """邮箱提供商配置"""
    name: str
    value: str
    imap_server: str
    imap_port: int
    help_url: str


class SyncIntervalUpdate(BaseModel):
    """更新同步间隔"""
    interval_minutes: int  # 15, 30, 60


# ===== 通用响应 =====

class MessageResponse(BaseModel):
    """通用消息响应"""
    message: str
    success: bool = True
