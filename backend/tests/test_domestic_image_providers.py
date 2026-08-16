# -*- coding: utf-8 -*-
"""
国内图片生成适配器协议回归测试

覆盖：通义/百度/混元 OpenAI 兼容图片接口、通义 wanx 旧版异步任务接口。
"""
import asyncio

import pytest
from unittest.mock import AsyncMock


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = ""

    def json(self):
        return self._payload


class _FakeAsyncClient:
    """记录请求的假 httpx 客户端"""

    def __init__(self, post_responses=None, get_responses=None):
        self.post_responses = list(post_responses or [])
        self.get_responses = list(get_responses or [])
        self.post_calls = []
        self.get_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        if self.post_responses:
            return _FakeResponse(200, self.post_responses.pop(0))
        return _FakeResponse(200, {"data": []})

    async def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        if self.get_responses:
            return _FakeResponse(200, self.get_responses.pop(0))
        return _FakeResponse(200, {})


def _install_fake_httpx(monkeypatch, **kwargs):
    import httpx

    fake = _FakeAsyncClient(**kwargs)
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: fake)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    return fake


class TestOpenAICompatibleImageProviders:
    """通义/百度/混元 OpenAI 兼容图片接口"""

    @pytest.mark.parametrize(
        "provider,module,base_url,model",
        [
            ("qwen", "app.services.langchain.image.providers.qwen", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-image-3.0"),
            ("baidu", "app.services.langchain.image.providers.baidu", "https://qianfan.baidubce.com/v2", "ernie-4.5-turbo-128k"),
            ("hunyuan", "app.services.langchain.image.providers.hunyuan", "https://api.hunyuan.cloud.tencent.com/v1", "hunyuan-image-latest"),
        ],
    )
    def test_generate_uses_openai_compatible_endpoint(
        self, monkeypatch, provider, module, base_url, model
    ):
        """POST {base}/images/generations，OpenAI 格式请求体，解析 url/b64_json 响应"""
        import importlib

        fake = _install_fake_httpx(
            monkeypatch,
            post_responses=[
                {
                    "data": [
                        {"url": "https://cdn.example.com/gen.png"},
                        {"b64_json": "ZmFrZQ=="},
                    ]
                }
            ],
        )
        class_name = {
            "qwen": "QwenImageGenerator",
            "baidu": "BaiduImageGenerator",
            "hunyuan": "HunyuanImageGenerator",
        }[provider]
        generator_cls = getattr(importlib.import_module(module), class_name)
        generator = generator_cls(api_key="sk-test", default_model=model)

        result = None

        async def run():
            nonlocal result
            result = await generator.generate(
                prompt="一只猫", size="1024x1024", n=2
            )

        asyncio.run(run())

        assert result.success
        assert result.images == [
            "https://cdn.example.com/gen.png",
            "ZmFrZQ==",
        ]
        url, kwargs = fake.post_calls[0]
        assert url == f"{base_url}/images/generations"
        payload = kwargs["json"]
        assert payload["model"] == model
        assert payload["prompt"] == "一只猫"
        assert payload["size"] == "1024x1024"
        assert payload["n"] == 2

    def test_qwen_wanx_uses_legacy_async_task(self, monkeypatch):
        """wanx 系列走 DashScope 旧版异步任务接口（官方 legacy 仍维护）"""
        from app.services.langchain.image.providers.qwen import QwenImageGenerator

        fake = _install_fake_httpx(
            monkeypatch,
            post_responses=[{"output": {"task_id": "task-1"}}],
            get_responses=[
                {
                    "output": {
                        "task_status": "SUCCEEDED",
                        "results": [{"url": "https://cdn.example.com/wanx.png"}],
                    }
                }
            ],
        )
        generator = QwenImageGenerator(
            api_key="sk-test", default_model="wanx2.1-t2i-turbo"
        )

        result = None

        async def run():
            nonlocal result
            result = await generator.generate(prompt="山水", size="1024x1024")

        asyncio.run(run())

        assert result.success
        assert result.images == ["https://cdn.example.com/wanx.png"]
        post_url, post_kwargs = fake.post_calls[0]
        assert "services/aigc/text2image/image-synthesis" in post_url
        assert post_kwargs["headers"]["X-DashScope-Async"] == "enable"
        get_url, _ = fake.get_calls[0]
        assert get_url.endswith("/tasks/task-1")
