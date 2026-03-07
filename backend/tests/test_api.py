from fastapi.testclient import TestClient
import pytest

from app.main import app

client = TestClient(app)

# 默认测试用户
TEST_USER_ID = "test-user-001"
TEST_HEADERS = {"X-User-Id": TEST_USER_ID}


def test_health_check():
    """测试健康检查接口"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_get_providers():
    """测试获取邮箱提供商列表"""
    response = client.get("/api/config/providers")
    assert response.status_code == 200
    providers = response.json()
    assert len(providers) == 4
    assert any(p["value"] == "qq" for p in providers)


def test_get_accounts_empty():
    """测试获取空账户列表"""
    response = client.get("/api/accounts", headers=TEST_HEADERS)
    assert response.status_code == 200
    assert response.json() == []


def test_create_account_invalid_provider():
    """测试创建账户 - 无效提供商"""
    response = client.post("/api/accounts",
        json={
            "email": "test@example.com",
            "auth_code": "test123",
            "provider": "invalid"
        },
        headers=TEST_HEADERS
    )
    assert response.status_code == 400


def test_get_sync_status():
    """测试获取同步状态"""
    response = client.get("/api/sync/status", headers=TEST_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "is_syncing" in data
    assert "total_emails" in data
    assert "accounts" in data


def test_get_sync_logs():
    """测试获取同步日志"""
    response = client.get("/api/sync/logs", headers=TEST_HEADERS)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_api_requires_user_id():
    """测试需要用户ID的接口"""
    # 账户列表
    assert client.get("/api/accounts").status_code == 401
    # 同步状态
    assert client.get("/api/sync/status").status_code == 401
    # 同步日志
    assert client.get("/api/sync/logs").status_code == 401
