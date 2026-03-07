from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, UniqueConstraint
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
    __table_args__ = (
        UniqueConstraint('user_id', 'email', name='uq_user_email'),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String(64), index=True, nullable=False)  # 用户ID，用于数据隔离
    email = Column(String(255), index=True, nullable=False)
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
    user_id = Column(String(64), index=True, nullable=False)  # 用户ID，用于数据隔离
    account_id = Column(Integer, index=True, nullable=False)
    sync_time = Column(DateTime, default=datetime.utcnow)
    emails_count = Column(Integer, default=0)
    status = Column(String(50), nullable=False)  # success, failed, partial
    error_message = Column(Text, nullable=True)


class EmailCache(Base):
    """邮件缓存表 - 避免重复同步"""
    __tablename__ = "email_cache"
    __table_args__ = (
        UniqueConstraint('user_id', 'message_id', name='uq_user_message'),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String(64), index=True, nullable=False)  # 用户ID，用于数据隔离
    account_id = Column(Integer, index=True, nullable=False)
    message_id = Column(String(255), index=True, nullable=False)
    subject = Column(Text, nullable=True)
    sync_time = Column(DateTime, default=datetime.utcnow)


def migrate_to_multi_user():
    """迁移现有数据到多用户模式
    
    为现有数据库添加 user_id 字段，并将现有数据分配给默认用户。
    仅在检测到缺少 user_id 字段时执行迁移。
    """
    from sqlalchemy import text, inspect
    
    inspector = inspect(engine)
    
    # 检查表是否存在
    if 'email_accounts' not in inspector.get_table_names():
        print("数据库表不存在，跳过迁移")
        return
    
    # 检查是否已有 user_id 列
    columns = [col['name'] for col in inspector.get_columns('email_accounts')]
    
    if 'user_id' in columns:
        print("user_id 字段已存在，跳过迁移")
        return
    
    print("开始迁移数据到多用户模式...")
    
    with engine.connect() as conn:
        # 添加 user_id 列
        conn.execute(text("ALTER TABLE email_accounts ADD COLUMN user_id VARCHAR(64)"))
        conn.execute(text("ALTER TABLE sync_logs ADD COLUMN user_id VARCHAR(64)"))
        conn.execute(text("ALTER TABLE email_cache ADD COLUMN user_id VARCHAR(64)"))
        conn.commit()
        
        # 将现有数据分配给默认用户
        conn.execute(text("UPDATE email_accounts SET user_id = 'legacy-user-001'"))
        conn.execute(text("UPDATE sync_logs SET user_id = 'legacy-user-001'"))
        conn.execute(text("UPDATE email_cache SET user_id = 'legacy-user-001'"))
        conn.commit()
    
    print("数据迁移完成")


def init_db():
    """初始化数据库"""
    # 先尝试迁移现有数据
    migrate_to_multi_user()
    # 创建新表（如果不存在）
    Base.metadata.create_all(bind=engine)


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
