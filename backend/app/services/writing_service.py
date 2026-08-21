"""
写作服务
支持三种模式：
1. API Key模式 - 使用 LangChain 统一调用
2. Cookie模式 - 通过OAuth账号使用网页版
3. 插件增强模式 - 通过插件获取实时信息

已改造为使用 LangChain 统一服务，支持 16 个 AI 厂商。
"""
from typing import Dict, Any, Optional, List
import logging
import time
import json
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.creation import Creation
from app.models.ai_model import AIModel
from app.schemas.creation import CreationCreate
# 使用新的 LangChain 服务
from app.services.langchain import LangChainService, quick_chat

from app.services.ai.prompt_templates import get_platform_prompt

logger = logging.getLogger(__name__)


class WritingService:
    """写作服务"""

    # 工具类型别名：前端/历史记录中出现的旧类型名 -> 规范模板键
    TOOL_ALIASES = {
        "content_rewrite": "rewrite",
        "press_release": "news_article",
        "resume_cover_letter": "resume",
    }

    @classmethod
    def _normalize_tool_type(cls, tool_type: str) -> str:
        """将工具类型别名归一化为模板键"""
        return cls.TOOL_ALIASES.get(tool_type, tool_type)
    
    # 写作工具提示词模板
    TOOL_PROMPTS = {
        "wechat_article": """你是一位专业的微信公众号文章写手。请根据以下信息创作一篇高质量的公众号文章：

主题：{topic}
关键词：{keywords}
目标读者：{target_audience}
文章风格：{style}

要求：
1. 标题吸引人，包含关键词
2. 开头引人入胜，快速抓住读者注意力
3. 内容结构清晰，使用小标题分段
4. 语言生动有趣，贴近读者
5. 适当使用emoji表情
6. 结尾有互动引导（点赞、转发、评论）
7. 字数控制在1500-2500字

请直接输出文章内容，包含标题。""",
        
        "xiaohongshu_note": """你是一位小红书爆款笔记创作专家。请根据以下信息创作一篇小红书笔记：

主题：{topic}
关键词：{keywords}
笔记类型：{note_type}

要求：
1. 标题使用数字、emoji、符号等吸引眼球
2. 开头直击痛点或亮点
3. 内容分点呈现，每点简洁有力
4. 大量使用emoji表情
5. 适当添加话题标签#
6. 结尾引导互动（收藏、点赞、关注）
7. 字数控制在500-1000字
8. 语言口语化、真实感强

请直接输出笔记内容。""",
        
        "official_document": """你是一位资深公文写作专家。请根据以下信息撰写一份规范的公文：

公文类型：{doc_type}
主题：{topic}
发文单位：{issuer}
收文单位：{receiver}
主要内容：{content}

要求：
1. 严格遵循公文格式规范
2. 语言正式、准确、简洁
3. 结构完整（标题、主送机关、正文、落款等）
4. 逻辑清晰，层次分明
5. 用词规范，避免口语化

请直接输出公文内容。""",
        
        "academic_paper": """你是一位学术论文写作专家。请根据以下信息撰写学术论文：

论文题目：{title}
研究领域：{field}
研究方法：{method}
核心观点：{main_points}

要求：
1. 包含摘要、关键词、引言、正文、结论、参考文献
2. 语言学术化、严谨
3. 论证充分，逻辑严密
4. 适当引用文献
5. 字数控制在3000-5000字

请直接输出论文内容。""",
        
        "marketing_copy": """你是一位资深营销文案策划。请根据以下信息创作营销文案：

产品/服务：{product}
目标客户：{target_customer}
核心卖点：{selling_points}
营销目标：{goal}

要求：
1. 标题抓眼球，激发兴趣
2. 突出产品核心价值和差异化优势
3. 使用AIDA模型（注意-兴趣-欲望-行动）
4. 语言有感染力和说服力
5. 包含明确的行动号召（CTA）
6. 字数控制在800-1500字

请直接输出文案内容。""",
        
        "news_article": """你是一位专业新闻记者。请根据以下信息撰写新闻稿：

新闻主题：{topic}
新闻类型：{news_type}
关键信息：{key_info}

要求：
1. 标题简洁有力，概括核心信息
2. 导语包含5W1H（何时、何地、何人、何事、为何、如何）
3. 倒金字塔结构，重要信息在前
4. 客观中立，事实准确
5. 语言简洁明了
6. 字数控制在800-1200字

请直接输出新闻稿内容。""",
        
        "video_script": """请根据以下信息创作短视频脚本：

{topic_section}{preset_section}视频时长：{duration}
目标平台：{platform}
视频类型：{video_type}
视频风格：{style}

【视频类型钩子策略】{video_type}：{hook_strategy}
【视频风格结构】{style}：{structure}
【镜头节奏】{duration}：目标镜头数 {shot_guide}；单镜最长不超过3秒，快节奏段不超过1秒；分镜时间轴必须覆盖完整{duration}""",
        
        "story_novel": """你是一位优秀的故事作家。请根据以下信息创作故事：

故事类型：{genre}
故事主题：{theme}
主要角色：{characters}
故事背景：{setting}

要求：
1. 情节引人入胜，有起承转合
2. 人物形象鲜明，性格突出
3. 语言生动，富有画面感
4. 适当使用对话和心理描写
5. 结局有意义或有悬念
6. 字数控制在2000-3000字

请直接输出故事内容。""",
        
        "business_plan": """你是一位资深商业顾问。请根据以下信息撰写商业计划书：

项目名称：{project_name}
行业领域：{industry}
商业模式：{business_model}
目标市场：{target_market}

要求：
1. 包含执行摘要、市场分析、产品服务、营销策略、财务预测等
2. 数据支撑，逻辑严密
3. 语言专业、清晰
4. 突出项目优势和可行性
5. 字数控制在3000-5000字

请直接输出商业计划书内容。""",
        
        "work_report": """你是一位专业的工作报告撰写专家。请根据以下信息撰写工作报告：

报告类型：{report_type}
报告周期：{period}
主要工作：{main_work}
工作成果：{achievements}

要求：
1. 结构清晰（工作概述、完成情况、问题分析、下步计划）
2. 数据详实，有理有据
3. 语言简洁、客观
4. 突出重点和亮点
5. 字数控制在1500-2500字

请直接输出工作报告内容。""",
        
        "resume": """你是一位专业的简历撰写顾问。请根据以下信息撰写简历：

姓名：{name}
应聘职位：{position}
工作经验：{experience}
教育背景：{education}
技能特长：{skills}

要求：
1. 格式规范，重点突出
2. 工作经历使用STAR法则描述
3. 量化成果，突出价值
4. 技能与岗位匹配
5. 语言简洁、专业
6. 控制在1-2页

请直接输出简历内容。""",
        
        "rewrite": """你是一位专业的内容改写专家。请根据以下要求改写内容：

原文：{original_text}
改写要求：{rewrite_type}
目标风格：{target_style}

要求：
1. 保持原文核心意思不变
2. 根据要求调整表达方式
3. 优化语言和结构
4. 确保内容流畅自然

请直接输出改写后的内容。""",
        
        "translation": """你是一位专业翻译。请根据以下信息进行翻译：

原文：{source_text}
源语言：{source_lang}
目标语言：{target_lang}
翻译风格：{style}

要求：
1. 准确传达原文意思
2. 符合目标语言习惯
3. 保持原文风格和语气
4. 专业术语准确
5. 语言流畅自然

请直接输出翻译内容。""",

        "lesson_plan": """你是一位经验丰富的教学设计专家。请根据以下信息设计一份完整的教案：

学科/课程：{subject}
年级：{grade}
课时时长：{duration}
教学目标：{objectives}

要求：
1. 包含完整的教学环节（导入、新授、练习、总结）
2. 明确教学目标（知识、能力、情感三维）
3. 设计合适的教学活动和互动环节
4. 包含板书设计或PPT要点
5. 注明时间分配
6. 设计课堂练习和作业布置
7. 考虑学生的认知水平和学习特点

请直接输出教案内容。"""
    }
    
    @staticmethod
    def get_langchain_service(
        ai_model: AIModel,
        user_id: int = None,
        tool: str = None,
        creation_id: int = None
    ) -> LangChainService:
        """根据AI模型配置获取 LangChain 服务实例
        
        Args:
            ai_model: AI模型实例
            user_id: 用户ID（用于监控日志）
            tool: 调用步骤标识（用于监控日志）
            creation_id: 关联创作ID（用于监控日志）
        """
        return LangChainService(
            provider=ai_model.provider,
            model=ai_model.model_name or "gpt-4",
            api_key=ai_model.api_key,
            api_base=ai_model.base_url,
            # 监控参数
            user_id=user_id,
            ai_model_id=ai_model.id,
            tool=tool,
            creation_id=creation_id,
            # 双密钥厂商的额外参数
            secret_key=getattr(ai_model, 'secret_key', None),
            app_id=getattr(ai_model, 'app_id', None),
            api_secret=getattr(ai_model, 'api_secret', None),
            group_id=getattr(ai_model, 'group_id', None),
        )

    @staticmethod
    def _inject_supplement(prompt: str, supplement: str) -> str:
        """将用户补充说明追加到提示词末尾，作为低优先级补充要求"""
        supplement = supplement.strip()
        if not supplement:
            return prompt
        return (
            f"{prompt}\n\n"
            f"【补充要求】\n{supplement}\n"
            f"（以上为补充要求，请在不与上文要求冲突的前提下尽量满足。）"
        )
    
    # 各工具类型的默认参数值
    TOOL_DEFAULTS = {
        "wechat_article": {
            "target_audience": "普通读者",
            "style": "专业严谨",
        },
        "xiaohongshu_note": {
            "note_type": "好物分享",
        },
        "official_document": {
            "doc_type": "通知",
            "issuer": "",
            "receiver": "",
            "content": "",
        },
        "academic_paper": {
            "title": "",
            "field": "通用",
            "method": "文献研究",
            "main_points": "",
        },
        "marketing_copy": {
            "product": "",
            "target_customer": "目标客户",
            "selling_points": "",
            "goal": "提高销量",
        },
        "news_article": {
            "news_type": "企业新闻稿",
            "key_info": "",
        },
        "video_script": {
            "duration": "1分钟",
            "platform": "抖音",
            "preset_content": "",
            "preset_section": "",
            "style": "轻松搞笑",
            "topic": "",
            "topic_section": "",
            "video_type": "",
        },
        "story_novel": {
            "genre": "现代都市",
            "theme": "",
            "characters": "",
            "setting": "",
        },
        "business_plan": {
            "project_name": "",
            "industry": "通用行业",
            "business_model": "",
            "target_market": "",
        },
        "work_report": {
            "report_type": "工作总结",
            "period": "本月",
            "main_work": "",
            "achievements": "",
        },
        "resume": {
            "name": "",
            "position": "",
            "experience": "",
            "education": "",
            "skills": "",
        },
        "lesson_plan": {
            "subject": "",
            "grade": "",
            "duration": "45分钟",
            "objectives": "",
        },
        "rewrite": {
            "original_text": "",
            "rewrite_type": "改写",
            "target_style": "通用",
        },
        "translation": {
            "source_text": "",
            "source_lang": "中文",
            "target_lang": "英文",
            "style": "通用",
        },
    }

    # 短视频脚本：预设内容（客户前采素材）最大长度（字符数）
    MAX_PRESET_CONTENT_LENGTH = 5000

    # 短视频脚本：分层系统提示词（角色+通用规则+输出格式，固定不变）
    TOOL_SYSTEM_PROMPTS = {
        "video_script": """你是一位短视频脚本创作专家。请遵循以下规则创作短视频脚本：

【通用创作规则】
1. 开头3秒必须抓住注意力；若用户消息中给出了视频类型钩子策略则严格遵循，未给出则由你根据内容与所选风格自由设计最有吸引力的开场钩子
2. 按用户消息中给出的视频风格组织节奏与表达方式
3. 节奏紧凑，每5秒设置一个兴趣点
4. 适合竖屏观看（9:16），前3秒要有大字幕
5. 结尾有互动引导（点赞/评论/关注/收藏/转发）
6. 分镜镜头数必须符合用户消息中给出的目标镜头数；单镜最长不超过3秒，快节奏段不超过1秒

【预设内容】
1. 用户消息中的【预设内容/素材方向】是最高优先级的事实基础：选题、台词、画面必须围绕其展开，不得脱离该范围
2. 视频主题（如有）仅作辅助参考；当主题与预设内容不一致时，以预设内容为准
3. 从预设内容中提炼与本次拍摄最相关的信息，避免全量堆砌细节
4. 绝对禁止在输出的任何部分（标题、台词、字幕、分镜表、标签、拍摄要点、备注等）出现预设内容中的电话号码、微信号、邮箱、地址等敏感信息；确需提及时只用"联系方式"这类泛指，不得写出具体号码或账号

【平台适配】
- 抖音/快手：以15-60秒为主，黄金3秒+前3秒大字幕，强互动引导
- B站/小红书：以1-3分钟为主，开头钩子可以稍深，完播导向
- 视频号：社交传播导向，结尾引导转发

【博主风格（表达人格，按用户所选视频风格遵循）】
- 影视飓风：电影质感、工业化画面描述；问题→讲解→解决；专业但通俗（10岁孩子都能听懂）；节奏紧凑、视觉记忆点强；结尾情绪共鸣
- 薛辉：脱口秀式口播、极度松弛；先共鸣/抛坑再讲方法论；案例+亲身经历；带梗不端着；互动引导强；金句收尾
- 何同学：脑洞提问开场；实验/故事推进；可视化表达；年轻化口语；结尾升华意义
- 房琪Kiki：金句文案开场；唯美画面意境；克制真实表达；情感递进；结尾格局升华

【输出格式】（严格按以下六要素，使用Markdown）
## 一、视频标题（2个备选，20字内，含关键词或悬念）
## 二、黄金3秒开头（钩子类型+开场口播+开场画面）
## 三、分镜表（Markdown表格，固定表头：镜号|时间轴|画面|台词|字幕|音效，逐镜列出）
## 四、强化结尾（CTA互动引导+记忆点金句）
## 五、标签建议（5-8个精准标签）
## 六、拍摄要点（关键镜头技巧、道具场景、注意事项）""",
    }

    # 短视频脚本：8 种视频类型 -> 钩子策略（动态注入所选类型）
    VIDEO_SCRIPT_HOOKS = {
        "成本型": "利益点钩——直接给出代价/投入与收益的强对比",
        "人群型": "身份认同钩——用圈层标签开场，让用户觉得“这说的就是我”",
        "猎奇型": "悬念/反常识钩——用反常识或圈内秘闻开场，制造好奇心",
        "反差型": "冲突反转钩——打破固有预期，用反差制造停留与评论",
        "最差型": "避坑清单钩——盘点坑点/避坑预警开场",
        "头牌型": "权威标杆钩——借头部案例与标杆数据开场提升专业感",
        "怀旧型": "情感共鸣钩——唤醒共同记忆，触发情感共鸣",
        "荷尔蒙型": "向往感钩——用审美、体面、自信气场制造向往感",
    }

    # 短视频脚本：9 种视频风格 -> 结构要求（动态注入所选风格）
    VIDEO_SCRIPT_STRUCTURES = {
        "轻松搞笑": "段子+反转结构，节奏明快",
        "专业讲解": "总分总结构，逻辑清晰",
        "情感故事": "故事+情感共鸣结构，情绪递进",
        "快节奏剪辑": "每5秒一个兴趣点，快切镜头",
        "Vlog风格": "第一人称+过程记录结构",
        "教知识": "问题+反常识+三步拆解（或清单避坑）结构，干货密集",
        "晒过程": "立目标+过程记录+结果呈现结构，持续制造期待",
        "聊观点": "观点+反驳+我的看法结构，引发评论",
        "讲故事": "故事+感悟+行动建议结构，建立信任",
        "影视飓风": "电影质感+工业化叙事：问题→讲解→解决，专业但通俗，画面视觉冲击强，节奏紧凑，结尾情绪共鸣",
        "薛辉": "脱口秀式讲课：先共鸣/抛坑→案例+方法论→金句收尾，松弛口语、带梗、强互动",
        "何同学": "脑洞实验叙事：脑洞提问开场→实验/故事推进→可视化表达→意义升华结尾",
        "房琪Kiki": "治愈文案叙事：金句开场→唯美画面→克制真实表达→情感递进→格局升华结尾",
    }

    # 短视频脚本：时长 -> 目标镜头数（动态注入所选时长）
    VIDEO_SCRIPT_SHOT_GUIDE = {
        "15秒": "2-4镜",
        "30秒": "5-8镜",
        "1分钟": "10-15镜",
        "3分钟": "18-30镜",
        "5分钟": "30-45镜",
    }
    
    @classmethod
    async def generate_content(
        cls,
        db: Session,
        tool_type: str,
        user_input: Dict[str, Any],
        ai_model: AIModel,
        user_id: int = None,
        creation_id: int = None
    ) -> str:
        """生成内容
        
        Args:
            db: 数据库会话
            tool_type: 工具类型
            user_input: 用户输入
            ai_model: AI模型实例
            user_id: 用户ID（用于监控日志）
            creation_id: 关联创作ID（用于监控日志）
        """
        tool_type = cls._normalize_tool_type(tool_type)
        # 获取提示词模板
        if tool_type not in cls.TOOL_PROMPTS:
            raise ValueError(f"不支持的写作工具类型: {tool_type}")
        
        prompt_template = cls.TOOL_PROMPTS[tool_type]
        
        # 提取用户补充说明（不传递给模板格式化）
        additional_description = user_input.pop('additional_description', None)
        
        # 合并默认参数和用户输入
        defaults = cls.TOOL_DEFAULTS.get(tool_type, {})
        merged_input = {**defaults, **user_input}

        # 短视频脚本：分层提示词 + 动态组装（A+B）
        # 系统提示词承载角色/规则/输出格式；用户消息只注入所选类型/风格/时长的策略
        system_prompt = None
        if tool_type == "video_script":
            video_type_label = (merged_input.get("video_type") or "").strip() or "自由创作"
            merged_input["hook_strategy"] = cls.VIDEO_SCRIPT_HOOKS.get(
                merged_input.get("video_type"),
                "根据内容与所选风格自由设计最有吸引力的开场钩子",
            )
            merged_input["video_type"] = video_type_label
            merged_input["structure"] = cls.VIDEO_SCRIPT_STRUCTURES.get(
                merged_input.get("style"), "结构清晰、节奏紧凑"
            )
            merged_input["shot_guide"] = cls.VIDEO_SCRIPT_SHOT_GUIDE.get(
                merged_input.get("duration"), "按平台惯例"
            )
            preset_content = (merged_input.get("preset_content") or "").strip()
            if not preset_content:
                raise ValueError(
                    "请填写预设内容（客户基础信息与拍摄方向），作为脚本的事实基础"
                )
            if len(preset_content) > cls.MAX_PRESET_CONTENT_LENGTH:
                raise ValueError(
                    f"预设内容过长，最多支持 {cls.MAX_PRESET_CONTENT_LENGTH} 字"
                )
            merged_input["preset_section"] = (
                f"【预设内容/素材方向】\n{preset_content}\n" if preset_content else ""
            )
            topic = (merged_input.get("topic") or "").strip()
            merged_input["topic_section"] = f"视频主题：{topic}\n" if topic else ""
            system_prompt = cls.TOOL_SYSTEM_PROMPTS.get("video_script")
        
        # 填充提示词
        try:
            prompt = prompt_template.format(**merged_input)
        except KeyError as e:
            raise ValueError(f"缺少必需的输入参数: {str(e)}")
        
        # 如果用户提供了补充说明，追加到提示词末尾（低优先级补充要求）
        if additional_description and additional_description.strip():
            prompt = cls._inject_supplement(prompt, additional_description)
        
        # 调用 LangChain 服务生成内容
        service = cls.get_langchain_service(
            ai_model,
            user_id=user_id,
            tool=tool_type,
            creation_id=creation_id
        )
        response = await service.chat(prompt, system_prompt=system_prompt)
        
        return response.content
    
    @classmethod
    async def optimize_content(
        cls,
        db: Session,
        content: str,
        optimization_type: str,
        ai_model: AIModel,
        user_id: int = None
    ) -> str:
        """优化内容
        
        Args:
            db: 数据库会话
            content: 内容
            optimization_type: 优化类型
            ai_model: AI模型实例
            user_id: 用户ID（用于监控日志）
        """
        optimization_prompts = {
            "seo": f"请对以下内容进行SEO优化，提高搜索引擎友好度：\n\n{content}",
            "readability": f"请优化以下内容的可读性，使其更易理解：\n\n{content}",
            "style": f"请在不改变原意的前提下调整以下内容的文风，使其更自然、更有感染力，并符合目标场景的表达习惯：\n\n{content}",
            "engagement": f"请优化以下内容，提高用户参与度和互动性：\n\n{content}",
            "concise": f"请精简以下内容，保留核心信息：\n\n{content}",
            "expand": f"请扩展以下内容，增加细节和深度：\n\n{content}"
        }
        
        if optimization_type not in optimization_prompts:
            raise ValueError(f"不支持的优化类型: {optimization_type}")
        
        prompt = optimization_prompts[optimization_type]
        
        # 调用 LangChain 服务优化内容
        service = cls.get_langchain_service(
            ai_model,
            user_id=user_id,
            tool=f"optimize_{optimization_type}"
        )
        response = await service.chat(prompt)
        
        return response.content
    
    @staticmethod
    def get_available_tools():
        """获取所有可用的写作工具列表"""
        tools = [
            {
                "type": "wechat_article",
                "name": "公众号文章",
                "description": "创作高质量的微信公众号文章",
                "icon": "📱",
                "required_fields": ["topic", "keywords", "target_audience", "style"]
            },
            {
                "type": "xiaohongshu_note",
                "name": "小红书笔记",
                "description": "创作爆款小红书笔记",
                "icon": "📔",
                "required_fields": ["topic", "keywords", "note_type"]
            },
            {
                "type": "official_document",
                "name": "公文写作",
                "description": "撰写规范的公文",
                "icon": "📄",
                "required_fields": ["doc_type", "topic", "issuer", "receiver", "content"]
            },
            {
                "type": "academic_paper",
                "name": "论文写作",
                "description": "撰写学术论文",
                "icon": "🎓",
                "required_fields": ["title", "field", "method", "main_points"]
            },
            {
                "type": "marketing_copy",
                "name": "营销文案",
                "description": "创作有说服力的营销文案",
                "icon": "💼",
                "required_fields": ["product", "target_customer", "selling_points", "goal"]
            },
            {
                "type": "news_article",
                "name": "新闻稿",
                "description": "撰写专业的新闻稿",
                "icon": "📰",
                "required_fields": ["topic", "news_type", "key_info"]
            },
            {
                "type": "video_script",
                "name": "短视频脚本",
                "description": "创作短视频脚本",
                "icon": "🎬",
                "required_fields": ["topic", "duration", "platform", "style"]
            },
            {
                "type": "story_novel",
                "name": "故事创作",
                "description": "创作引人入胜的故事",
                "icon": "📖",
                "required_fields": ["genre", "theme", "characters", "setting"]
            },
            {
                "type": "business_plan",
                "name": "商业计划书",
                "description": "撰写商业计划书",
                "icon": "💡",
                "required_fields": ["project_name", "industry", "business_model", "target_market"]
            },
            {
                "type": "work_report",
                "name": "工作报告",
                "description": "撰写工作报告",
                "icon": "📊",
                "required_fields": ["report_type", "period", "main_work", "achievements"]
            },
            {
                "type": "resume",
                "name": "简历",
                "description": "撰写专业简历",
                "icon": "👔",
                "required_fields": ["name", "position", "experience", "education", "skills"]
            },
            {
                "type": "rewrite",
                "name": "内容改写",
                "description": "改写和优化内容",
                "icon": "✏️",
                "required_fields": ["original_text", "rewrite_type", "target_style"]
            },
            {
                "type": "translation",
                "name": "多语言翻译",
                "description": "专业多语言翻译",
                "icon": "🌐",
                "required_fields": ["source_text", "source_lang", "target_lang", "style"]
            }
            ]
        return tools
    
    @classmethod
    async def generate_content_with_plugins(
        cls,
        db: Session,
        tool_type: str,
        user_input: Dict[str, Any],
        ai_model: AIModel,
        enabled_plugins: Optional[List[str]] = None,
        user_id: Optional[int] = None,
        creation_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        使用插件增强的内容生成
        
        AI 可以根据需要调用启用的插件获取实时信息，
        例如搜索最新资讯、计算数据等。
        
        Args:
            db: 数据库连接
            tool_type: 工具类型
            user_input: 用户输入
            ai_model: AI模型配置
            enabled_plugins: 启用的插件名称列表
            user_id: 用户ID（用于日志记录）
            creation_id: 创作ID（用于关联日志）
            
        Returns:
            {
                "content": str,  # 生成的内容
                "plugin_invocations": list,  # 插件调用记录
                "usage": dict  # token 使用情况
            }
        """
        tool_type = cls._normalize_tool_type(tool_type)
        from app.services.plugins.plugin_manager import PluginManager
        from app.models.plugin import PluginInvocation, UserPlugin
        
        # 获取提示词模板
        if tool_type not in cls.TOOL_PROMPTS:
            raise ValueError(f"不支持的写作工具类型: {tool_type}")
        
        prompt_template = cls.TOOL_PROMPTS[tool_type]
        
        # 提取用户补充说明（不传递给模板格式化）
        additional_description = user_input.pop('additional_description', None)
        
        # 合并默认参数和用户输入
        defaults = cls.TOOL_DEFAULTS.get(tool_type, {})
        merged_input = {**defaults, **user_input}
        
        # 填充提示词
        try:
            base_prompt = prompt_template.format(**merged_input)
        except KeyError as e:
            raise ValueError(f"缺少必需的输入参数: {str(e)}")
        
        # 如果用户提供了补充说明，追加到提示词末尾（低优先级补充要求）
        if additional_description and additional_description.strip():
            base_prompt = cls._inject_supplement(base_prompt, additional_description)
        
        # 检测补充说明中是否有URL
        has_url = False
        if additional_description:
            import re
            url_pattern = r'https?://[^\s）\)\]]+'
            if re.search(url_pattern, additional_description):
                has_url = True
                logger.info("检测到用户补充说明中包含URL链接")
        
        # 如果没有启用插件，直接生成
        if not enabled_plugins:
            # 如果有URL但没有启用插件，自动添加web_fetch插件
            if has_url:
                logger.info("检测到URL但未启用插件，自动添加web_fetch插件")
                enabled_plugins = ["web_fetch"]
                
                # 检查用户是否已安装web_fetch插件，如果没有则自动安装
                from app.models.plugin import UserPlugin
                existing = db.query(UserPlugin).filter(
                    UserPlugin.user_id == user_id,
                    UserPlugin.plugin_name == "web_fetch",
                    UserPlugin.is_enabled == True
                ).first()
                
                if not existing:
                    logger.info(f"用户{user_id}未安装web_fetch插件，自动安装")
                    user_plugin = UserPlugin(
                        user_id=user_id,
                        plugin_name="web_fetch",
                        is_enabled=True,
                        config={},
                        is_auto_use=False
                    )
                    db.add(user_plugin)
                    db.commit()
            else:
                service = cls.get_langchain_service(
                    ai_model,
                    user_id=user_id,
                    tool=tool_type
                )
                response = await service.chat(base_prompt)
                return {
                    "content": response.content,
                    "plugin_invocations": [],
                    "usage": {}
                }
        
        # 初始化插件管理器（单例）
        plugin_manager = PluginManager()
        
        # 加载插件实例（带用户配置）
        plugins = plugin_manager.create_plugin_instances(db, user_id or 0, enabled_plugins)
        
        if not plugins:
            # 没有有效插件，直接生成
            service = cls.get_langchain_service(
                ai_model,
                user_id=user_id,
                tool=tool_type
            )
            response = await service.chat(base_prompt)
            return {
                "content": response.content,
                "plugin_invocations": [],
                "usage": {}
            }
        
        # 构建 OpenAI tools 定义
        tools = [plugin.to_openai_function() for plugin in plugins]
        
        # 构建增强的系统提示
        system_prompt = """你是一位专业的内容创作助手。你可以使用以下工具来获取信息和完成任务：

可用工具：
"""
        for plugin in plugins:
            system_prompt += f"- {plugin.display_name}: {plugin.description}\n"
        
        system_prompt += """
在创作过程中，如果需要最新信息、事实数据或计算结果，请使用相应的工具。

【重要】如果用户的输入（特别是"补充说明"字段）中包含URL链接（以http://或https://开头），请：
1. 先使用"网页抓取"工具获取该链接的内容
2. 仔细阅读获取到的内容
3. 基于获取到的内容进行创作，将信息自然地融入文章中

工具返回的信息应该融入到你的创作中，而不是直接展示给用户。
"""
        
        # 构建消息
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": base_prompt}
        ]
        
        # 创建工具执行器
        invocation_logs = []
        
        async def tool_executor(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
            """执行插件并记录日志"""
            start_time = time.time()
            error_msg = None
            result = None
            
            try:
                # 查找对应的插件
                plugin = next((p for p in plugins if p.name == tool_name), None)
                if not plugin:
                    return {"success": False, "error": f"未找到插件: {tool_name}"}
                
                # 执行插件
                result = await plugin.execute(**arguments)
                return result
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Plugin execution error: {tool_name} - {e}")
                return {"success": False, "error": error_msg}
            
            finally:
                # 记录调用日志
                duration_ms = int((time.time() - start_time) * 1000)
                
                invocation_logs.append({
                    "plugin_name": tool_name,
                    "arguments": arguments,
                    "result": result,
                    "error": error_msg,
                    "duration_ms": duration_ms
                })
                
                # 持久化到数据库
                if user_id:
                    invocation = PluginInvocation(
                        user_id=user_id,
                        creation_id=creation_id,
                        plugin_name=tool_name,
                        arguments=arguments,
                        result=result,
                        error=error_msg,
                        duration_ms=duration_ms
                    )
                    db.add(invocation)
                    
                    # 更新用户插件使用统计
                    user_plugin = db.query(UserPlugin).filter(
                        UserPlugin.user_id == user_id,
                        UserPlugin.plugin_name == tool_name
                    ).first()
                    if user_plugin:
                        user_plugin.usage_count = (user_plugin.usage_count or 0) + 1
                        user_plugin.last_used_at = datetime.utcnow()
                    
                    db.commit()
        
        # 使用 LangChain 服务执行带工具的聊天
        from app.services.langchain.tools import create_tool_from_plugin
        
        # 将插件转换为 LangChain Tools
        langchain_tools = [create_tool_from_plugin(plugin) for plugin in plugins]
        
        service = cls.get_langchain_service(
            ai_model,
            user_id=user_id,
            tool=tool_type,
            creation_id=creation_id
        )
        
        try:
            # 使用带工具的对话
            response = await service.chat_with_tools(
                message=base_prompt,
                tools=langchain_tools,
                system_prompt=system_prompt,
                max_iterations=5
            )
            
            return {
                "content": response.content,
                "plugin_invocations": invocation_logs,
                "usage": {}
            }
        except Exception as e:
            # 工具调用失败时回退到普通生成
            logger.warning(f"Tool-based generation failed, falling back to normal: {e}")
            response = await service.chat(base_prompt)
            return {
                "content": response.content,
                "plugin_invocations": [],
                "usage": {}
            }
    
    @classmethod
    async def generate_content_with_template(
        cls,
        db: Session,
        platform: str,
        category: str,
        user_input: Dict[str, Any],
        ai_model: AIModel,
        style: Optional[str] = None,
        template_id: Optional[int] = None
    ) -> str:
        """
        使用平台模板生成内容
        
        Args:
            db: 数据库连接
            platform: 平台类型 (wechat/xiaohongshu/toutiao/ppt)
            category: 场景分类
            user_input: 用户输入
            ai_model: AI模型配置
            style: 风格类型
            template_id: 模板ID（可选，如果提供则使用该模板的提示词）
            
        Returns:
            生成的内容
        """
        from app.models.template import ContentTemplate
        
        # 如果提供了模板ID，使用模板的自定义提示词
        if template_id:
            template = db.query(ContentTemplate).filter(
                ContentTemplate.id == template_id
            ).first()
            
            if template and template.ai_prompt:
                prompt_template = template.ai_prompt
            else:
                # 使用默认的平台提示词
                prompt_template = get_platform_prompt(platform, category, style)
        else:
            # 使用默认的平台提示词
            prompt_template = get_platform_prompt(platform, category, style)
        
        # 提取用户补充说明
        additional_info = user_input.pop('additional_info', user_input.pop('additional_description', ''))
        
        # 填充提示词
        try:
            prompt = prompt_template.format(
                topic=user_input.get('topic', ''),
                additional_info=additional_info or '',
                **user_input
            )
        except KeyError as e:
            # 如果格式化失败，使用简单的方式
            prompt = f"{prompt_template}\n\n【主题】{user_input.get('topic', '')}\n【补充信息】{additional_info}"
        
        # 调用 LangChain 服务生成内容
        service = cls.get_langchain_service(ai_model)
        response = await service.chat(prompt)
        
        return response.content
