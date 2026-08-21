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
        self.captured["system_prompt"] = kwargs.get("system_prompt")
        return SimpleNamespace(content="生成内容")


class TestGenerateContentSupplement:
    """测试生成/重新生成时补充说明进入提示词"""

    async def test_generate_content_appends_supplement_at_end_without_priority(self, db_session):
        """补充说明追加到提示词末尾，作为低优先级要求，不再触发极简模式"""
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
        assert "小红书爆款笔记创作专家" in prompt
        assert prompt.startswith("你是一位小红书爆款笔记创作专家")
        assert "字数要求：50字" in prompt
        assert "【补充要求】\n字数要求：50字" in prompt
        assert "最高优先级" not in prompt
        # 补充说明块位于提示词末尾
        assert prompt.endswith("（以上为补充要求，请在不与上文要求冲突的前提下尽量满足。）")

    async def test_generate_content_general_supplement_keeps_template(self, db_session):
        """补充说明未指定字数时，保留工具模板并追加到末尾"""
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
        assert "【补充要求】\n语言要口语化、有感染力" in prompt
        assert "最高优先级" not in prompt
        assert prompt.endswith("（以上为补充要求，请在不与上文要求冲突的前提下尽量满足。）")


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
            # hook_strategy/structure/shot_guide 为 video_script 派生字段（由类型/风格/时长计算）
            user_input_fields = {
                'topic', 'keywords', 'content', 'title', 'original_content',
                'hook_strategy', 'structure', 'shot_guide',
            }
            for placeholder in placeholders:
                if placeholder not in user_input_fields:
                    assert placeholder in defaults, \
                        f"工具 {tool_type} 的占位符 {placeholder} 没有默认值"


class TestVideoScriptTemplate:
    """短视频脚本模板：8 类型 × 9 风格、六要素输出、时长换算、钩子与结构指引"""

    VIDEO_TYPES = ["成本型", "人群型", "猎奇型", "反差型", "最差型", "头牌型", "怀旧型", "荷尔蒙型"]
    STYLES = [
        "轻松搞笑", "专业讲解", "情感故事", "快节奏剪辑", "Vlog风格",
        "教知识", "晒过程", "聊观点", "讲故事",
        "影视飓风", "薛辉", "何同学", "房琪Kiki",
    ]
    SECTIONS = [
        "## 一、视频标题", "## 二、黄金3秒开头", "## 三、分镜表",
        "## 四、强化结尾", "## 五、标签建议", "## 六、拍摄要点",
    ]

    def _render(self, **overrides):
        template = WritingService.TOOL_PROMPTS["video_script"]
        defaults = WritingService.TOOL_DEFAULTS.get("video_script", {})
        merged = {**defaults, "topic": "测试主题", **overrides}
        video_type_label = (merged.get("video_type") or "").strip() or "自由创作"
        merged["hook_strategy"] = WritingService.VIDEO_SCRIPT_HOOKS.get(
            merged.get("video_type"),
            "根据内容与所选风格自由设计最有吸引力的开场钩子",
        )
        merged["video_type"] = video_type_label
        merged["structure"] = WritingService.VIDEO_SCRIPT_STRUCTURES.get(merged.get("style"), "")
        merged["shot_guide"] = WritingService.VIDEO_SCRIPT_SHOT_GUIDE.get(merged.get("duration"), "")
        preset_content = (merged.get("preset_content") or "").strip()
        merged["preset_section"] = (
            f"【预设内容/素材方向】\n{preset_content}\n" if preset_content else ""
        )
        topic = (merged.get("topic") or "").strip()
        merged["topic_section"] = f"视频主题：{topic}\n" if topic else ""
        return template.format(**merged)

    def test_template_fills_all_video_types_and_styles(self):
        """8 种视频类型 × 13 种风格全部可正常填充模板"""
        for vtype in self.VIDEO_TYPES:
            for style in self.STYLES:
                prompt = self._render(video_type=vtype, style=style)
                assert vtype in prompt
                assert style in prompt

    def test_prompt_contains_six_sections(self):
        """系统提示词要求六要素结构化输出"""
        system_prompt = WritingService.TOOL_SYSTEM_PROMPTS["video_script"]
        for section in self.SECTIONS:
            assert section in system_prompt

    def test_prompt_contains_shot_guide(self):
        """时长换算字典齐全，且用户消息只注入所选时长的目标镜头数"""
        assert WritingService.VIDEO_SCRIPT_SHOT_GUIDE == {
            "15秒": "2-4镜", "30秒": "5-8镜", "1分钟": "10-15镜",
            "3分钟": "18-30镜", "5分钟": "30-45镜",
        }
        assert "目标镜头数 5-8镜" in self._render(duration="30秒")
        assert "目标镜头数 2-4镜" in self._render(duration="15秒")
        assert "目标镜头数 10-15镜" in self._render(duration="1分钟")

    def test_prompt_contains_hook_and_structure_guides(self):
        """钩子与结构字典覆盖 8 类型 × 13 风格；用户消息只注入所选内容（B）"""
        assert len(WritingService.VIDEO_SCRIPT_HOOKS) == 8
        for hook in ["利益点钩", "身份认同钩", "悬念/反常识钩", "冲突反转钩",
                     "避坑清单钩", "权威标杆钩", "情感共鸣钩", "向往感钩"]:
            assert any(hook in v for v in WritingService.VIDEO_SCRIPT_HOOKS.values())
        assert len(WritingService.VIDEO_SCRIPT_STRUCTURES) == 13
        for struct in ["段子+反转", "总分总", "故事+情感共鸣", "每5秒一个兴趣点",
                       "第一人称+过程记录", "问题+反常识+三步拆解", "立目标+过程记录+结果呈现",
                       "观点+反驳+我的看法", "故事+感悟+行动建议"]:
            assert any(struct in v for v in WritingService.VIDEO_SCRIPT_STRUCTURES.values())
        for struct in ["电影质感", "脱口秀式讲课", "脑洞实验叙事", "治愈文案叙事"]:
            assert any(struct in v for v in WritingService.VIDEO_SCRIPT_STRUCTURES.values())

        prompt = self._render(video_type="猎奇型", style="教知识")
        assert "悬念/反常识钩" in prompt
        assert "问题+反常识+三步拆解" in prompt
        assert "利益点钩" not in prompt  # 未选类型不注入
        assert "讲故事" not in prompt    # 未选风格不注入

    @pytest.mark.asyncio
    async def test_generate_video_script_uses_system_prompt_and_dynamic_assembly(self, db_session):
        """分层提示词：规则/格式在 system，用户消息只注入所选类型/风格（A+B）"""
        fake = _FakeChatService()
        ai_model = Mock()
        ai_model.provider = "openai"
        ai_model.api_key = "test-key"
        ai_model.model_name = "gpt-4"
        ai_model.base_url = None
        ai_model.id = 1
        with patch.object(WritingService, "get_langchain_service", return_value=fake):
            await WritingService.generate_content(
                db=db_session,
                tool_type="video_script",
                user_input={
                    "topic": "测试主题",
                    "duration": "30秒",
                    "platform": "抖音",
                    "video_type": "猎奇型",
                    "style": "教知识",
                    "preset_content": "客户是做母婴用品的，想拍辅食机避坑视频",
                    "additional_description": "口播要口语化",
                },
                ai_model=ai_model,
            )

        system_prompt = fake.captured["system_prompt"]
        user_prompt = fake.captured["message"]

        assert system_prompt is not None
        assert "短视频脚本创作专家" in system_prompt
        for section in self.SECTIONS:
            assert section in system_prompt

        # 用户消息只包含所选类型/风格/时长策略
        assert "猎奇型" in user_prompt and "悬念/反常识钩" in user_prompt
        assert "教知识" in user_prompt and "问题+反常识+三步拆解" in user_prompt
        assert "目标镜头数 5-8镜" in user_prompt
        for other in ["成本型", "人群型", "反差型", "晒过程", "聊观点", "讲故事"]:
            assert other not in user_prompt

        # 补充说明仍在用户消息末尾，且无最高优先级措辞
        assert "口播要口语化" in user_prompt
        assert "最高优先级" not in user_prompt

    def test_topic_optional(self):
        """视频主题可选：缺省时不出现主题行，主题仍位于预设内容之前"""
        prompt_no_topic = self._render(topic="", preset_content="客户前采素材")
        assert "视频主题：" not in prompt_no_topic
        prompt_with_topic = self._render(topic="辅食机避坑", preset_content="客户前采素材")
        assert prompt_with_topic.index("视频主题：辅食机避坑") < prompt_with_topic.index("【预设内容/素材方向】")

    @pytest.mark.asyncio
    async def test_generate_missing_preset_raises(self, db_session):
        """预设内容为必填：缺失时抛出 ValueError，且不调用模型"""
        fake = _FakeChatService()
        ai_model = Mock()
        ai_model.provider = "openai"
        ai_model.api_key = "test-key"
        ai_model.model_name = "gpt-4"
        ai_model.base_url = None
        ai_model.id = 1
        with patch.object(WritingService, "get_langchain_service", return_value=fake):
            with pytest.raises(ValueError, match="请填写预设内容"):
                await WritingService.generate_content(
                    db=db_session,
                    tool_type="video_script",
                    user_input={"topic": "测试主题"},
                    ai_model=ai_model,
                )
        assert "message" not in fake.captured

    def test_system_prompt_contains_priority_and_blogger_rules(self):
        """system 提示词：预设内容为最高优先级，包含 4 种博主风格规则"""
        system_prompt = WritingService.TOOL_SYSTEM_PROMPTS["video_script"]
        assert "最高优先级" in system_prompt
        assert "以预设内容为准" in system_prompt
        for blogger in ["影视飓风", "薛辉", "何同学", "房琪Kiki"]:
            assert blogger in system_prompt

    def test_defaults_include_video_type(self):
        """默认值：video_type 为空（选填），style 保持轻松搞笑"""
        defaults = WritingService.TOOL_DEFAULTS["video_script"]
        assert defaults["video_type"] == ""
        assert defaults["style"] == "轻松搞笑"

    def test_video_type_optional(self):
        """视频类型可选：缺省时注入自由创作钩子，选择时注入对应钩子策略"""
        prompt_free = self._render(video_type="")
        assert "自由创作" in prompt_free
        assert "自由设计最有吸引力的开场钩子" in prompt_free
        assert "利益点钩" not in prompt_free
        prompt_hooked = self._render(video_type="猎奇型")
        assert "猎奇型" in prompt_hooked
        assert "悬念/反常识钩" in prompt_hooked

    def test_preset_section_injected_when_provided(self):
        """提供预设内容时，在主题之后注入【预设内容/素材方向】段"""
        preset = "客户是做母婴用品的，目标人群是90后妈妈，想拍一条介绍婴儿辅食机的视频，主打省时省力"
        prompt = self._render(preset_content=preset)
        assert "【预设内容/素材方向】" in prompt
        assert preset in prompt
        assert prompt.index("视频主题：测试主题") < prompt.index("【预设内容/素材方向】")
        assert prompt.index("【预设内容/素材方向】") < prompt.index("视频时长：")

    def test_preset_section_omitted_when_empty(self):
        """未提供预设内容时不注入该段，主题后直接是视频时长"""
        prompt = self._render()
        assert "【预设内容/素材方向】" not in prompt
        assert prompt.index("视频主题：测试主题") < prompt.index("视频时长：")

    def test_system_prompt_contains_preset_rules(self):
        """system 提示词包含预设内容规则：事实基础、提炼、隐私"""
        system_prompt = WritingService.TOOL_SYSTEM_PROMPTS["video_script"]
        assert "事实基础" in system_prompt
        assert "提炼" in system_prompt
        assert "敏感信息" in system_prompt

    @pytest.mark.asyncio
    async def test_generate_preset_content_too_long_raises(self, db_session):
        """预设内容超过 5000 字时抛出 ValueError，且不调用模型"""
        assert WritingService.MAX_PRESET_CONTENT_LENGTH == 5000
        fake = _FakeChatService()
        ai_model = Mock()
        ai_model.provider = "openai"
        ai_model.api_key = "test-key"
        ai_model.model_name = "gpt-4"
        ai_model.base_url = None
        ai_model.id = 1
        too_long = "字" * (WritingService.MAX_PRESET_CONTENT_LENGTH + 1)
        with patch.object(WritingService, "get_langchain_service", return_value=fake):
            with pytest.raises(ValueError, match="预设内容过长"):
                await WritingService.generate_content(
                    db=db_session,
                    tool_type="video_script",
                    user_input={"topic": "测试主题", "preset_content": too_long},
                    ai_model=ai_model,
                )
        assert "message" not in fake.captured

    @pytest.mark.asyncio
    async def test_generate_video_script_injects_preset_content(self, db_session):
        """generate_content 全链路：预设内容注入用户消息，系统提示词含隐私约束"""
        fake = _FakeChatService()
        ai_model = Mock()
        ai_model.provider = "openai"
        ai_model.api_key = "test-key"
        ai_model.model_name = "gpt-4"
        ai_model.base_url = None
        ai_model.id = 1
        preset = "客户是餐饮连锁品牌，主打健康轻食，想拍一条介绍新品沙拉的视频，联系电话 13800138000"
        with patch.object(WritingService, "get_langchain_service", return_value=fake):
            await WritingService.generate_content(
                db=db_session,
                tool_type="video_script",
                user_input={
                    "topic": "轻食沙拉推荐",
                    "duration": "30秒",
                    "platform": "抖音",
                    "video_type": "人群型",
                    "style": "教知识",
                    "preset_content": preset,
                },
                ai_model=ai_model,
            )
        user_prompt = fake.captured["message"]
        system_prompt = fake.captured["system_prompt"]
        assert "【预设内容/素材方向】" in user_prompt
        assert preset in user_prompt
        assert "敏感信息" in system_prompt


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
