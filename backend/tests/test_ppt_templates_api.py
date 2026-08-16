# -*- coding: utf-8 -*-
"""
PPT 模板管理 API 测试（上传/列表/详情/缩略图/删除）
"""
import base64
import io
import json
import zipfile

import pytest


def _make_mini_pptx() -> bytes:
    """构造最小合法 PPTX（zip 结构）"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
</Types>""",
        )
        z.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>""",
        )
        z.writestr(
            "ppt/presentation.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"></p:presentation>""",
        )
    return buf.getvalue()


def _layout_json() -> str:
    return json.dumps({
        "themeColors": ["#FF0000"],
        "size": {"width": 960, "height": 540},
        "slides": [{"elements": []}, {"elements": []}],
    })


def _thumbnail_b64() -> str:
    png_1x1 = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    return "data:image/png;base64," + base64.b64encode(png_1x1).decode()


@pytest.fixture
def ppt_tmp_dir(monkeypatch, tmp_path):
    """把模板存储目录指向 pytest 临时目录，测试结束自动清理"""
    import app.api.v1.ppt_templates as ppt_api

    monkeypatch.setattr(ppt_api, "TEMPLATE_DIR", str(tmp_path))
    return tmp_path


def _upload_files(client, headers, name="测试模板", pptx_name="test.pptx",
                  layout="valid", thumbnail=None):
    """构造上传请求"""
    if layout == "valid":
        layout_content = _layout_json()
    elif layout == "invalid":
        layout_content = "{not valid json"
    else:
        layout_content = layout

    files = {
        "pptx_file": (pptx_name, io.BytesIO(_make_mini_pptx()),
                      "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        "layout_file": ("layout.json", io.BytesIO(layout_content.encode()), "application/json"),
    }
    data = {"name": name, "description": "测试描述"}
    if thumbnail is not None:
        data["thumbnail"] = thumbnail
    return client.post("/api/v1/ppt-templates/upload", files=files, data=data, headers=headers)


class TestPPTUpload:
    def test_upload_success_and_appears_in_list(
        self, client, auth_headers, ppt_tmp_dir
    ):
        """上传成功并出现在模板列表中"""
        resp = _upload_files(client, auth_headers, name="自定义模板")
        assert resp.status_code == 200
        template_id = resp.json()["data"]["id"]
        assert template_id is not None

        resp = client.get("/api/v1/ppt-templates", headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        found = [t for t in items if t["id"] == template_id]
        assert found
        assert found[0]["name"] == "自定义模板"
        assert found[0]["is_system"] is False

    def test_upload_detail_contains_layout(
        self, client, auth_headers, ppt_tmp_dir
    ):
        """详情接口能读回布局数据（2 页）"""
        resp = _upload_files(client, auth_headers)
        template_id = resp.json()["data"]["id"]

        resp = client.get(f"/api/v1/ppt-templates/{template_id}", headers=auth_headers)
        assert resp.status_code == 200
        detail = resp.json()["data"]
        assert detail["ppt_layout"]["slides"]
        assert len(detail["ppt_layout"]["slides"]) == 2

    def test_upload_thumbnail_served(self, client, auth_headers, ppt_tmp_dir):
        """上传缩略图后可通过缩略图接口访问"""
        resp = _upload_files(client, auth_headers, thumbnail=_thumbnail_b64())
        assert resp.status_code == 200
        thumb_url = resp.json()["data"]["thumbnail"]
        assert thumb_url and thumb_url.startswith("/api/v1/ppt-templates/thumbnails/")

        resp = client.get(thumb_url, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"

    def test_upload_rejects_non_pptx(self, client, auth_headers, ppt_tmp_dir):
        """非 .pptx 文件被拒绝"""
        resp = _upload_files(client, auth_headers, pptx_name="test.txt")
        assert resp.status_code == 400
        assert "pptx" in resp.json()["message"]

    def test_upload_rejects_invalid_layout(self, client, auth_headers, ppt_tmp_dir):
        """非法布局 JSON 被拒绝"""
        resp = _upload_files(client, auth_headers, layout="invalid")
        assert resp.status_code == 400
        assert "JSON" in resp.json()["message"]

    def test_upload_requires_auth(self, client, ppt_tmp_dir):
        """未登录上传返回 401"""
        resp = _upload_files(client, {})
        assert resp.status_code in (401, 403)


class TestPPTDelete:
    def test_delete_own_template(self, client, auth_headers, ppt_tmp_dir):
        """上传者可以删除自己的模板，删除后列表不再存在"""
        resp = _upload_files(client, auth_headers)
        template_id = resp.json()["data"]["id"]

        resp = client.delete(f"/api/v1/ppt-templates/{template_id}", headers=auth_headers)
        assert resp.status_code == 200


class TestPPTUseCount:
    def test_use_increments_count(
        self, client, auth_headers, ppt_tmp_dir
    ):
        """调用使用接口后 use_count 递增，列表/详情可见"""
        resp = _upload_files(client, auth_headers)
        template_id = resp.json()["data"]["id"]

        resp = client.post(f"/api/v1/ppt-templates/{template_id}/use", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["use_count"] == 1

        resp = client.post(f"/api/v1/ppt-templates/{template_id}/use", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["use_count"] == 2

        resp = client.get(f"/api/v1/ppt-templates/{template_id}", headers=auth_headers)
        assert resp.json()["data"]["use_count"] == 2

    def test_use_returns_404_for_missing_template(
        self, client, auth_headers, ppt_tmp_dir
    ):
        """不存在的模板返回 404"""
        resp = client.post("/api/v1/ppt-templates/999999/use", headers=auth_headers)
        assert resp.status_code == 404

        resp = client.get("/api/v1/ppt-templates", headers=auth_headers)
        items = resp.json()["data"]["items"]
        assert not [t for t in items if t["id"] == template_id]

    def test_delete_forbidden_for_other_user(
        self, client, db_session, auth_headers, test_user, ppt_tmp_dir
    ):
        """其他用户不能删除别人上传的模板"""
        from app.core.security import get_password_hash
        from app.models.user import User, UserStatus

        other = User(
            username="otheruser",
            email="other@example.com",
            password_hash=get_password_hash("otherpass123"),
            status=UserStatus.ACTIVE,
        )
        db_session.add(other)
        db_session.commit()

        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "otheruser", "password": "otherpass123"},
        )
        other_headers = {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}

        resp = _upload_files(client, auth_headers)
        template_id = resp.json()["data"]["id"]

        resp = client.delete(f"/api/v1/ppt-templates/{template_id}", headers=other_headers)
        assert resp.status_code == 404

        # 原上传者仍可删除
        resp = client.delete(f"/api/v1/ppt-templates/{template_id}", headers=auth_headers)
        assert resp.status_code == 200
