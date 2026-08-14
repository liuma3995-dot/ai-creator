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


class TestGetAIService:
    """测试 get_ai_service 方法"""
    
    def test_get_openai_service(self):
        """测试获取 OpenAI 服务"""
        # 创建模拟的 AIModel
        ai_model = Mock()
        ai_model.provider = "openai"
        ai_model.api_key = "test-api-key"
        ai_model.base_url = "https://api.test.com/v1"
        ai_model.model_name = "gpt-4-turbo"
        
        service = WritingService.get_ai_service(ai_model)
        
        assert isinstance(service, OpenAIService)
        assert service.api_key == "test-api-key"
        assert service.base_url == "https://api.test.com/v1"
        assert service.model == "gpt-4-turbo"
    
    def test_get_openai_service_with_defaults(self):
        """测试 OpenAI 服务使用默认值"""
        ai_model = Mock()
        ai_model.provider = "openai"
        ai_model.api_key = "test-api-key"
        ai_model.base_url = None  # 使用默认值
        ai_model.model_name = None  # 使用默认值
        
        service = WritingService.get_ai_service(ai_model)
        
        assert isinstance(service, OpenAIService)
        assert service.base_url == "https://api.openai.com/v1"
        assert service.model == "gpt-4"
    
    def test_get_anthropic_service(self):
        """测试获取 Anthropic 服务"""
        ai_model = Mock()
        ai_model.provider = "anthropic"
        ai_model.api_key = "test-anthropic-key"
        ai_model.model_name = "claude-3-sonnet-20240229"
        
        service = WritingService.get_ai_service(ai_model)
        
        assert isinstance(service, AnthropicService)
        assert service.api_key == "test-anthropic-key"
        assert service.model == "claude-3-sonnet-20240229"
    
    def test_get_anthropic_service_with_defaults(self):
        """测试 Anthropic 服务使用默认值"""
        ai_model = Mock()
        ai_model.provider = "anthropic"
        ai_model.api_key = "test-anthropic-key"
        ai_model.model_name = None
        
        service = WritingService.get_ai_service(ai_model)
        
        assert isinstance(service, AnthropicService)
        assert service.model == "claude-3-opus-20240229"
    
    def test_unsupported_provider(self):
        """测试不支持的提供商"""
        ai_model = Mock()
        ai_model.provider = "unsupported"
        
        with pytest.raises(ValueError) as exc_info:
            WritingService.get_ai_service(ai_model)
        
        assert "不支持的AI服务提供商" in str(exc_info.value)


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
        # 模拟 AI 模型
        ai_model = Mock()
        ai_model.provider = "openai"
        ai_model.api_key = "test-key"
        ai_model.base_url = "https://api.openai.com/v1"
        ai_model.model_name = "gpt-4"
        
        # 模拟 db
        db = Mock()
        
        # 模拟 OpenAIService.generate_text
        with patch.object(OpenAIService, 'generate_text', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = "生成的文章内容"
            
            result = await WritingService.generate_content(
                db=db,
                tool_type="wechat_article",
                user_input={"topic": "AI技术", "keywords": "人工智能"},
                ai_model=ai_model,
            )
            
            assert result == "生成的文章内容"
            mock_generate.assert_called_once()
            
            # 检查调用的 prompt 是否包含默认值
            call_args = mock_generate.call_args
            prompt = call_args[0][0]  # 第一个位置参数
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
        
        db = Mock()
        
        with patch.object(OpenAIService, 'generate_text', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = "生成的文章内容"
            
            result = await WritingService.generate_content(
                db=db,
                tool_type="wechat_article",
                user_input={
                    "topic": "AI技术",
                    "keywords": "人工智能",
                    "target_audience": "技术人员",  # 覆盖默认值
                    "style": "技术文",
                },
                ai_model=ai_model,
            )
            
            call_args = mock_generate.call_args
            prompt = call_args[0][0]
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
