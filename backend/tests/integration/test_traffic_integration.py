# -*- coding: utf-8 -*-
"""
集成测试 4.4：流量统计 Redis → 后台同步 → MySQL 查询链路

验证：/traffic/batch 写入 Redis → 手动触发同步 → PageView/UserEvent 落库
→ 概览/每日/热门页面查询正确；重复同步不产生重复数据。
"""
import pytest

from app.models.traffic import PageView, UserEvent


@pytest.mark.integration
class TestTrafficSyncLink:
    """埋点 → Redis → 后台同步 → 查询 全链路"""

    async def _sync_once(self):
        from app.tasks.background_tracker import tracker_background_task

        await tracker_background_task._sync_tracking_data()

    async def test_batch_to_sync_to_query(
        self, client, mysql_session, admin_headers, clean_tracker_redis
    ):
        # 1. 上报埋点（免登录）
        batch = client.post(
            "/api/v1/traffic/batch",
            json={
                "page_views": [
                    {"path": "/home", "session_id": "s-1"},
                    {"path": "/pricing", "session_id": "s-2"},
                ],
                "user_events": [
                    {
                        "session_id": "s-1",
                        "page_path": "/home",
                        "event_type": "click",
                        "event_name": "start_create",
                    }
                ],
            },
        )
        assert batch.status_code == 200
        assert batch.json()["data"]["page_views"] == 2
        assert batch.json()["data"]["events"] == 1

        # 2. 手动触发后台同步
        await self._sync_once()

        # 3. 数据落库
        assert mysql_session.query(PageView).count() == 2
        assert mysql_session.query(UserEvent).count() == 1

        # 4. 查询接口口径正确
        overview = client.get("/api/v1/admin/traffic/overview", headers=admin_headers)
        assert overview.status_code == 200
        overview_data = overview.json()["data"]
        assert overview_data["week_pv"] >= 2
        assert overview_data["month_pv"] >= 2

        hot_pages = client.get("/api/v1/admin/traffic/hot-pages", headers=admin_headers)
        assert hot_pages.status_code == 200
        paths = [item["path"] for item in hot_pages.json()["data"]]
        assert "/home" in paths
        assert "/pricing" in paths

        daily = client.get("/api/v1/admin/traffic/daily", headers=admin_headers)
        assert daily.status_code == 200
        assert any(item["pv"] >= 1 for item in daily.json()["data"])

    async def test_sync_is_idempotent(
        self, client, mysql_session, admin_headers, clean_tracker_redis
    ):
        client.post(
            "/api/v1/traffic/batch",
            json={"page_views": [{"path": "/home", "session_id": "s-1"}]},
        )

        await self._sync_once()
        await self._sync_once()

        # Redis 记录被原子弹出，第二次同步不会重复插入
        assert mysql_session.query(PageView).count() == 1
