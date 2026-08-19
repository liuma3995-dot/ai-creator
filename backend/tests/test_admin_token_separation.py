# -*- coding: utf-8 -*-
"""T1 管理员令牌与用户令牌分离回归测试"""
from jose import jwt

from app.core.config import settings


def _token_type(token: str) -> str:
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    return payload.get("type")


class TestAdminTokenSeparation:
    def test_user_token_rejected_on_admin_api_even_with_admin_role(
        self, client, db_session, test_user
    ):
        """普通用户令牌即使把 role 改成 admin 也不能访问管理接口"""
        from app.models.user import UserRole

        test_user.role = UserRole.ADMIN
        db_session.commit()

        r = client.post("/api/v1/auth/login", json={
            "username": test_user.username, "password": "testpass123",
        })
        assert r.status_code == 200
        user_token = r.json()["data"]["access_token"]

        resp = client.get(
            "/api/v1/admin/operation/referral/rule",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 401, resp.text

    def test_admin_login_issues_admin_token_and_accesses_admin_api(
        self, client, admin_headers
    ):
        r = client.get(
            "/api/v1/admin/operation/referral/rule",
            headers=admin_headers,
        )
        assert r.status_code == 200

    def test_admin_token_rejected_on_user_api(self, client, admin_headers):
        r = client.get("/api/v1/auth/me", headers=admin_headers)
        assert r.status_code == 401, r.text

    def test_refresh_token_cannot_be_used_as_access_token(self, client, auth_headers, test_user):
        login = client.post("/api/v1/auth/login", json={
            "username": test_user.username, "password": "testpass123",
        })
        refresh = login.json()["data"]["refresh_token"]
        r = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {refresh}"},
        )
        assert r.status_code == 401, r.text

    def test_user_refresh_cannot_issue_admin_token(self, client, auth_headers, test_user):
        login = client.post("/api/v1/auth/login", json={
            "username": test_user.username, "password": "testpass123",
        })
        refresh = login.json()["data"]["refresh_token"]
        r = client.post("/api/v1/auth/admin/refresh", json={"refresh_token": refresh})
        assert r.status_code == 401, r.text

    def test_admin_login_rejected_for_normal_user(self, client, test_user):
        r = client.post("/api/v1/auth/admin/login", json={
            "username": test_user.username, "password": "testpass123",
        })
        assert r.status_code == 403, r.text

    def test_token_types_are_distinct(self, client, auth_headers, admin_headers):
        # 用户登录签发 user 访问令牌
        user_login = client.post("/api/v1/auth/login", json={
            "username": "testuser", "password": "testpass123",
        })
        user_token = user_login.json()["data"]["access_token"]
        assert _token_type(user_token) == "user"

        # 管理员登录签发 admin 访问令牌
        admin_token = admin_headers["Authorization"].replace("Bearer ", "")
        assert _token_type(admin_token) == "admin"


class TestAdminIpWhitelist:
    """T2 管理接口 IP 白名单（应用层兜底）"""

    def test_no_whitelist_allows_all(self, client, admin_headers, monkeypatch):
        monkeypatch.setattr(settings, "ADMIN_IP_WHITELIST", [])
        r = client.get("/api/v1/admin/operation/referral/rule", headers=admin_headers)
        assert r.status_code == 200

    def test_whitelist_denies_non_whitelisted_ip(self, client, admin_headers, monkeypatch):
        monkeypatch.setattr(settings, "ADMIN_IP_WHITELIST", ["203.0.113.10"])
        r = client.get(
            "/api/v1/admin/operation/referral/rule",
            headers={**admin_headers, "X-Real-IP": "198.51.100.7"},
        )
        assert r.status_code == 403
        assert "白名单" in r.json()["message"]

    def test_whitelist_allows_matching_ip(self, client, admin_headers, monkeypatch):
        monkeypatch.setattr(settings, "ADMIN_IP_WHITELIST", ["203.0.113.10"])
        r = client.get(
            "/api/v1/admin/operation/referral/rule",
            headers={**admin_headers, "X-Real-IP": "203.0.113.10"},
        )
        assert r.status_code == 200

    def test_whitelist_supports_cidr(self, client, admin_headers, monkeypatch):
        monkeypatch.setattr(settings, "ADMIN_IP_WHITELIST", ["10.0.0.0/8"])
        r = client.get(
            "/api/v1/admin/operation/referral/rule",
            headers={**admin_headers, "X-Real-IP": "10.1.2.3"},
        )
        assert r.status_code == 200
