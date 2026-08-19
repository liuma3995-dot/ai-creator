"""
应用配置
"""
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


# 确定.env文件的位置
def get_env_file_path() -> str:
    """
    智能查找.env文件路径
    支持从项目根目录或backend目录运行
    """
    # 当前文件所在目录
    current_file = Path(__file__).resolve()
    backend_dir = current_file.parent.parent.parent  # backend/app/core -> backend
    
    # 尝试backend/.env
    env_file = backend_dir / ".env"
    if env_file.exists():
        return str(env_file)
    
    # 尝试当前工作目录的.env
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists():
        return str(cwd_env)
    
    # 尝试backend目录下的.env（相对路径）
    relative_env = Path("backend/.env")
    if relative_env.exists():
        return str(relative_env)
    
    # 默认返回backend/.env
    return str(env_file)


class Settings(BaseSettings):
    """应用配置类"""
    
    # 应用基本信息
    APP_NAME: str = "AI创作者平台"
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    
    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    
    # 数据库配置
    DATABASE_URL: str = Field(
        default="mysql+pymysql://root:123456@localhost:3306/ai_creator",
        description="数据库连接URL"
    )
    
    # Redis配置
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis连接URL"
    )
    REDIS_PASSWORD: Optional[str] = Field(
        default=None,
        description="Redis密码"
    )
    
    # JWT配置
    SECRET_KEY: str = Field(
        default="your-secret-key-change-in-production",
        description="JWT密钥"
    )
    ALGORITHM: str = "HS256"
    PAYMENT_CALLBACK_SECRET: str = Field(
        default="change-me-payment-callback-secret",
        description="支付回调签名密钥（网关回调校验用）"
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120  # 2小时
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # 7天
    # 管理端令牌（T1 安全加固）：独立、更短有效期，生产建议单独设置 ADMIN_SECRET_KEY
    ADMIN_TOKEN_EXPIRE_MINUTES: int = 30  # 管理端访问令牌30分钟
    ADMIN_SECRET_KEY: Optional[str] = None  # 为空时与 SECRET_KEY 共用，生产建议独立设置
    ADMIN_IP_WHITELIST: list = Field(
        default_factory=list,
        description="管理接口IP白名单（如 ['1.2.3.4', '10.0.0.0/8']），空列表表示不限制",
    )
    
    # CORS配置
    CORS_ORIGINS: list = Field(
        default=[
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
        ]
    )
    
    # 文件上传配置
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: set = {".jpg", ".jpeg", ".png", ".gif", ".pdf", ".docx"}
    
    # AI服务配置
    DEFAULT_AI_PROVIDER: str = "openai"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_API_BASE: str = "https://api.openai.com/v1"
    ANTHROPIC_API_KEY: Optional[str] = None
    ZHIPU_API_KEY: Optional[str] = None
    BAIDU_API_KEY: Optional[str] = None
    BAIDU_SECRET_KEY: Optional[str] = None
    
    # Celery配置
    CELERY_BROKER_URL: str = Field(
        default="redis://localhost:6379/1",
        description="Celery消息代理URL"
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/2",
        description="Celery结果后端URL"
    )
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"
    
    # 限流配置
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60
    # 登录限流与失败锁定（T4）
    LOGIN_RATE_LIMIT_ENABLED: bool = True
    LOGIN_RATE_LIMIT_PER_MINUTE: int = 10
    ADMIN_LOGIN_RATE_LIMIT_PER_MINUTE: int = 5
    LOGIN_FAIL_LOCK_THRESHOLD: int = 5
    LOGIN_LOCK_MINUTES: int = 15
    
    # 平台发布配置
    WECHAT_APP_ID: Optional[str] = None
    WECHAT_APP_SECRET: Optional[str] = None
    
    # OAuth加密配置
    OAUTH_ENCRYPTION_KEY: str = Field(
        default="your-oauth-encryption-key-change-in-production",
        description="OAuth凭据加密密钥"
    )
    
    # 数据库初始化配置
    AUTO_CREATE_TABLES: bool = Field(
        default=True,
        description="启动时自动创建数据库表"
    )
    # API 文档开关（T4）：None = 跟随 DEBUG（开发开、生产关）；true/false 强制开/关
    ENABLE_API_DOCS: Optional[bool] = None

# 获取.env文件路径
_env_file_path = get_env_file_path()
print(f"[CONFIG] Loading environment from: {_env_file_path}")

# 创建全局配置实例 - 在Pydantic v2中，通过环境变量或实例化前设置Config
class _Settings(Settings):
    """内部Settings类，用于动态设置env_file"""
    model_config = SettingsConfigDict(
        env_file=_env_file_path,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = _Settings()


# 已知不安全默认值：生产环境（DEBUG=False）检测到这些值直接拒绝启动（T3）
INSECURE_DEFAULT_SECRETS = {
    "your-secret-key-change-in-production",
    "change-me-payment-callback-secret",
    "your-oauth-encryption-key-change-in-production",
}


def validate_production_settings(cfg: Settings = settings) -> None:
    """生产环境安全校验：默认/空密钥直接拒绝启动，避免弱配置上线（T3）"""
    if cfg.DEBUG:
        return
    insecure = {
        "SECRET_KEY": cfg.SECRET_KEY,
        "PAYMENT_CALLBACK_SECRET": cfg.PAYMENT_CALLBACK_SECRET,
        "OAUTH_ENCRYPTION_KEY": cfg.OAUTH_ENCRYPTION_KEY,
    }
    bad = [
        name
        for name, value in insecure.items()
        if not value or value in INSECURE_DEFAULT_SECRETS
    ]
    if bad:
        raise ValueError(
            "生产环境检测到未配置的安全密钥（{}），请在 .env 中设置强随机值后重新启动".format(
                ", ".join(bad)
            )
        )


def resolve_docs_enabled(enable: Optional[bool], debug: bool) -> bool:
    """API 文档开关解析（T4）：None 跟随 DEBUG，显式值优先"""
    if enable is not None:
        return enable
    return debug
