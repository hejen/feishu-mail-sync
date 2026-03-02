from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os

from app.config import settings


def get_encryption_key() -> bytes:
    """从配置获取加密密钥"""
    key = settings.encryption_key.encode()
    # 使用 PBKDF2 派生固定长度的密钥
    salt = b'email_sync_salt'  # 生产环境应从配置获取
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    return base64.urlsafe_b64encode(kdf.derive(key))


def encrypt(text: str) -> str:
    """加密文本"""
    f = Fernet(get_encryption_key())
    return f.encrypt(text.encode()).decode()


def decrypt(encrypted_text: str) -> str:
    """解密文本"""
    f = Fernet(get_encryption_key())
    return f.decrypt(encrypted_text.encode()).decode()
