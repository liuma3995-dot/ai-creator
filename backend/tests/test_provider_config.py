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
