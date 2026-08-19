"""
WritingService 单元测试
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.writing_service import WritingService
from app.services.ai.openai_service import OpenAIService
from app.services.ai.anthropic_service import AnthropicService
from types import SimpleNamespace


class _FakeChatService:
    """模拟 LangChain 服务，捕获提示词"""

    def __init__(self):
        self.captured = {}

    async def chat(self, message, **kwargs):
        self.captured["message"] = message
        return SimpleNamespace(content="生成内容")


class TestGenerateContentSupplement:
    """测试生成/重新生成时补充说明进入提示词"""

    async def test_generate_content_appends_supplement_with_priority(self, db_session):
        ai_model = Mock()
        ai_model.provider = "openai"
        ai_model.api_key = "test-key"
        ai_model.model_name = "gpt-4"
        ai_model.base_url = None
        ai_model.id = 1

        fake = _FakeChatService()
        with patch.object(WritingService, "get_langchain_service", return_value=fake):
            result = await WritingService.generate_content(
                db=db_session,
                tool_type="xiaohongshu_note",
                user_input={
                    "topic": "AI主题",
                    "keywords": "AI,科技",
                    "note_type": "热点",
                    "additional_description": "字数要求：50字",
                },
                ai_model=ai_model,
            )

        prompt = fake.captured["message"]
        assert result == "生成内容"
        assert "【用户特殊要求】" in prompt
        assert prompt.startswith("请根据以下信息创作内容")
        assert "字数要求：50字" in prompt
        assert "最高优先级" in prompt
        # 补充说明指定字数后应改用极简模式，不再携带模板结构要求
        assert "小红书爆款笔记创作专家" not in prompt

    async def test_generate_content_general_supplement_keeps_template(self, db_session):
        """补充说明未指定字数时，保留工具模板并注入最高优先级要求"""
        ai_model = Mock()
        ai_model.provider = "openai"
        ai_model.api_key = "test-key"
        ai_model.model_name = "gpt-4"
        ai_model.base_url = None
        ai_model.id = 1

        fake = _FakeChatService()
        with patch.object(WritingService, "get_langchain_service", return_value=fake):
            await WritingService.generate_content(
                db=db_session,
                tool_type="xiaohongshu_note",
                user_input={
                    "topic": "AI主题",
                    "keywords": "AI,科技",
                    "note_type": "热点",
                    "additional_description": "语言要口语化、有感染力",
                },
                ai_model=ai_model,
            )

        prompt = fake.captured["message"]
        assert "语言要口语化、有感染力" in prompt
        assert "小红书爆款笔记创作专家" in prompt
        assert "最高优先级" in prompt


class TestGetLangChainService:
    """测试 get_langchain_service（现行统一服务入口）"""

    def _make_model(self, provider="openai", api_key="test-api-key",
                    base_url="https://api.test.com/v1", model_name="gpt-4-turbo"):
        ai_model = Mock()
        ai_model.provider = provider
        ai_model.api_key = api_key
        ai_model.base_url = base_url
        ai_model.model_name = model_name
        ai_model.id = 1
        return ai_model

    def test_get_openai_service(self):
        """测试获取 OpenAI 服务"""
        from app.services.langchain.service import LangChainChatFactory

        with patch.object(LangChainChatFactory, "create", return_value=Mock()):
            service = WritingService.get_langchain_service(self._make_model())

        assert service.provider == "openai"
        assert service.api_key == "test-api-key"
        assert service.api_base == "https://api.test.com/v1"
        assert service.model == "gpt-4-turbo"

    def test_get_openai_service_with_defaults(self):
        """测试 OpenAI 服务使用默认模型名"""
        from app.services.langchain.service import LangChainChatFactory

        ai_model = self._make_model(base_url=None, model_name=None)
        with patch.object(LangChainChatFactory, "create", return_value=Mock()):
            service = WritingService.get_langchain_service(ai_model)

        assert service.provider == "openai"
        assert service.api_base is None
        assert service.model == "gpt-4"

    def test_get_anthropic_service(self):
        """测试获取 Anthropic 服务"""
        from app.services.langchain.service import LangChainChatFactory

        ai_model = self._make_model(
            provider="anthropic",
            api_key="test-anthropic-key",
            base_url=None,
            model_name="claude-3-sonnet-20240229",
        )
        with patch.object(LangChainChatFactory, "create", return_value=Mock()):
            service = WritingService.get_langchain_service(ai_model)

        assert service.provider == "anthropic"
        assert service.api_key == "test-anthropic-key"
        assert service.model == "claude-3-sonnet-20240229"

    def test_get_anthropic_service_with_defaults(self):
        """测试 Anthropic 服务模型名缺省回退（当前实现统一回退 gpt-4）"""
        from app.services.langchain.service import LangChainChatFactory

        ai_model = self._make_model(
            provider="anthropic",
            api_key="test-anthropic-key",
            base_url=None,
            model_name=None,
        )
        with patch.object(LangChainChatFactory, "create", return_value=Mock()):
            service = WritingService.get_langchain_service(ai_model)

        assert service.model == "gpt-4"

    def test_unsupported_provider(self):
        """测试不支持的厂商"""
        ai_model = self._make_model(provider="unsupported")

        with pytest.raises(ValueError) as exc_info:
            WritingService.get_langchain_service(ai_model)

        assert "不支持的厂商" in str(exc_info.value)


class TestToolDefaults:
    """测试工具默认参数"""
    
    def test_wechat_article_defaults(self):
        """测试微信公众号文章默认参数"""
        defaults = WritingService.TOOL_DEFAULTS.get("wechat_article", {})
        assert "target_audience" in defaults
        assert "style" in defaults
    
    def test_xiaohongshu_defaults(self):
        """测试小红书笔记默认参数"""
        defaults = WritingService.TOOL_DEFAULTS.get("xiaohongshu_note", {})
        assert "note_type" in defaults


class TestGenerateContent:
    """测试 generate_content 方法"""
    
    @pytest.mark.asyncio
    async def test_generate_content_with_defaults(self):
        """测试使用默认参数生成内容"""
        ai_model = Mock()
        ai_model.provider = "openai"
        ai_model.api_key = "test-key"
        ai_model.base_url = "https://api.openai.com/v1"
        ai_model.model_name = "gpt-4"

        fake = _FakeChatService()
        with patch.object(WritingService, "get_langchain_service", return_value=fake):
            result = await WritingService.generate_content(
                db=Mock(),
                tool_type="wechat_article",
                user_input={"topic": "AI技术", "keywords": "人工智能"},
                ai_model=ai_model,
            )

        prompt = fake.captured["message"]
        assert result == "生成内容"
        assert "AI技术" in prompt
        assert "人工智能" in prompt
        assert "普通读者" in prompt  # 默认的 target_audience
    
    @pytest.mark.asyncio
    async def test_generate_content_override_defaults(self):
        """测试用户输入覆盖默认参数"""
        ai_model = Mock()
        ai_model.provider = "openai"
        ai_model.api_key = "test-key"
        ai_model.base_url = "https://api.openai.com/v1"
        ai_model.model_name = "gpt-4"

        fake = _FakeChatService()
        with patch.object(WritingService, "get_langchain_service", return_value=fake):
            await WritingService.generate_content(
                db=Mock(),
                tool_type="wechat_article",
                user_input={
                    "topic": "AI技术",
                    "keywords": "人工智能",
                    "target_audience": "技术人员",  # 覆盖默认值
                    "style": "技术文",
                },
                ai_model=ai_model,
            )

        prompt = fake.captured["message"]
        assert "技术人员" in prompt  # 应该使用用户指定的值
        assert "普通读者" not in prompt
    
    @pytest.mark.asyncio
    async def test_generate_content_unsupported_tool(self):
        """测试不支持的工具类型"""
        ai_model = Mock()
        db = Mock()
        
        with pytest.raises(ValueError) as exc_info:
            await WritingService.generate_content(
                db=db,
                tool_type="unsupported_tool",
                user_input={},
                ai_model=ai_model,
            )
        
        assert "不支持的写作工具类型" in str(exc_info.value)


class TestPromptTemplates:
    """测试提示词模板"""
    
    def test_all_templates_have_defaults(self):
        """测试所有模板都有对应的默认参数"""
        for tool_type in WritingService.TOOL_PROMPTS.keys():
            template = WritingService.TOOL_PROMPTS[tool_type]
            defaults = WritingService.TOOL_DEFAULTS.get(tool_type, {})
            
            # 提取模板中的占位符
            import re
            placeholders = re.findall(r'\{(\w+)\}', template)
            
            # 检查每个占位符是否有默认值或是常见的用户输入字段
            user_input_fields = {'topic', 'keywords', 'content', 'title', 'original_content'}
            for placeholder in placeholders:
                if placeholder not in user_input_fields:
                    assert placeholder in defaults, \
                        f"工具 {tool_type} 的占位符 {placeholder} 没有默认值"


class TestToolTypeAliasAndCreationType:
    """内容改写/新闻稿等工具类型别名与 creation_type 映射"""

    def _make_model(self):
        ai_model = Mock()
        ai_model.provider = "openai"
        ai_model.api_key = "test-key"
        ai_model.model_name = "gpt-4"
        ai_model.base_url = None
        ai_model.id = 1
        return ai_model

    @pytest.mark.asyncio
    async def test_content_rewrite_uses_rewrite_template(self, db_session):
        """content_rewrite 别名归一化为 rewrite 模板，不再报不支持"""
        fake = _FakeChatService()
        ai_model = self._make_model()
        with patch.object(WritingService, "get_langchain_service", return_value=fake):
            result = await WritingService.generate_content(
                db=db_session,
                tool_type="content_rewrite",
                user_input={
                    "original_text": "原文内容",
                    "rewrite_type": "改写",
                    "target_style": "正式书面",
                },
                ai_model=ai_model,
            )
        prompt = fake.captured["message"]
        assert result == "生成内容"
        assert "内容改写专家" in prompt
        assert "原文内容" in prompt

    @pytest.mark.asyncio
    async def test_press_release_uses_news_article_template(self, db_session):
        """press_release 别名归一化为 news_article 模板"""
        fake = _FakeChatService()
        ai_model = self._make_model()
        with patch.object(WritingService, "get_langchain_service", return_value=fake):
            result = await WritingService.generate_content(
                db=db_session,
                tool_type="press_release",
                user_input={
                    "topic": "公司发布新产品",
                    "news_type": "企业新闻稿",
                    "key_info": "关键信息",
                },
                ai_model=ai_model,
            )
        prompt = fake.captured["message"]
        assert result == "生成内容"
        assert "专业新闻记者" in prompt
        assert "公司发布新产品" in prompt

    @pytest.mark.asyncio
    async def test_academic_paper_template_works(self, db_session):
        """论文写作模板可正常填充并生成"""
        fake = _FakeChatService()
        ai_model = self._make_model()
        with patch.object(WritingService, "get_langchain_service", return_value=fake):
            result = await WritingService.generate_content(
                db=db_session,
                tool_type="academic_paper",
                user_input={
                    "title": "人工智能在医疗诊断中的应用研究",
                    "field": "计算机科学",
                    "method": "文献研究",
                    "main_points": "AI辅助诊断",
                },
                ai_model=ai_model,
            )
        prompt = fake.captured["message"]
        assert result == "生成内容"
        assert "学术论文写作专家" in prompt
        assert "人工智能在医疗诊断中的应用研究" in prompt

    def test_map_creation_type(self):
        """写作工具类型 -> creations.creation_type ENUM 映射"""
        from app.api.v1.writing import map_creation_type

        assert map_creation_type("academic_paper") == "PAPER"
        assert map_creation_type("content_rewrite") == "REWRITE"
        assert map_creation_type("rewrite") == "REWRITE"
        assert map_creation_type("press_release") == "NEWS_ARTICLE"
        assert map_creation_type("resume_cover_letter") == "RESUME"
        assert map_creation_type("story_novel") == "STORY"
        assert map_creation_type("wechat_article") == "WECHAT_ARTICLE"
        with pytest.raises(ValueError):
            map_creation_type("unknown_tool")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
