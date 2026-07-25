"""
AI模型配置数据模型
"""
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, BigInteger, JSON, Index, ForeignKey
from sqlalchemy.orm import relationship, foreign
from datetime import datetime

from app.core.database import Base
from app.models.user import User


class AIModel(Base):
    """AI模型配置表"""
    __tablename__ = "ai_models"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True, comment="模型ID")
    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="用户ID（FK→users.id，删除用户时级联）"
    )
    name = Column(String(100), nullable=False, comment="模型名称")
    provider = Column(String(50), nullable=False, comment="提供商(openai/anthropic/zhipu/baidu/ali/tencent)")
    model_name = Column(String(100), nullable=False, comment="模型标识")
    api_key = Column(Text, nullable=False, comment="API密钥(加密存储)")
    base_url = Column(String(255), nullable=True, comment="API基础URL")
    is_default = Column(Boolean, default=False, comment="是否为默认模型")
    is_active = Column(Boolean, default=True, comment="是否启用")
    is_system_builtin = Column(Boolean, default=False, comment="是否系统内置模型")
    description = Column(Text, nullable=True, comment="模型描述")
    capabilities = Column(JSON, default=["text"], comment="模型能力列表(text/image/video/audio)")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # 关系（用真实外键）
    user = relationship("User", back_populates="ai_models")
    creations = relationship("Creation", back_populates="model")

    def __repr__(self):
        return f"<AIModel(id={self.id}, name='{self.name}', provider='{self.provider}')>"


# 索引
__table_args__ = (
    Index("idx_system_builtin_user", "is_system_builtin", "user_id"),
)
