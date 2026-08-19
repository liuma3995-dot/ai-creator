# -*- coding: utf-8 -*-
"""T2/T3 管理登录与刷新端点 IP 白名单回归测试"""
from app.core.config import settings


def _login_headers(ip):
    return {"X-Real-IP": ip}


class TestAdminLoginIpWhitelist:
    def test_no_whitelist_allows_admin_login(self, client, admin_user, monkeypatch):
        monkeypatch.setattr(settings, "ADMIN_IP_WHITELIST", [])
        r = client.post(
            "/api/v1/auth/admin/login",
            json={"username": admin_user.username, "password": "adminpass123"},
        )
        assert r.status_code == 200

    def test_non_whitelisted_ip_rejected(self, client, admin_user, monkeypatch):
        monkeypatch.setattr(settings, "ADMIN_IP_WHITELIST", ["203.0.113.10"])
        r = client.post(
            "/api/v1/auth/admin/login",
            json={"username": admin_user.username, "password": "adminpass123"},
            headers=_login_headers("198.51.100.7"),
        )
        assert r.status_code == 403
        assert "白名单" in r.json()["message"]

    def test_whitelisted_ip_allowed(self, client, admin_user, monkeypatch):
        monkeypatch.setattr(settings, "ADMIN_IP_WHITELIST", ["203.0.113.10"])
        r = client.post(
            "/api/v1/auth/admin/login",
            json={"username": admin_user.username, "password": "adminpass123"},
            headers=_login_headers("203.0.113.10"),
        )
        assert r.status_code == 200

    def test_admin_refresh_rejects_non_whitelisted_ip(self, client, admin_user, monkeypatch):
        # 先正常登录拿 refresh 令牌
        login = client.post(
            "/api/v1/auth/admin/login",
            json={"username": "adminuser", "password": "adminpass123"},
            headers=_login_headers("203.0.113.10"),
        )
        assert login.status_code == 200
        refresh = login.json()["data"]["refresh_token"]

        monkeypatch.setattr(settings, "ADMIN_IP_WHITELIST", ["203.0.113.10"])
        r = client.post(
            "/api/v1/auth/admin/refresh",
            json={"refresh_token": refresh},
            headers=_login_headers("198.51.100.7"),
        )
        assert r.status_code == 403
