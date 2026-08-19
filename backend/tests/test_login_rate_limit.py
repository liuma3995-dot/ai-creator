# -*- coding: utf-8 -*-
"""T4 登录限流与失败锁定回归测试（每个用例使用独立 IP 与用户名避免串扰）"""
import time

from app.core.config import settings


def _headers(ip: str) -> dict:
    return {"X-Real-IP": ip}


class TestLoginRateLimit:
    def test_ip_rate_limit_exceeded(self, client, test_user, monkeypatch):
        monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_ENABLED", True)
        ip = "203.0.113.101"
        statuses = []
        # 用正确密码触发限流（成功登录会清空失败计数，不会触发锁定）
        for _ in range(settings.LOGIN_RATE_LIMIT_PER_MINUTE + 1):
            r = client.post(
                "/api/v1/auth/login",
                json={"username": test_user.username, "password": "testpass123"},
                headers=_headers(ip),
            )
            statuses.append(r.status_code)
        assert statuses[-1] == 429, statuses
        assert statuses.count(429) >= 1
        from app.utils.login_limits import clear_login_rate
        clear_login_rate("user", ip)

    def test_failure_lockout_locks_account(self, client, db_session, monkeypatch):
        monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_ENABLED", True)
        from app.utils.login_limits import clear_login_failures, clear_login_rate
        from app.core.security import get_password_hash
        from app.models.user import User, UserStatus

        # 创建独立用户避免与其他用例串扰
        username = f"lockuser{int(time.time() * 1000)}"
        ip = "203.0.113.102"
        clear_login_rate("user", ip)
        clear_login_failures("user", username)
        user = User(
            username=username,
            email=f"{username}@example.com",
            password_hash=get_password_hash("correct-pass-123"),
            status=UserStatus.ACTIVE,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        for _ in range(settings.LOGIN_FAIL_LOCK_THRESHOLD):
            r = client.post(
                "/api/v1/auth/login",
                json={"username": username, "password": "wrong-pass"},
                headers=_headers(ip),
            )
            assert r.status_code == 401

        # 达到阈值后，即使密码正确也被锁定
        r = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "correct-pass-123"},
            headers=_headers(ip),
        )
        assert r.status_code == 429

        # 清理 Redis 锁定键，避免影响后续运行
        clear_login_failures("user", username)

    def test_successful_login_resets_failures(self, client, db_session, monkeypatch):
        monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_ENABLED", True)
        from app.utils.login_limits import clear_login_failures, clear_login_rate
        from app.core.security import get_password_hash
        from app.models.user import User, UserStatus

        username = f"resetuser{int(time.time() * 1000)}"
        ip = "203.0.113.103"
        clear_login_rate("user", ip)
        clear_login_failures("user", username)
        user = User(
            username=username,
            email=f"{username}@example.com",
            password_hash=get_password_hash("testpass123"),
            status=UserStatus.ACTIVE,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        for _ in range(settings.LOGIN_FAIL_LOCK_THRESHOLD - 1):
            r = client.post(
                "/api/v1/auth/login",
                json={"username": username, "password": "wrong-pass"},
                headers=_headers(ip),
            )
            assert r.status_code == 401

        # 正确登录成功后清零失败计数
        r = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "testpass123"},
            headers=_headers(ip),
        )
        assert r.status_code == 200

        # 再错 4 次仍不锁定（失败计数已重置）
        for _ in range(settings.LOGIN_FAIL_LOCK_THRESHOLD - 1):
            r = client.post(
                "/api/v1/auth/login",
                json={"username": username, "password": "wrong-pass"},
                headers=_headers(ip),
            )
            assert r.status_code == 401

        clear_login_failures("user", username)
        clear_login_rate("user", ip)

    def test_admin_login_rate_limit_stricter(self, client, admin_user, monkeypatch):
        monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_ENABLED", True)
        ip = "203.0.113.104"
        statuses = []
        for _ in range(settings.ADMIN_LOGIN_RATE_LIMIT_PER_MINUTE + 1):
            r = client.post(
                "/api/v1/auth/admin/login",
                json={"username": admin_user.username, "password": "adminpass123"},
                headers=_headers(ip),
            )
            statuses.append(r.status_code)
        assert statuses[-1] == 429, statuses
        from app.utils.login_limits import clear_login_rate
        clear_login_rate("admin", ip)
