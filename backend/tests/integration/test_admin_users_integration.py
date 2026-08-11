# -*- coding: utf-8 -*-
"""
集成测试 4.5：用户管理全链路

验证：重置密码后登录行为、软删除后的可见性与登录、模型禁用生效。
"""
import pytest

from app.core.security import get_password_hash
from app.models.ai_model import AIModel
from app.models.user import User


@pytest.mark.integration
class TestAdminUserFullLink:
    """用户管理跨模块链路"""

    def _create_user(self, mysql_session, username, password):
        user = User(
            username=username,
            email=f"{username}@example.com",
            password_hash=get_password_hash(password),
        )
        mysql_session.add(user)
        mysql_session.commit()
        mysql_session.refresh(user)
        return user

    def test_reset_password_changes_login(
        self, client, mysql_session, admin_headers
    ):
        user = self._create_user(mysql_session, "resetit", "oldpass123")

        # 旧密码可登录
        old_login = client.post(
            "/api/v1/auth/login",
            json={"username": user.username, "password": "oldpass123"},
        )
        assert old_login.status_code == 200

        # 管理员重置
        reset = client.post(
            f"/api/v1/admin/users/{user.id}/reset-password",
            headers=admin_headers,
        )
        assert reset.status_code == 200

        # 旧密码失效、新密码可登录
        assert client.post(
            "/api/v1/auth/login",
            json={"username": user.username, "password": "oldpass123"},
        ).status_code == 401
        assert client.post(
            "/api/v1/auth/login",
            json={"username": user.username, "password": "123456"},
        ).status_code == 200

    def test_soft_delete_hides_user_and_blocks_login(
        self, client, mysql_session, admin_headers
    ):
        user = self._create_user(mysql_session, "delit", "delpass123")

        deleted = client.delete(f"/api/v1/admin/users/{user.id}", headers=admin_headers)
        assert deleted.status_code == 200

        mysql_session.expire_all()
        refreshed = mysql_session.query(User).filter(User.id == user.id).first()
        assert refreshed.deleted_at is not None

        # 列表不再出现
        listing = client.get(
            "/api/v1/admin/users/list",
            params={"keyword": "delit"},
            headers=admin_headers,
        )
        assert listing.json()["data"]["total"] == 0

        # 登录被拒
        assert client.post(
            "/api/v1/auth/login",
            json={"username": user.username, "password": "delpass123"},
        ).status_code == 403

    def test_disable_user_model(self, client, mysql_session, admin_headers):
        user = self._create_user(mysql_session, "modelit", "modelpass123")
        model = AIModel(
            user_id=user.id,
            name="测试模型",
            provider="openai",
            model_name="gpt-4",
            api_key="fake-key",
            is_active=True,
        )
        mysql_session.add(model)
        mysql_session.commit()
        mysql_session.refresh(model)

        toggled = client.post(
            f"/api/v1/admin/users/{user.id}/toggle-model-status",
            params={"model_id": model.id, "is_active": False},
            headers=admin_headers,
        )
        assert toggled.status_code == 200
        assert toggled.json()["data"]["is_active"] is False

        mysql_session.expire_all()
        refreshed = mysql_session.query(AIModel).filter(AIModel.id == model.id).first()
        assert refreshed.is_active is False

        detail = client.get(f"/api/v1/admin/users/{user.id}", headers=admin_headers)
        detail_models = detail.json()["data"]["ai_models"]
        assert all(m["is_active"] is False for m in detail_models if m["id"] == model.id)
