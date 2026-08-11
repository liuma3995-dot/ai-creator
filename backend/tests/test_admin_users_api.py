# -*- coding: utf-8 -*-
"""
管理员用户管理 API 测试
覆盖：用户列表、详情、重置密码、模型状态切换、软删除
"""
from app.core.security import verify_password
from app.models.ai_model import AIModel
from app.models.user import User


def _make_user(db, username, email, **kwargs):
    defaults = dict(password_hash="hashed")
    defaults.update(kwargs)
    user = User(username=username, email=email, **defaults)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class TestUserListAPI:
    """用户列表接口测试"""

    def test_list_requires_admin(self, client, auth_headers):
        r = client.get("/api/v1/admin/users/list", headers=auth_headers)
        assert r.status_code == 403

    def test_list_anonymous(self, client):
        r = client.get("/api/v1/admin/users/list")
        assert r.status_code in (401, 403)

    def test_list_as_admin(self, client, admin_headers):
        r = client.get("/api/v1/admin/users/list", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total"] >= 1
        assert data["total_pages"] >= 1

    def test_list_keyword_search(self, client, admin_headers):
        r = client.get(
            "/api/v1/admin/users/list",
            params={"keyword": "adminuser"},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["data"]["total"] == 1

    def test_list_excludes_deleted(self, client, admin_headers, db_session):
        deleted = _make_user(db_session, "goneuser", "gone@example.com")
        from datetime import datetime
        deleted.deleted_at = datetime.now()
        db_session.commit()
        r = client.get(
            "/api/v1/admin/users/list",
            params={"keyword": "goneuser"},
            headers=admin_headers,
        )
        assert r.json()["data"]["total"] == 0


class TestUserDetailAPI:
    """用户详情接口测试"""

    def test_get_detail(self, client, admin_headers, db_session):
        user = _make_user(db_session, "detailuser", "detail@example.com")
        r = client.get(f"/api/v1/admin/users/{user.id}", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["user"]["username"] == "detailuser"
        assert "ai_models" in data

    def test_get_detail_not_found(self, client, admin_headers):
        r = client.get("/api/v1/admin/users/99999", headers=admin_headers)
        assert r.status_code == 404


class TestResetPasswordAPI:
    """重置密码接口测试"""

    def test_reset_password(self, client, admin_headers, db_session):
        user = _make_user(db_session, "resetuser", "reset@example.com")
        r = client.post(f"/api/v1/admin/users/{user.id}/reset-password", headers=admin_headers)
        assert r.status_code == 200
        updated = db_session.query(User).filter(User.id == user.id).first()
        assert verify_password("123456", updated.password_hash)

    def test_reset_password_self_forbidden(self, client, admin_headers, admin_user):
        r = client.post(f"/api/v1/admin/users/{admin_user.id}/reset-password", headers=admin_headers)
        assert r.status_code == 400

    def test_reset_password_not_found(self, client, admin_headers):
        r = client.post("/api/v1/admin/users/99999/reset-password", headers=admin_headers)
        assert r.status_code == 404


class TestToggleModelStatusAPI:
    """模型启用状态切换接口测试"""

    def test_toggle_model_status(self, client, admin_headers, db_session):
        user = _make_user(db_session, "modeluser", "model@example.com")
        model = AIModel(
            user_id=user.id,
            name="测试模型",
            provider="openai",
            model_name="gpt-4",
            api_key="fake-key",
            is_active=True,
        )
        db_session.add(model)
        db_session.commit()
        db_session.refresh(model)

        r = client.post(
            f"/api/v1/admin/users/{user.id}/toggle-model-status",
            params={"model_id": model.id, "is_active": False},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["data"]["is_active"] is False
        refreshed = db_session.query(AIModel).filter(AIModel.id == model.id).first()
        assert refreshed.is_active is False

    def test_toggle_model_status_user_not_found(self, client, admin_headers):
        r = client.post(
            "/api/v1/admin/users/99999/toggle-model-status",
            params={"model_id": 1, "is_active": True},
            headers=admin_headers,
        )
        assert r.status_code == 404

    def test_toggle_model_status_model_not_found(self, client, admin_headers, db_session):
        user = _make_user(db_session, "modeluser2", "model2@example.com")
        r = client.post(
            f"/api/v1/admin/users/{user.id}/toggle-model-status",
            params={"model_id": 99999, "is_active": True},
            headers=admin_headers,
        )
        assert r.status_code == 404


class TestDeleteUserAPI:
    """删除用户接口测试"""

    def test_delete_user_soft(self, client, admin_headers, db_session):
        user = _make_user(db_session, "deluser", "del@example.com")
        r = client.delete(f"/api/v1/admin/users/{user.id}", headers=admin_headers)
        assert r.status_code == 200
        updated = db_session.query(User).filter(User.id == user.id).first()
        assert updated.deleted_at is not None

    def test_delete_self_forbidden(self, client, admin_headers, admin_user):
        r = client.delete(f"/api/v1/admin/users/{admin_user.id}", headers=admin_headers)
        assert r.status_code == 400

    def test_delete_user_not_found(self, client, admin_headers):
        r = client.delete("/api/v1/admin/users/99999", headers=admin_headers)
        assert r.status_code == 404
