# -*- coding: utf-8 -*-
"""管理员操作审计日志模型"""
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, JSON
from sqlalchemy.sql import func

from app.core.database import Base


class AdminAuditLog(Base):
    """管理员操作审计日志表"""
    __tablename__ = "admin_audit_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="日志ID")
    user_id = Column(BigInteger, nullable=True, index=True, comment="操作管理员用户ID")
    username = Column(String(50), nullable=True, index=True, comment="操作管理员用户名")
    method = Column(String(10), nullable=False, comment="HTTP方法")
    path = Column(String(255), nullable=False, index=True, comment="请求路径")
    status_code = Column(Integer, nullable=False, comment="响应状态码")
    detail = Column(JSON, comment="操作详情（可空）")
    client_ip = Column(String(64), comment="客户端IP")
    created_at = Column(DateTime, server_default=func.now(), comment="操作时间")
