from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """应用配置"""
    app_name: str = "邮箱同步助手"
    debug: bool = True

    # 数据库配置
    database_url: str = "sqlite:///./email_sync.db"

    # 加密密钥（生产环境应从环境变量获取）
    encryption_key: str = "your-secret-key-32-bytes-long!!"

    # 同步配置
    default_sync_days: int = 30
    max_retry_count: int = 3

    class Config:
        env_file = ".env"


settings = Settings()
