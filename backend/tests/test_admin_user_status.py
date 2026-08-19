# -*- coding: utf-8 -*-
"""用户管理：停用/启用账号与删除改归档兜底回归测试"""
from app.models.user import User, UserRole, UserStatus


def _login(client, username, password):
    return client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )


class TestToggleUserStatus:
    """T1 停用/启用账号"""

    def test_disable_user_blocks_login_and_enable_restores(self, client, db_session, admin_headers):
        user = User(
            username="togglestatus",
            email="togglestatus@example.com",
            password_hash="x",
            status=UserStatus.ACTIVE,
        )
        # 需要可用密码用于登录验证
        from app.core.security import get_password_hash
        user.password_hash = get_password_hash("pass123456")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        assert _login(client, "togglestatus", "pass123456").status_code == 200

        r = client.post(
            f"/api/v1/admin/users/{user.id}/toggle-status",
            params={"is_active": False},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "inactive"
        assert _login(client, "togglestatus", "pass123456").status_code == 403

        r = client.post(
            f"/api/v1/admin/users/{user.id}/toggle-status",
            params={"is_active": True},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert _login(client, "togglestatus", "pass123456").status_code == 200

    def test_cannot_toggle_self(self, client, admin_headers, admin_user):
        r = client.post(
            f"/api/v1/admin/users/{admin_user.id}/toggle-status",
            params={"is_active": False},
            headers=admin_headers,
        )
        assert r.status_code == 400
        assert "自己" in (r.json().get("detail") or r.json().get("message") or "")

    def test_normal_user_cannot_toggle(self, client, auth_headers, test_user):
        r = client.post(
            f"/api/v1/admin/users/{test_user.id}/toggle-status",
            params={"is_active": False},
            headers=auth_headers,
        )
        assert r.status_code in (401, 403)


class TestArchiveUser:
    """T2 删除接口改归档兜底（软删除 + 二次确认）"""

    def test_delete_requires_confirm_param(self, client, admin_headers, test_user):
        r = client.delete(f"/api/v1/admin/users/{test_user.id}", headers=admin_headers)
        assert r.status_code == 422

    def test_delete_with_mismatched_confirm_rejected(self, client, admin_headers, test_user):
        r = client.delete(
            f"/api/v1/admin/users/{test_user.id}",
            params={"confirm_user_id": 99999},
            headers=admin_headers,
        )
        assert r.status_code == 400
        assert "确认参数不一致" in (r.json().get("detail") or r.json().get("message") or "")

    def test_delete_with_confirm_archives_user(self, client, db_session, admin_headers, test_user):
        r = client.delete(
            f"/api/v1/admin/users/{test_user.id}",
            params={"confirm_user_id": test_user.id},
            headers=admin_headers,
        )
        assert r.status_code == 200

        db_session.expire_all()
        archived = db_session.query(User).filter(User.id == test_user.id).first()
        assert archived.deleted_at is not None
        assert archived.status == UserStatus.INACTIVE

        # 列表不再出现（软删过滤）
        listing = client.get("/api/v1/admin/users/list", headers=admin_headers)
        ids = [u["id"] for u in listing.json()["data"]["users"]]
        assert test_user.id not in ids

    def test_cannot_archive_admin_user(self, client, db_session, admin_headers):
        from app.core.security import get_password_hash

        other_admin = User(
            username="otheradmin",
            email="otheradmin@example.com",
            password_hash=get_password_hash("pass123456"),
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
        )
        db_session.add(other_admin)
        db_session.commit()
        db_session.refresh(other_admin)

        r = client.delete(
            f"/api/v1/admin/users/{other_admin.id}",
            params={"confirm_user_id": other_admin.id},
            headers=admin_headers,
        )
        assert r.status_code == 400
        assert "管理员" in (r.json().get("detail") or r.json().get("message") or "")

    def test_cannot_archive_self(self, client, admin_headers, admin_user):
        r = client.delete(
            f"/api/v1/admin/users/{admin_user.id}",
            params={"confirm_user_id": admin_user.id},
            headers=admin_headers,
        )
        assert r.status_code == 400
