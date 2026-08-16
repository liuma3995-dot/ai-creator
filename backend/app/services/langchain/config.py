"""
LangChain 服务配置
支持 16 个主流 AI 厂商的统一配置
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class Capability(Enum):
    """模型能力类型"""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


class AuthType(Enum):
    """认证方式"""
    API_KEY = "api_key"                    # 单密钥
    DUAL_KEY = "dual_key"                  # 双密钥 (API Key + Secret Key)
    TRIPLE_KEY = "triple_key"              # 三元组 (讯飞: AppID + APIKey + APISecret)
    OAUTH2 = "oauth2"                      # OAuth2 (Google)
    API_KEY_GROUP = "api_key_group"        # API Key + Group ID (MiniMax)


@dataclass
class ProviderConfig:
    """厂商配置"""
    name: str                                      # 厂商标识符
    display_name: str                              # 显示名称
    base_url: str                                  # 默认 API 地址
    auth_type: AuthType                            # 认证方式
    capabilities: List[Capability]                 # 支持的能力
    langchain_class: Optional[str] = None          # LangChain 类名，None 表示需自定义
    supports_custom_url: bool = True               # 是否支持自定义 URL
    models: Dict[str, List[str]] = field(default_factory=dict)    # 各能力支持的模型
    endpoints: Dict[str, str] = field(default_factory=dict)       # 各能力的端点


# ============================================================================
# 完整厂商配置（16个厂商）
# ============================================================================

PROVIDERS: Dict[str, ProviderConfig] = {
    # ======================== 国外厂商 ========================
    
    "openai": ProviderConfig(
        name="openai",
        display_name="OpenAI",
        base_url="https://api.openai.com/v1",
        auth_type=AuthType.API_KEY,
        capabilities=[Capability.TEXT, Capability.IMAGE],
        langchain_class="langchain_openai.ChatOpenAI",
        models={
            # 2026：GPT-5 系列（gpt-4o/o3 等已退役）；dall-e 系列已停用，改用 gpt-image 系列
            "text": ["gpt-5.4", "gpt-5.4-mini", "gpt-5.3", "gpt-5.2", "gpt-5"],
            "image": ["gpt-image-1", "gpt-image-1-mini"],
        },
        endpoints={
            "chat": "/chat/completions",
            "image": "/images/generations",
        }
    ),
    
    "anthropic": ProviderConfig(
        name="anthropic",
        display_name="Anthropic",
        base_url="https://api.anthropic.com/v1",
        auth_type=AuthType.API_KEY,
        capabilities=[Capability.TEXT],
        langchain_class="langchain_anthropic.ChatAnthropic",
        models={
            "text": [
                "claude-opus-4-7",
                "claude-opus-4-6-20260206",
                "claude-sonnet-4-6-20260217",
                "claude-opus-4-5-20251101",
                "claude-sonnet-4-5-20250929",
                "claude-opus-4-20250514", 
                "claude-sonnet-4-20250514",
                "claude-3-5-sonnet-20241022", 
                "claude-3-5-haiku-20241022",
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307"
            ],
        },
        endpoints={
            "chat": "/messages",
        }
    ),
    
    "google": ProviderConfig(
        name="google",
        display_name="Google Gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        auth_type=AuthType.API_KEY,
        capabilities=[Capability.TEXT, Capability.IMAGE, Capability.VIDEO],
        langchain_class="langchain_google_genai.ChatGoogleGenerativeAI",
        models={
            "text": ["gemini-3-pro", "gemini-3-flash", "gemini-3-deepthink", "gemini-2.5-pro", "gemini-2.5-flash"],
            "image": ["imagen-4.0-generate-001", "imagen-4.0-ultra-generate-001", "gemini-2.5-flash-image"],
            "video": ["veo-3.1", "veo-3"],
        },
        endpoints={
            "chat": "/models/{model}:generateContent",
            "image": "/models/{model}:predict",
        }
    ),
    
    "stability": ProviderConfig(
        name="stability",
        display_name="Stability AI",
        base_url="https://api.stability.ai/v2beta",
        auth_type=AuthType.API_KEY,
        capabilities=[Capability.IMAGE, Capability.VIDEO],
        langchain_class=None,  # 需自定义
        models={
            "image": ["stable-image-core", "stable-image-ultra", "stable-diffusion-3.5-large", "stable-diffusion-3.5-large-turbo"],
            "video": ["stable-video-diffusion"],
        },
        endpoints={
            "image": "/stable-image/generate/core",
            "video": "/video/stable-video-diffusion",
        }
    ),
    
    "replicate": ProviderConfig(
        name="replicate",
        display_name="Replicate",
        base_url="https://api.replicate.com/v1",
        auth_type=AuthType.API_KEY,
        capabilities=[Capability.TEXT, Capability.IMAGE, Capability.VIDEO],
        langchain_class="langchain_community.llms.Replicate",
        models={
            "text": ["meta/llama-4-scout-17b-16e-instruct", "meta/llama-4-maverick-17b-128e-instruct"],
            "image": ["black-forest-labs/flux-1.1-pro", "black-forest-labs/flux-schnell", "stability-ai/sdxl"],
            "video": ["wan-video/wan-2.1-t2v-480p", "THUDM/cogvideox-5b"],
        },
        endpoints={
            "predictions": "/predictions",
        }
    ),
    
    # ======================== 国内厂商 ========================
    
    "zhipu": ProviderConfig(
        name="zhipu",
        display_name="智谱 AI",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        auth_type=AuthType.API_KEY,
        capabilities=[Capability.TEXT, Capability.IMAGE, Capability.VIDEO],
        # 智谱官方 OpenAI 兼容接口，旧 ChatZhipuAI 适配器已弃用
        langchain_class="langchain_openai.ChatOpenAI",
        models={
            "text": ["glm-5.1", "glm-5", "glm-5-turbo", "glm-4.7", "glm-4.6", "glm-4.5", "glm-4-plus", "glm-4-air", "glm-4-flash"],
            "image": ["cogview-4", "cogview-3-plus"],
            "video": ["cogvideox-3", "cogvideox"],
        },
        endpoints={
            "chat": "/chat/completions",
            "image": "/images/generations",
            "video": "/videos/generations",
        }
    ),
    
    "qwen": ProviderConfig(
        name="qwen",
        display_name="阿里通义",
        # 阿里百炼 OpenAI 兼容模式（北京地域）；旧 dashscope/api/v1 + ChatTongyi 已弃用
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        auth_type=AuthType.API_KEY,
        capabilities=[Capability.TEXT, Capability.IMAGE, Capability.VIDEO],
        langchain_class="langchain_openai.ChatOpenAI",
        models={
            "text": ["qwen3.7-max", "qwen3-max", "qwen-max", "qwen3.7-plus", "qwen-plus", "qwen3.7-flash", "qwen-turbo", "qwen3-coder-plus", "qwen3-coder-flash"],
            "image": ["wanx2.1-t2i-turbo", "wanx2.1-t2i-plus"],
            "video": ["wanx2.1-t2v-turbo", "wanx2.1-t2v-plus"],
        },
        endpoints={
            "chat": "/chat/completions",
            "image": "/images/generations",
            "video": "/video/generations",
        }
    ),
    
    "baidu": ProviderConfig(
        name="baidu",
        display_name="百度文心",
        # 千帆 ModelBuilder OpenAI 兼容模式（2026），单 API Key（bce-v3/ALTAK-xxx）
        base_url="https://qianfan.baidubce.com/v2",
        auth_type=AuthType.API_KEY,
        capabilities=[Capability.TEXT, Capability.IMAGE],
        langchain_class="langchain_openai.ChatOpenAI",
        models={
            "text": ["ernie-5.1", "ernie-5.0", "ernie-4.5-turbo-128k", "ernie-4.5-8k"],
            "image": ["ernie-4.5-turbo-128k"],
        },
        endpoints={
            "chat": "/chat/completions",
            "image": "/images/generations",
        }
    ),
    
    "doubao": ProviderConfig(
        name="doubao",
        display_name="火山引擎/豆包",
        # 火山方舟 OpenAI 兼容接口；注意模型 ID 可能是控制台"推理接入点"（ep-xxx）
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        auth_type=AuthType.API_KEY,
        capabilities=[Capability.TEXT, Capability.IMAGE, Capability.VIDEO],
        langchain_class=None,  # 需自定义
        models={
            "text": [
                "doubao-seed-2.0-mini", "doubao-seed-2.0-lite", "doubao-seed-2.0-code",
                "doubao-seed-1.6",
            ],
            "image": [
                "doubao-seedream-5.0-pro", "doubao-seedream-5.0-lite", "doubao-seedream-4.5",
            ],
            "video": [
                "doubao-seedance-2.0", "doubao-seedance-2.0-fast", "doubao-seedance-1.5-pro",
            ],
        },
        endpoints={
            "chat": "/chat/completions",
            "image": "/images/generations",
            "video": "/videos/generations",
        }
    ),
    
    "hunyuan": ProviderConfig(
        name="hunyuan",
        display_name="腾讯混元",
        # 混元开放平台 OpenAI 兼容接口（2026），单 API Key；旧腾讯云 Action 协议已弃用
        base_url="https://api.hunyuan.cloud.tencent.com/v1",
        auth_type=AuthType.API_KEY,
        capabilities=[Capability.TEXT, Capability.IMAGE],
        langchain_class="langchain_openai.ChatOpenAI",
        models={
            "text": ["hunyuan-t1-latest", "hunyuan-turbo-s-latest", "hunyuan-pro-latest", "hunyuan-standard-latest", "hunyuan-lite-latest"],
            "image": ["hunyuan-image-latest"],
        },
        endpoints={
            "chat": "/chat/completions",
            "image": "/images/generations",
        }
    ),
    
    "minimax": ProviderConfig(
        name="minimax",
        display_name="MiniMax",
        # 新版开放平台（2026）：OpenAI 兼容接口，域名 api.minimaxi.com（国内）
        base_url="https://api.minimaxi.com/v1",
        auth_type=AuthType.API_KEY,
        capabilities=[Capability.TEXT, Capability.VIDEO, Capability.AUDIO],
        # MiniMaxChat 适配器已过时（旧域名+旧协议），新版走 OpenAI 兼容接口
        langchain_class="langchain_openai.ChatOpenAI",
        models={
            "text": ["MiniMax-M3", "MiniMax-M2.7", "MiniMax-M2.7-highspeed", "MiniMax-Text-01"],
            "video": ["MiniMax-Hailuo-2.3", "MiniMax-Hailuo-2.3-Fast", "MiniMax-Hailuo-02", "I2V-01"],
            "audio": ["speech-2.8-hd", "speech-2.6-hd", "speech-01", "speech-02"],
        },
        endpoints={
            "chat": "/chat/completions",
            "video": "/video_generation",
            "audio": "/t2a_v2",
        }
    ),
    
    "spark": ProviderConfig(
        name="spark",
        display_name="讯飞星火",
        # 星火 HTTP OpenAI 兼容接口（2026），Bearer APIKey；旧 WebSocket 三元组保留在 chat/providers/spark.py
        base_url="https://spark-api-open.xf-yun.com/v1",
        auth_type=AuthType.API_KEY,
        capabilities=[Capability.TEXT],
        langchain_class="langchain_openai.ChatOpenAI",
        models={
            "text": ["4.0ultra", "max", "pro", "lite"],
        },
        endpoints={
            "chat": "/chat/completions",
        }
    ),
    
    "moonshot": ProviderConfig(
        name="moonshot",
        display_name="月之暗面",
        base_url="https://api.moonshot.cn/v1",
        auth_type=AuthType.API_KEY,
        capabilities=[Capability.TEXT],
        # Moonshot 官方 OpenAI 兼容，旧 MoonshotChat 适配器已过时
        langchain_class="langchain_openai.ChatOpenAI",
        models={
            "text": ["kimi-k3", "kimi-k2.7-code", "kimi-k2.6", "kimi-k2.5"],
        },
        endpoints={
            "chat": "/chat/completions",
        }
    ),
    
    "deepseek": ProviderConfig(
        name="deepseek",
        display_name="DeepSeek",
        base_url="https://api.deepseek.com",
        auth_type=AuthType.API_KEY,
        capabilities=[Capability.TEXT],
        langchain_class="langchain_openai.ChatOpenAI",  # OpenAI 兼容接口
        models={
            # V4 系列（2026-04 发布）；deepseek-chat/reasoner 已于 2026-07-24 退役（自动迁移）
            "text": ["deepseek-v4-flash", "deepseek-v4-pro"],
        },
        endpoints={
            "chat": "/chat/completions",
        }
    ),
    
    "baichuan": ProviderConfig(
        name="baichuan",
        display_name="百川",
        base_url="https://api.baichuan-ai.com/v1",
        auth_type=AuthType.API_KEY,
        capabilities=[Capability.TEXT],
        # 百川官方 OpenAI 兼容，旧 ChatBaichuan 适配器已过时
        langchain_class="langchain_openai.ChatOpenAI",
        models={
            "text": ["Baichuan-M3", "Baichuan-M2", "Baichuan-M1"],
        },
        endpoints={
            "chat": "/chat/completions",
        }
    ),
    
    # ======================== 开源模型平台 ========================
    
    "huggingface": ProviderConfig(
        name="huggingface",
        display_name="Hugging Face",
        # 2026 官方推荐 AI Inference Router（OpenAI 兼容，仅 chat）；图片走专用 Inference API
        base_url="https://router.huggingface.co/v1",
        auth_type=AuthType.API_KEY,
        capabilities=[Capability.TEXT, Capability.IMAGE, Capability.VIDEO],
        langchain_class=None,  # 需自定义实现（使用OpenAI兼容接口）
        models={
            "text": [
                "Qwen/Qwen3-32B",
                "Qwen/Qwen3-8B",
                "deepseek-ai/DeepSeek-R1",
                "meta-llama/Llama-3.3-70B-Instruct",
                "meta-llama/Llama-3.1-8B-Instruct",
                "mistralai/Mistral-7B-Instruct-v0.3",
            ],
            "image": [
                "stabilityai/stable-diffusion-xl-base-1.0",
                "stabilityai/sdxl-turbo",
            ],
            "video": [
                "stabilityai/stable-video-diffusion-img2vid-xt",
                "stabilityai/stable-video-diffusion-img2vid",
                "cerspense/zeroscope_v2_576w",
            ],
        },
        endpoints={
            "chat": "/chat/completions",
            "image": "/models/{model_id}",
            "video": "/models/{model_id}",
        }
    ),
    
    "modelscope": ProviderConfig(
        name="modelscope",
        display_name="ModelScope",
        base_url="https://api-inference.modelscope.cn/v1",
        auth_type=AuthType.API_KEY,
        capabilities=[Capability.TEXT, Capability.IMAGE, Capability.VIDEO],
        langchain_class=None,  # 需自定义实现（使用OpenAI兼容接口）
        models={
            "text": [
                "Qwen/Qwen3-32B",
                "Qwen/Qwen3-8B",
                "Qwen/Qwen3-VL-8B-Instruct",
            ],
            "image": [
                "Tongyi-MAI/Z-Image-Turbo",
                "stabilityai/stable-diffusion-xl-base-1.0",
            ],
            "video": [
                "iic/text-to-video-synthesis",
            ],
        },
        endpoints={
            "chat": "/chat/completions",
            "image": "/models/{model_id}",
            "video": "/models/{model_id}",
        }
    ),
    
    "leonardo": ProviderConfig(
        name="leonardo",
        display_name="Leonardo AI",
        base_url="https://cloud.leonardo.ai/api/rest/v1",
        auth_type=AuthType.API_KEY,
        capabilities=[Capability.IMAGE],
        langchain_class=None,  # 需自定义实现
        models={
            "image": [
                "leonardo-phoenix",
                "leonardo-lightning-xl",
                "leonardo-kinexl",
                "leonardo-diffusion-xl",
                "sd-1.5",
                "playground-v2-5",
            ],
        },
        endpoints={
            "image": "/generations",
        }
    ),
}


# ============================================================================
# 辅助函数
# ============================================================================

def get_provider_config(provider: str) -> Optional[ProviderConfig]:
    """获取厂商配置"""
    return PROVIDERS.get(provider.lower())


def get_providers_by_capability(capability: Capability) -> List[str]:
    """获取支持特定能力的厂商列表"""
    return [
        name for name, config in PROVIDERS.items()
        if capability in config.capabilities
    ]


def get_all_providers() -> Dict[str, ProviderConfig]:
    """获取所有厂商配置"""
    return PROVIDERS.copy()


def get_text_providers() -> List[str]:
    """获取支持文本生成的厂商"""
    return get_providers_by_capability(Capability.TEXT)


def get_image_providers() -> List[str]:
    """获取支持图片生成的厂商"""
    return get_providers_by_capability(Capability.IMAGE)


def get_video_providers() -> List[str]:
    """获取支持视频生成的厂商"""
    return get_providers_by_capability(Capability.VIDEO)


def get_default_model(provider: str, capability: str = "text") -> Optional[str]:
    """获取厂商的默认模型"""
    config = get_provider_config(provider)
    if config and capability in config.models and config.models[capability]:
        return config.models[capability][0]
    return None


def get_endpoint(provider: str, capability: str) -> Optional[str]:
    """获取厂商特定能力的端点"""
    config = get_provider_config(provider)
    if config and capability in config.endpoints:
        return config.endpoints[capability]
    return None


# ============================================================================
# 厂商分组信息（用于前端展示）
# ============================================================================

PROVIDER_GROUPS = {
    "international": {
        "name": "国际厂商",
        "providers": ["openai", "anthropic", "google", "stability", "replicate", "leonardo"]
    },
    "domestic": {
        "name": "国内厂商",
        "providers": ["zhipu", "qwen", "baidu", "doubao", "hunyuan", "minimax", "spark", "moonshot", "deepseek", "baichuan"]
    },
    "opensource": {
        "name": "开源模型平台",
        "providers": ["huggingface", "modelscope"]
    }
}


# ============================================================================
# 能力说明
# ============================================================================

CAPABILITY_INFO = {
    Capability.TEXT: {
        "name": "文本生成",
        "description": "生成文本内容，支持对话和创作",
        "providers_count": len(get_text_providers())
    },
    Capability.IMAGE: {
        "name": "图片生成",
        "description": "根据文本描述生成图片",
        "providers_count": len(get_image_providers())
    },
    Capability.VIDEO: {
        "name": "视频生成",
        "description": "根据文本描述或图片生成视频",
        "providers_count": len(get_video_providers())
    },
    Capability.AUDIO: {
        "name": "音频生成",
        "description": "文本转语音、音乐生成等",
        "providers_count": len(get_providers_by_capability(Capability.AUDIO))
    }
}
