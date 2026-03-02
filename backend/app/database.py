from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from app.config import settings

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class EmailAccount(Base):
    """邮箱账户表"""
    __tablename__ = "email_accounts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    provider = Column(String(50), nullable=False)
    auth_code = Column(Text, nullable=False)  # 加密存储
    imap_server = Column(String(255), nullable=False)
    imap_port = Column(Integer, nullable=False, default=993)
    last_sync_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)


class SyncLog(Base):
    """同步记录表"""
    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    account_id = Column(Integer, index=True, nullable=False)
    sync_time = Column(DateTime, default=datetime.utcnow)
    emails_count = Column(Integer, default=0)
    status = Column(String(50), nullable=False)  # success, failed, partial
    error_message = Column(Text, nullable=True)


class EmailCache(Base):
    """邮件缓存表 - 避免重复同步"""
    __tablename__ = "email_cache"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    account_id = Column(Integer, index=True, nullable=False)
    message_id = Column(String(255), unique=True, index=True, nullable=False)
    subject = Column(Text, nullable=True)
    sync_time = Column(DateTime, default=datetime.utcnow)


def init_db():
    """初始化数据库"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
