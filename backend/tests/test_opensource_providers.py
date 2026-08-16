# -*- coding: utf-8 -*-
"""
开源模型平台（HuggingFace / ModelScope）适配器协议回归测试
"""
import asyncio

from unittest.mock import AsyncMock


class _FakeResponse:
    def __init__(self, status_code, payload=None, content=b"", content_type="application/json"):
        self.status_code = status_code
        self._payload = payload
        self.content = content
        self.headers = {"content-type": content_type}
        self.text = (payload if isinstance(payload, str) else "") or ""

    def json(self):
        return self._payload


class _FakeAsyncClient:
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
        return self.post_responses.pop(0) if self.post_responses else _FakeResponse(200, {})

    async def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return self.get_responses.pop(0) if self.get_responses else _FakeResponse(200, {})


def _install_fake_httpx(monkeypatch, **kwargs):
    import httpx

    fake = _FakeAsyncClient(**kwargs)
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: fake)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    return fake


class TestOpenSourceProviderConfig:
    def test_huggingface_uses_router_for_chat(self):
        """HuggingFace 聊天走官方 AI Inference Router（OpenAI 兼容）"""
        from app.services.langchain.config import get_provider_config

        cfg = get_provider_config("huggingface")
        assert cfg.base_url == "https://router.huggingface.co/v1"
        assert "Qwen/Qwen3-32B" in cfg.models["text"]

    def test_modelscope_openai_compatible_endpoint(self):
        """ModelScope 保持 OpenAI 兼容端点，模型清单为 2026 主流"""
        from app.services.langchain.config import get_provider_config

        cfg = get_provider_config("modelscope")
        assert cfg.base_url == "https://api-inference.modelscope.cn/v1"
        assert "Qwen/Qwen3-32B" in cfg.models["text"]
        assert "Tongyi-MAI/Z-Image-Turbo" in cfg.models["image"]

    def test_opensource_chat_factory_creates_chat_openai(self):
        """HuggingFace / ModelScope 聊天工厂创建 ChatOpenAI 实例"""
        from langchain_openai import ChatOpenAI
        from app.services.langchain.chat.factory import LangChainChatFactory

        for provider in ("huggingface", "modelscope"):
            model = LangChainChatFactory.create(
                provider=provider,
                model_name="Qwen/Qwen3-32B",
                api_key="hf-test",
            )
            assert isinstance(model, ChatOpenAI), provider


class TestHuggingFaceImageProvider:
    def test_generate_uses_inference_api(self, monkeypatch):
        """HF 图片走专用 Inference API（router /v1 仅支持 chat）"""
        from app.services.langchain.image.providers.huggingface import HuggingFaceImageGenerator

        fake = _install_fake_httpx(
            monkeypatch,
            post_responses=[
                _FakeResponse(200, content=b"\x89PNG-fake", content_type="image/png")
            ],
        )
        generator = HuggingFaceImageGenerator(
            api_key="hf-test", default_model="stabilityai/stable-diffusion-xl-base-1.0"
        )

        result = None

        async def run():
            nonlocal result
            result = await generator.generate(prompt="一只猫", size="1024x1024")

        asyncio.run(run())

        assert result.success
        assert result.images[0].startswith("data:image/png;base64,")
        url, kwargs = fake.post_calls[0]
        assert url.endswith("/models/stabilityai/stable-diffusion-xl-base-1.0")
        assert kwargs["headers"]["Authorization"] == "Bearer hf-test"
        assert kwargs["json"]["inputs"] == "一只猫"


class TestModelScopeImageProvider:
    def test_generate_uses_async_task_mode(self, monkeypatch):
        """ModelScope 图片走 OpenAI 兼容异步任务：提交 + 轮询"""
        from app.services.langchain.image.providers.modelscope import ModelScopeImageGenerator

        fake = _install_fake_httpx(
            monkeypatch,
            post_responses=[
                _FakeResponse(200, {"output": {"task_id": "task-1"}})
            ],
            get_responses=[
                _FakeResponse(
                    200,
                    {
                        "output": {
                            "task_status": "SUCCEED",
                            "results": [{"url": "https://cdn.modelscope.cn/img.png"}],
                        }
                    },
                )
            ],
        )
        generator = ModelScopeImageGenerator(
            api_key="ms-test", default_model="Tongyi-MAI/Z-Image-Turbo"
        )

        result = None

        async def run():
            nonlocal result
            result = await generator.generate(prompt="山水画", size="1024x1024")

        asyncio.run(run())

        assert result.success
        assert result.images == ["https://cdn.modelscope.cn/img.png"]
        post_url, post_kwargs = fake.post_calls[0]
        assert post_url.endswith("/images/generations")
        assert post_kwargs["headers"]["X-ModelScope-Async-Mode"] == "true"
        get_url, _ = fake.get_calls[0]
        assert get_url.endswith("/tasks/task-1")
