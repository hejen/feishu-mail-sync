"""用户认证依赖"""
from fastapi import Header, HTTPException
from typing import Optional


async def get_current_user(x_user_id: Optional[str] = Header(None)) -> str:
    """从请求头获取当前用户ID
    
    Args:
        x_user_id: X-User-Id 请求头
        
    Returns:
        用户ID字符串
        
    Raises:
        HTTPException: 未提供用户身份信息时返回 401
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="未提供用户身份信息")
    return x_user_id
