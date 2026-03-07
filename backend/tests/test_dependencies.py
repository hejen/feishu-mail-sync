# backend/tests/test_dependencies.py
import pytest
import asyncio
from fastapi import HTTPException

from app.dependencies import get_current_user


def test_get_current_user_with_valid_header():
    """测试有效的 X-User-Id header"""
    async def test():
        user_id = await get_current_user(x_user_id="user-123")
        assert user_id == "user-123"
    
    asyncio.run(test())


def test_get_current_user_missing_header():
    """测试缺少 X-User-Id header 时抛出异常"""
    async def test():
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(x_user_id=None)
        assert exc_info.value.status_code == 401
        assert "未提供用户身份信息" in exc_info.value.detail
    
    asyncio.run(test())


def test_get_current_user_empty_string():
    """测试空字符串时抛出异常"""
    async def test():
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(x_user_id="")
        assert exc_info.value.status_code == 401
    
    asyncio.run(test())
