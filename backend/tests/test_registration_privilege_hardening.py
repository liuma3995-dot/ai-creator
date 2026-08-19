# -*- coding: utf-8 -*-
"""T5 注册与提权防护显式化回归测试"""


class TestRegisterRoleHardening:
    def test_register_with_role_field_rejected(self, client):
        r = client.post("/api/v1/auth/register", json={
            "username": "eviluser",
            "email": "evil@example.com",
            "password": "password123",
            "role": "admin",
        })
        assert r.status_code == 422

    def test_normal_register_creates_normal_user(self, client, db_session):
        r = client.post("/api/v1/auth/register", json={
            "username": "normaluser",
            "email": "normal@example.com",
            "password": "password123",
        })
        assert r.status_code == 200
        assert r.json()["data"]["role"] == "user"


class TestProfileUpdateRoleHardening:
    def test_update_profile_with_role_field_rejected(self, client, auth_headers):
        r = client.put(
            "/api/v1/auth/me",
            headers=auth_headers,
            json={"nickname": "新昵称", "role": "admin"},
        )
        assert r.status_code == 422

    def test_update_profile_allows_whitelist_fields(self, client, auth_headers):
        r = client.put(
            "/api/v1/auth/me",
            headers=auth_headers,
            json={"nickname": "合法昵称"},
        )
        assert r.status_code == 200
        assert r.json()["data"]["nickname"] == "合法昵称"
