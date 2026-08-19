# -*- coding: utf-8 -*-
"""
管理员模型调用监控 API 测试
覆盖：日志列表、详情、统计概览
"""
from app.models.model_usage_log import AIModelUsageLog


def _make_log(db, **kwargs):
    defaults = dict(
        user_id=1,
        ai_model_id=1,
        provider="openai",
        model_name="gpt-4",
        request_type="chat",
        status="success",
        total_tokens=100,
        prompt_tokens=50,
        completion_tokens=50,
        tool="writing",
    )
    defaults.update(kwargs)
    log = AIModelUsageLog(**defaults)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


class TestUsageLogsAPI:
    """调用日志列表接口测试"""

    def test_logs_requires_admin(self, client, auth_headers):
        r = client.get("/api/v1/admin/model-usage/logs", headers=auth_headers)
        assert r.status_code in (401, 403)

    def test_logs_anonymous(self, client):
        r = client.get("/api/v1/admin/model-usage/logs")
        assert r.status_code in (401, 403)

    def test_logs_as_admin_empty(self, client, admin_headers):
        r = client.get("/api/v1/admin/model-usage/logs", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["data"]["items"] == []

    def test_logs_filter_by_provider(self, client, admin_headers, db_session):
        _make_log(db_session, provider="openai")
        _make_log(db_session, provider="anthropic")
        r = client.get(
            "/api/v1/admin/model-usage/logs",
            params={"provider": "openai"},
            headers=admin_headers,
        )
        assert r.json()["data"]["total"] == 1

    def test_logs_filter_by_status(self, client, admin_headers, db_session):
        _make_log(db_session, status="success")
        _make_log(db_session, status="failed")
        r = client.get(
            "/api/v1/admin/model-usage/logs",
            params={"status": "failed"},
            headers=admin_headers,
        )
        assert r.json()["data"]["total"] == 1

    def test_logs_pagination(self, client, admin_headers, db_session):
        for i in range(3):
            _make_log(db_session, model_name=f"model-{i}")
        r = client.get(
            "/api/v1/admin/model-usage/logs",
            params={"page": 1, "page_size": 2},
            headers=admin_headers,
        )
        data = r.json()["data"]
        assert data["total"] == 3
        assert len(data["items"]) == 2


class TestUsageLogDetailAPI:
    """调用日志详情接口测试"""

    def test_log_detail_not_found(self, client, admin_headers):
        r = client.get("/api/v1/admin/model-usage/logs/99999", headers=admin_headers)
        assert r.status_code == 404

    def test_log_detail(self, client, admin_headers, db_session):
        log = _make_log(db_session)
        r = client.get(f"/api/v1/admin/model-usage/logs/{log.id}", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["provider"] == "openai"
        assert data["total_tokens"] == 100


class TestUsageStatsAPI:
    """调用统计概览接口测试"""

    def test_stats_empty(self, client, admin_headers):
        r = client.get("/api/v1/admin/model-usage/stats", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["overview"]["total_calls"] == 0
        assert data["overview"]["success_rate"] == 0
        assert data["by_provider"] == []
        assert data["by_tool"] == []

    def test_stats_with_logs(self, client, admin_headers, db_session):
        _make_log(db_session, provider="openai", total_tokens=100)
        _make_log(db_session, provider="openai", total_tokens=50, status="failed")
        r = client.get("/api/v1/admin/model-usage/stats", headers=admin_headers)
        overview = r.json()["data"]["overview"]
        assert overview["total_calls"] == 2
        assert overview["failed_calls"] == 1
        assert overview["total_tokens"] == 150
