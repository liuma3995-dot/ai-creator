# -*- coding: utf-8 -*-
"""
供应商 API 配置回归测试

覆盖：MiniMax 新版 OpenAI 兼容协议、其他 OpenAI 兼容厂商的适配器切换。
"""


class TestProviderConfig:
    """供应商配置回归测试"""

    def test_minimax_uses_new_openai_compatible_endpoint(self):
        """MiniMax 必须使用新版域名与 OpenAI 兼容协议（回归：旧域名+旧适配器导致 'choices' 报错）"""
        from app.services.langchain.config import get_provider_config

        cfg = get_provider_config("minimax")
        assert cfg is not None
        assert cfg.base_url == "https://api.minimaxi.com/v1"
        assert cfg.langchain_class == "langchain_openai.ChatOpenAI"
        assert "MiniMax-M3" in cfg.models["text"]

    def test_minimax_chat_model_is_openai_compatible(self):
        """MiniMax 创建的 Chat Model 必须是 ChatOpenAI，且模型名正确"""
        from langchain_openai import ChatOpenAI
        from app.services.langchain.chat.factory import LangChainChatFactory

        model = LangChainChatFactory.create(
            provider="minimax",
            model_name="MiniMax-M3",
            api_key="sk-test",
        )
        assert isinstance(model, ChatOpenAI)
        assert model.model_name == "MiniMax-M3"

    def test_openai_compatible_providers_use_chat_openai(self):
        """Moonshot / 百川 / DeepSeek 都走 OpenAI 兼容 ChatOpenAI 适配器"""
        from langchain_openai import ChatOpenAI
        from app.services.langchain.chat.factory import LangChainChatFactory
        from app.services.langchain.config import get_provider_config

        for provider in ("moonshot", "baichuan", "deepseek"):
            cfg = get_provider_config(provider)
            assert cfg.langchain_class == "langchain_openai.ChatOpenAI"
            model = LangChainChatFactory.create(
                provider=provider,
                model_name=cfg.models["text"][0],
                api_key="sk-test",
            )
            assert isinstance(model, ChatOpenAI), provider

    def test_minimax_models_include_m3(self):
        """MiniMax 文本模型清单必须包含 MiniMax-M3"""
        from app.services.langchain.config import get_provider_config

        cfg = get_provider_config("minimax")
        assert "MiniMax-M3" in cfg.models["text"]

    def test_domestic_openai_compatible_providers(self):
        """国内 5 家厂商（智谱/通义/百度/混元/讯飞）必须切到 OpenAI 兼容新协议"""
        from app.services.langchain.config import AuthType, get_provider_config

        expected = {
            "zhipu": "https://open.bigmodel.cn/api/paas/v4",
            "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "baidu": "https://qianfan.baidubce.com/v2",
            "hunyuan": "https://api.hunyuan.cloud.tencent.com/v1",
            "spark": "https://spark-api-open.xf-yun.com/v1",
        }
        for provider, base_url in expected.items():
            cfg = get_provider_config(provider)
            assert cfg is not None, provider
            assert cfg.langchain_class == "langchain_openai.ChatOpenAI", provider
            assert cfg.base_url == base_url, provider
            assert cfg.auth_type == AuthType.API_KEY, provider

    def test_domestic_openai_compatible_factory_creates_chat_openai(self):
        """国内 5 家厂商通过工厂创建的都是 ChatOpenAI 实例"""
        from langchain_openai import ChatOpenAI
        from app.services.langchain.chat.factory import LangChainChatFactory
        from app.services.langchain.config import get_provider_config

        for provider in ("zhipu", "qwen", "baidu", "hunyuan", "spark"):
            cfg = get_provider_config(provider)
            model = LangChainChatFactory.create(
                provider=provider,
                model_name=cfg.models["text"][0],
                api_key="sk-test",
            )
            assert isinstance(model, ChatOpenAI), provider

    def test_2026_model_lists_updated(self):
        """2026 模型清单：DeepSeek V4、Kimi K3、百川 M 系列、豆包 Seed 系列"""
        from app.services.langchain.config import get_provider_config

        assert get_provider_config("deepseek").models["text"] == [
            "deepseek-v4-flash",
            "deepseek-v4-pro",
        ]
        assert "kimi-k3" in get_provider_config("moonshot").models["text"]
        assert "Baichuan-M3" in get_provider_config("baichuan").models["text"]
        doubao = get_provider_config("doubao")
        assert "doubao-seed-2.0-mini" in doubao.models["text"]
        assert "doubao-seedream-5.0-pro" in doubao.models["image"]
        assert "doubao-seedance-2.0" in doubao.models["video"]

    def test_international_model_lists_2026(self):
        """2026 国外模型清单：OpenAI GPT-5 系列、Claude Opus 4.7、Gemini 3、Veo 3.1"""
        from app.services.langchain.config import get_provider_config

        openai = get_provider_config("openai")
        assert "gpt-5.4" in openai.models["text"]
        assert "gpt-image-1" in openai.models["image"]
        assert "dall-e-3" not in openai.models["image"]

        anthropic = get_provider_config("anthropic")
        assert "claude-opus-4-7" in anthropic.models["text"]

        google = get_provider_config("google")
        assert "gemini-3-pro" in google.models["text"]
        assert "imagen-4.0-generate-001" in google.models["image"]
        assert "veo-3.1" in google.models["video"]

        stability = get_provider_config("stability")
        assert "stable-image-core" in stability.models["image"]

        replicate = get_provider_config("replicate")
        assert any("llama-4" in m for m in replicate.models["text"])
        assert "black-forest-labs/flux-1.1-pro" in replicate.models["image"]

    def test_international_chat_factory_creates_models(self):
        """OpenAI/Anthropic/Google 通过工厂创建对应 LangChain 模型实例"""
        from app.services.langchain.chat.factory import LangChainChatFactory
        from app.services.langchain.config import get_provider_config

        expected_type = {
            "openai": "ChatOpenAI",
            "anthropic": "ChatAnthropic",
            "google": "ChatGoogleGenerativeAI",
        }
        for provider, class_name in expected_type.items():
            cfg = get_provider_config(provider)
            model = LangChainChatFactory.create(
                provider=provider,
                model_name=cfg.models["text"][0],
                api_key="sk-test",
            )
            assert model.__class__.__name__ == class_name, provider

    def test_stability_endpoint_model_mapping(self):
        """Stability 模型名到端点路径的映射"""
        from app.services.langchain.image.providers.stability import StabilityImageGenerator

        assert StabilityImageGenerator._resolve_endpoint_model("stable-image-core") == "core"
        assert StabilityImageGenerator._resolve_endpoint_model("stable-image-ultra") == "ultra"
        assert StabilityImageGenerator._resolve_endpoint_model("stable-diffusion-3.5-large") == "sd3.5-large"
        # 未知模型回退到 core
        assert StabilityImageGenerator._resolve_endpoint_model("unknown") == "core"
