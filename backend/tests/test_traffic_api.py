# -*- coding: utf-8 -*-
"""
流量统计 API 测试
覆盖：埋点上报（mock Redis）、概览、每日统计、热门页面、点击事件
"""
from unittest.mock import MagicMock, patch

import pytest

from app.api.v1 import traffic as traffic_module


@pytest.fixture
def mock_tracker():
    """替换 tracker_service，避免依赖真实 Redis"""
    fake = MagicMock()
    fake.cache_page_view.return_value = "pv-1"
    fake.cache_user_events.return_value = 1
    fake.get_stats.return_value = {"page_views": 0, "updates": 0, "events": 0}
    with patch.object(traffic_module, "tracker_service", fake):
        yield fake


class TestBatchTrackAPI:
    """埋点批量上报接口测试"""

    def test_batch_track_no_auth_required(self, client, mock_tracker):
        payload = {
            "page_views": [{"path": "/home", "session_id": "s1"}],
            "page_view_updates": [
                {"page_view_id": "pv-1", "stay_duration": 30, "max_scroll_depth": 80}
            ],
            "user_events": [
                {"session_id": "s1", "page_path": "/home", "event_type": "click", "event_name": "btn"}
            ],
        }
        r = client.post("/api/v1/traffic/batch", json=payload)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["page_views"] == 1
        assert data["updates"] == 1
        assert data["events"] == 1
        assert mock_tracker.cache_page_view.call_count == 1
        assert mock_tracker.update_page_view.call_count == 1
        assert mock_tracker.cache_user_events.call_count == 1

    def test_batch_track_remaps_page_view_id(self, client, mock_tracker):
        payload = {
            "page_views": [{"id": "fe-1", "path": "/home", "session_id": "s1"}],
            "user_events": [
                {
                    "session_id": "s1",
                    "page_path": "/home",
                    "event_type": "click",
                    "page_view_id": "fe-1",
                }
            ],
        }
        client.post("/api/v1/traffic/batch", json=payload)
        events = mock_tracker.cache_user_events.call_args[0][0]
        assert events[0]["page_view_id"] == "pv-1"

    def test_batch_track_page_view_gets_ip(self, client, mock_tracker):
        payload = {"page_views": [{"path": "/home", "session_id": "s1"}]}
        client.post("/api/v1/traffic/batch", json=payload)
        pv = mock_tracker.cache_page_view.call_args[0][0]
        assert "ip_address" in pv
        assert "created_at" in pv


class TestTrafficStatsAPI:
    """流量统计查询接口测试"""

    def test_stats_requires_admin(self, client, auth_headers, mock_tracker):
        r = client.get("/api/v1/admin/traffic/stats", headers=auth_headers)
        assert r.status_code in (401, 403)

    def test_stats_as_admin(self, client, admin_headers, mock_tracker):
        r = client.get("/api/v1/admin/traffic/stats", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["data"] == {"page_views": 0, "updates": 0, "events": 0}

    def test_overview_requires_admin(self, client, auth_headers):
        r = client.get("/api/v1/admin/traffic/overview", headers=auth_headers)
        assert r.status_code in (401, 403)

    def test_overview_empty(self, client, admin_headers):
        r = client.get("/api/v1/admin/traffic/overview", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["today_pv"] == 0
        assert data["today_uv"] == 0
        assert data["week_pv"] == 0
        assert data["month_pv"] == 0
        assert data["bounce_rate"] == 0

    def test_daily_default_days(self, client, admin_headers):
        r = client.get("/api/v1/admin/traffic/daily", headers=admin_headers)
        assert r.status_code == 200
        # start = today - 30，循环含两端，共 31 天
        assert len(r.json()["data"]) == 31

    def test_daily_days_out_of_range(self, client, admin_headers):
        r = client.get("/api/v1/admin/traffic/daily", params={"days": 91}, headers=admin_headers)
        assert r.status_code == 422

    def test_hot_pages_empty(self, client, admin_headers):
        r = client.get("/api/v1/admin/traffic/hot-pages", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["data"] == []

    def test_click_events_empty(self, client, admin_headers):
        r = client.get("/api/v1/admin/traffic/click-events", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["data"] == []
