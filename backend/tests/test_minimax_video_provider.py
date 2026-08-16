# -*- coding: utf-8 -*-
"""
MiniMax 视频生成适配器单元测试（2026 新平台协议）
"""
import asyncio
import json

import pytest
from unittest.mock import AsyncMock

from app.services.langchain.video.providers.minimax import MiniMaxVideoGenerator


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload, ensure_ascii=False)

    def json(self):
        return self._payload


class _FakeAsyncClient:
    """按调用顺序/URL 返回预设响应的假 httpx 客户端"""

    def __init__(self, post_payload=None, query_payloads=None, file_payload=None):
        self.post_payload = post_payload
        self.query_payloads = query_payloads or []
        self.file_payload = file_payload
        self.post_calls = []
        self.get_calls = []
        self._query_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return _FakeResponse(200, self.post_payload)

    async def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        if "/query/video_generation" in url:
            # 首次返回列表第一个，之后保持最后一个响应（稳定状态，避免空列表）
            idx = min(self._query_count, len(self.query_payloads) - 1)
            self._query_count += 1
            return _FakeResponse(200, self.query_payloads[idx])
        if "/files/retrieve" in url:
            return _FakeResponse(200, self.file_payload)
        return _FakeResponse(404, {})


def _install_fake_client(monkeypatch, **kwargs):
    """替换 httpx.AsyncClient 并禁止真实 sleep，保证测试快速"""
    import httpx

    fake = _FakeAsyncClient(**kwargs)
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda *a, **k: fake
    )
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    return fake


def _make_generator():
    return MiniMaxVideoGenerator(
        api_key="sk-test",
        api_base="https://api.minimaxi.com/v1",
        default_model="MiniMax-Hailuo-2.3",
    )


class TestMiniMaxVideoGenerator:
    async def test_text_to_video_success_uses_new_endpoints(self, monkeypatch):
        """文生视频：走新端点、无 GroupId，轮询到 Success 后返回下载地址"""
        fake = _install_fake_client(
            monkeypatch,
            post_payload={"task_id": "task-1", "base_resp": {"status_code": 0}},
            query_payloads=[
                {"task_id": "task-1", "status": "Processing"},
                {
                    "task_id": "task-1",
                    "status": "Success",
                    "file_id": "file-1",
                    "base_resp": {"status_code": 0},
                },
            ],
            file_payload={"download_url": "https://cdn.example.com/video.mp4"},
        )
        generator = _make_generator()

        result = await generator.generate(
            prompt="蓝天白云", duration=6, resolution="768P"
        )

        assert result.success
        assert result.videos == ["https://cdn.example.com/video.mp4"]
        assert result.metadata.get("file_id") == "file-1"
        # 提交任务走新端点，不含 GroupId
        post_url, post_kwargs = fake.post_calls[0]
        assert post_url == "https://api.minimaxi.com/v1/video_generation"
        assert "GroupId" not in post_url
        payload = post_kwargs["json"]
        assert payload["model"] == "MiniMax-Hailuo-2.3"
        assert payload["duration"] == 6
        assert payload["resolution"] == "768P"
        assert "first_frame_image" not in payload
        assert "watermark" not in payload  # 回归：watermark 字段会导致 invalid params
        # 查询/取文件均走新端点
        get_urls = [u for u, _ in fake.get_calls]
        assert any("query/video_generation" in u for u in get_urls)
        assert any("files/retrieve" in u for u in get_urls)

    async def test_image_to_video_passes_first_frame_image(self, monkeypatch):
        """图生视频：请求体必须携带 first_frame_image"""
        fake = _install_fake_client(
            monkeypatch,
            post_payload={"task_id": "task-2", "base_resp": {"status_code": 0}},
            query_payloads=[
                {
                    "task_id": "task-2",
                    "status": "Success",
                    "file_id": "file-2",
                    "base_resp": {"status_code": 0},
                }
            ],
            file_payload={"download_url": "https://cdn.example.com/i2v.mp4"},
        )
        generator = _make_generator()

        result = await generator.generate(
            prompt="让画面动起来",
            image_url="data:image/jpeg;base64,ZmFrZQ==",
            duration=6,
            resolution="768P",
        )

        assert result.success
        payload = fake.post_calls[0][1]["json"]
        assert payload["first_frame_image"] == "data:image/jpeg;base64,ZmFrZQ=="

    async def test_duration_and_resolution_normalization(self, monkeypatch):
        """时长/分辨率收敛到官方允许值"""
        fake = _install_fake_client(
            monkeypatch,
            post_payload={"task_id": "task-3", "base_resp": {"status_code": 0}},
            query_payloads=[
                {
                    "task_id": "task-3",
                    "status": "Success",
                    "file_id": "file-3",
                    "base_resp": {"status_code": 0},
                }
            ],
            file_payload={"download_url": "https://cdn.example.com/n.mp4"},
        )
        generator = _make_generator()

        await generator.generate(prompt="p", duration=15, resolution="1080p")
        payload = fake.post_calls[0][1]["json"]
        assert payload["duration"] == 10
        assert payload["resolution"] == "1080P"

        await generator.generate(prompt="p", duration=5, resolution="unknown")
        payload = fake.post_calls[1][1]["json"]
        assert payload["duration"] == 6
        assert payload["resolution"] == "768P"

    async def test_generate_fail_when_task_failed(self, monkeypatch):
        """任务失败时返回 fail 结果"""
        _install_fake_client(
            monkeypatch,
            post_payload={"task_id": "task-4", "base_resp": {"status_code": 0}},
            query_payloads=[
                {
                    "task_id": "task-4",
                    "status": "Fail",
                    "base_resp": {"status_code": 0},
                }
            ],
            file_payload={},
        )
        generator = _make_generator()

        result = await generator.generate(prompt="p")

        assert not result.success
        assert result.error == "视频生成失败"
