"""
AI写作相关API路由
"""
from typing import Any, List, Optional
import logging

from fastapi import APIRouter, Body, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.exceptions import BusinessException
from app.models.user import User
from app.models.creation import Creation, CreationVersion
from app.models.ai_model import AIModel
from app.schemas.creation import (
    WritingToolInfo,
    CreationGenerate as WritingGenerateRequest,
    CreationRegenerate as WritingRegenerateRequest,
    CreationOptimize as WritingOptimizeRequest,
    CreationResponse as WritingGenerateResponse,
    CreationResponse,
    CreationListResponse,
)
from app.services.writing_service import WritingService
from app.services.credit_service import CreditService
from app.models.credit import TransactionType

logger = logging.getLogger(__name__)
router = APIRouter()

# 工具类型 -> creations.creation_type（ENUM 枚举值）映射
TOOL_CREATION_TYPE = {
    "wechat_article": "WECHAT_ARTICLE",
    "xiaohongshu_note": "XIAOHONGSHU_NOTE",
    "official_document": "OFFICIAL_DOCUMENT",
    "academic_paper": "PAPER",
    "marketing_copy": "MARKETING_COPY",
    "press_release": "NEWS_ARTICLE",
    "news_article": "NEWS_ARTICLE",
    "video_script": "VIDEO_SCRIPT",
    "story_novel": "STORY",
    "business_plan": "BUSINESS_PLAN",
    "work_report": "WORK_REPORT",
    "resume": "RESUME",
    "resume_cover_letter": "RESUME",
    "lesson_plan": "LESSON_PLAN",
    "rewrite": "REWRITE",
    "content_rewrite": "REWRITE",
    "translation": "TRANSLATION",
}


def map_creation_type(tool_type: str) -> str:
    """将写作工具类型映射为 creations.creation_type 的 ENUM 值"""
    creation_type = TOOL_CREATION_TYPE.get(tool_type)
    if not creation_type:
        raise ValueError(f"不支持的写作工具类型: {tool_type}")
    return creation_type


@router.get("/tools", response_model=List[WritingToolInfo])
def get_writing_tools(db: Session = Depends(get_db)) -> Any:
    """
    获取所有写作工具列表
    """
    usage_rows = (
        db.query(Creation.tool_type, func.count(Creation.id))
        .filter(Creation.tool_type.isnot(None), Creation.deleted_at.is_(None))
        .group_by(Creation.tool_type)
        .all()
    )
    usage_map = {tool_type: count for tool_type, count in usage_rows}

    tools = [
        {
            "tool_type": "wechat_article",
            "name": "公众号文章",
            "description": "创作适合微信公众号的文章，自动优化排版和SEO",
            "icon": "📱",
            "category": "social_media",
        },
        {
            "tool_type": "xiaohongshu_note",
            "name": "小红书笔记",
            "description": "创作吸引人的小红书笔记，包含标题、正文和标签",
            "icon": "📔",
            "category": "social_media",
        },
        {
            "tool_type": "official_document",
            "name": "公文写作",
            "description": "撰写规范的公文，包括通知、报告、函等",
            "icon": "📄",
            "category": "professional",
        },
        {
            "tool_type": "academic_paper",
            "name": "论文写作",
            "description": "撰写学术论文，包含摘要、正文、参考文献",
            "icon": "🎓",
            "category": "academic",
        },
        {
            "tool_type": "marketing_copy",
            "name": "营销文案",
            "description": "创作吸引人的营销文案，提升转化率",
            "icon": "💰",
            "category": "marketing",
        },
        {
            "tool_type": "news_article",
            "name": "新闻稿/软文",
            "description": "撰写专业的新闻稿或软文",
            "icon": "📰",
            "category": "media",
        },
        {
            "tool_type": "video_script",
            "name": "短视频脚本",
            "description": "创作短视频脚本，包含场景、台词、镜头",
            "icon": "🎬",
            "category": "media",
        },
        {
            "tool_type": "story_novel",
            "name": "故事/小说",
            "description": "创作引人入胜的故事或小说",
            "icon": "📖",
            "category": "creative",
        },
        {
            "tool_type": "business_plan",
            "name": "商业计划书",
            "description": "撰写完整的商业计划书",
            "icon": "💼",
            "category": "business",
        },
        {
            "tool_type": "work_report",
            "name": "工作报告",
            "description": "撰写工作总结、述职报告等",
            "icon": "📊",
            "category": "professional",
        },
        {
            "tool_type": "resume",
            "name": "简历/求职信",
            "description": "创作专业的简历和求职信",
            "icon": "👔",
            "category": "career",
        },
        {
            "tool_type": "lesson_plan",
            "name": "教案/课件",
            "description": "制作教学教案和课件内容",
            "icon": "👨‍🏫",
            "category": "education",
        },
        {
            "tool_type": "rewrite",
            "name": "内容改写/扩写/缩写",
            "description": "对现有内容进行改写、扩写或缩写",
            "icon": "✏️",
            "category": "editing",
        },
        {
            "tool_type": "translation",
            "name": "多语言翻译",
            "description": "将内容翻译成多种语言",
            "icon": "🌐",
            "category": "language",
        },
        {
            "tool_type": "viral_analyze",
            "name": "爆款分析",
            "description": "深度拆解爆款文章的成功要素，提取写作技巧和爆款元素",
            "icon": "📊",
            "category": "creative",
        },
        {
            "tool_type": "viral_imitate",
            "name": "爆款模仿",
            "description": "参考爆款文章风格，围绕新主题生成类似风格内容",
            "icon": "📈",
            "category": "creative",
        },
    ]
    for tool in tools:
        tool["usage_count"] = usage_map.get(tool["tool_type"], 0)
    return tools


@router.post("/generate", response_model=WritingGenerateResponse)
async def generate_content(
    request: WritingGenerateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    生成AI写作内容
    支持两种模式：
    1. API Key模式：提供model_id，系统使用配置的API Key
    """
    # 检查并扣减积分（会员不扣积分）
    credits_required = 10  # 每次生成需要10积分
    
    try:
        CreditService.check_and_consume_credits(
            db=db,
            user_id=current_user.id,
            amount=credits_required,
            description=f"AI写作 - {request.tool_type}"
        )
    except BusinessException as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=e.detail,
        )
    
    try:
        # 判断使用哪种模式
        if request.platform:
            # Cookie模式
            logger.info(f"Using Cookie mode for platform: {request.platform}")
            content = await WritingService.generate_content_with_cookie(
                db=db,
                user_id=current_user.id,
                tool_type=request.tool_type,
                user_input=request.parameters or {},
                platform=request.platform,
            )
        else:
            # API Key模式（原有方式）
            logger.info(f"Using API Key mode with model_id: {request.model_id}")
            
            # 获取AI模型
            if not request.model_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="请选择AI模型或指定平台",
                )
            
            ai_model = db.query(AIModel).filter(
                AIModel.id == request.model_id,
                AIModel.user_id == current_user.id
            ).first()
            
            if not ai_model:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="AI模型不存在或无权访问",
                )
            
            # 检查是否启用了插件
            if request.enabled_plugins:
                # 使用带插件的生成方法
                logger.info(f"Using plugins: {request.enabled_plugins}")
                result = await WritingService.generate_content_with_plugins(
                    db=db,
                    tool_type=request.tool_type,
                    user_input=request.parameters or {},
                    ai_model=ai_model,
                    enabled_plugins=request.enabled_plugins,
                    user_id=current_user.id,
                )
                content = result["content"]
                # 可以在 extra_data 中保存插件调用信息
                plugin_info = {
                    "plugin_invocations": result.get("plugin_invocations", []),
                    "usage": result.get("usage", {})
                }
            else:
                # 普通生成
                content = await WritingService.generate_content(
                    db=db,
                    tool_type=request.tool_type,
                    user_input=request.parameters or {},
                    ai_model=ai_model,
                )
                plugin_info = None
        
        # 创建创作记录
        extra_data = {}
        if plugin_info:
            extra_data["plugin_info"] = plugin_info
        
        creation = Creation(
            user_id=current_user.id,
            title=f"{request.tool_type} - {(request.parameters or {}).get('topic', '未命名')}",
            output_content=content,
            creation_type=map_creation_type(request.tool_type),
            tool_type=request.tool_type,
            input_data=request.parameters,
            extra_data=extra_data if extra_data else None,
            model_id=ai_model.id if not request.platform else None,
            status="completed",
        )
        db.add(creation)
        db.commit()
        db.refresh(creation)
        
        return creation
        
    except HTTPException:
        # 扣费成功后的业务失败（如模型不存在 404）也退还积分（D6）
        if not current_user.is_member:
            db.rollback()  # 先清理可能已回滚的事务，避免退款被同一会话错误掩盖
            CreditService.add_credits(
                db=db,
                user_id=current_user.id,
                amount=credits_required,
                transaction_type=TransactionType.REFUND,
                description="AI写作失败退款"
            )
        raise
    except Exception as e:
        logger.error(f"Content generation failed: {e}", exc_info=True)
        # 生成失败，退还积分
        if not current_user.is_member:
            db.rollback()
            CreditService.add_credits(
                db=db,
                user_id=current_user.id,
                amount=credits_required,
                transaction_type=TransactionType.REFUND,
                description=f"AI写作失败退款 - {request.tool_type}"
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成内容失败: {str(e)}",
        )


@router.get("/creations", response_model=CreationListResponse)
def get_creations(
    skip: int = 0,
    limit: int = 20,
    tool_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    获取创作列表
    """
    # 只查列表所需字段，避免加载 output_data 大字段导致 MySQL 排序内存超限
    query = db.query(
        Creation.id, Creation.user_id, Creation.title, Creation.creation_type,
        Creation.tool_type, Creation.status, Creation.output_content,
        Creation.created_at, Creation.updated_at,
    ).filter(Creation.user_id == current_user.id)
    
    if tool_type:
        query = query.filter(Creation.tool_type == tool_type)
    
    total = query.count()
    rows = query.order_by(Creation.created_at.desc()).offset(skip).limit(limit).all()
    creations = [dict(row._mapping) for row in rows]
    
    return {
        "total": total,
        "items": creations,
    }


@router.get("/creations/{creation_id}", response_model=CreationResponse)
def get_creation(
    creation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    获取创作详情
    """
    creation = db.query(Creation).filter(
        Creation.id == creation_id,
        Creation.user_id == current_user.id,
    ).first()
    
    if not creation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="创作不存在",
        )
    
    return creation


@router.put("/creations/{creation_id}", response_model=CreationResponse)
def update_creation(
    creation_id: int,
    title: Optional[str] = None,
    content: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    更新创作内容
    """
    creation = db.query(Creation).filter(
        Creation.id == creation_id,
        Creation.user_id == current_user.id,
    ).first()
    
    if not creation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="创作不存在",
        )
    
    # 保存版本历史
    if content and content != creation.content:
        version = CreationVersion(
            creation_id=creation.id,
            version_number=creation.version + 1,
            content=creation.content,
            extra_data=creation.extra_data,
        )
        db.add(version)
        creation.version += 1
    
    # 更新内容
    if title:
        creation.title = title
    if content:
        creation.content = content
    
    db.commit()
    db.refresh(creation)
    
    return creation


@router.delete("/creations/{creation_id}")
def delete_creation(
    creation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    删除创作
    """
    creation = db.query(Creation).filter(
        Creation.id == creation_id,
        Creation.user_id == current_user.id,
    ).first()
    
    if not creation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="创作不存在",
        )
    
    db.delete(creation)
    db.commit()
    
    return {"message": "删除成功"}


@router.get("/creations/{creation_id}/versions")
def get_creation_versions(
    creation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    获取创作版本历史
    """
    creation = db.query(Creation).filter(
        Creation.id == creation_id,
        Creation.user_id == current_user.id,
    ).first()
    
    if not creation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="创作不存在",
        )
    
    versions = db.query(CreationVersion).filter(
        CreationVersion.creation_id == creation_id
    ).order_by(CreationVersion.version_number.desc()).all()
    
    return versions


@router.post("/creations/{creation_id}/regenerate", response_model=WritingGenerateResponse)
async def regenerate_content(
    creation_id: int,
    request: Optional[WritingRegenerateRequest] = Body(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    重新生成内容
    """
    creation = db.query(Creation).filter(
        Creation.id == creation_id,
        Creation.user_id == current_user.id,
    ).first()
    
    if not creation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="创作不存在",
        )
    
    # 检查并扣减积分（会员不扣积分）
    credits_required = 10  # 每次生成需要10积分
    
    try:
        CreditService.check_and_consume_credits(
            db=db,
            user_id=current_user.id,
            amount=credits_required,
            description=f"AI写作重新生成 - {creation.tool_type}"
        )
    except BusinessException as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=e.detail,
        )
    
    try:
        # 获取AI模型
        ai_model = db.query(AIModel).filter(
            AIModel.id == creation.model_id,
            AIModel.user_id == current_user.id
        ).first()
        
        if not ai_model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="AI模型不存在或无权访问",
            )
        
        # 优先使用前端传入的当前表单参数（含补充说明），否则回退到已保存的输入数据
        input_data = (request.parameters if request and request.parameters else None) or (creation.input_data or {})
        content = await WritingService.generate_content(
            db=db,
            tool_type=creation.tool_type,
            user_input=input_data,
            ai_model=ai_model,
        )
        
        # 更新创作记录
        creation.output_content = content
        db.commit()
        db.refresh(creation)
        
        return creation
        
    except HTTPException:
        # 扣费成功后的业务失败（如模型不存在 404）也退还积分（D6）
        if not current_user.is_member:
            db.rollback()
            CreditService.add_credits(
                db=db,
                user_id=current_user.id,
                amount=credits_required,
                transaction_type=TransactionType.REFUND,
                description="AI写作失败退款"
            )
        raise
    except Exception as e:
        # 生成失败，退还积分
        if not current_user.is_member:
            db.rollback()
            CreditService.add_credits(
                db=db,
                user_id=current_user.id,
                amount=credits_required,
                transaction_type=TransactionType.REFUND,
                description=f"AI写作重新生成失败退款 - {creation.tool_type}"
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重新生成失败: {str(e)}",
        )


@router.post("/{creation_id}/optimize", response_model=WritingGenerateResponse)
async def optimize_content(
    creation_id: int,
    request: WritingOptimizeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    优化已生成内容

    支持优化类型：seo（SEO优化）、readability（可读性）、style（文风调整）、
    engagement（互动）、concise（精简）、expand（扩写）。
    可通过 optimize_types 传多个类型，将按顺序依次优化。
    """
    creation = db.query(Creation).filter(
        Creation.id == creation_id,
        Creation.user_id == current_user.id,
    ).first()

    if not creation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="创作不存在",
        )

    # 归一化优化类型（兼容单类型 optimization_type 与多类型 optimize_types）
    optimize_types = request.optimize_types or (
        [request.optimization_type] if request.optimization_type else []
    )
    if not optimize_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请选择优化类型",
        )

    # 检查并扣减积分（会员不扣积分）
    credits_required = 10  # 每次优化需要10积分

    try:
        CreditService.check_and_consume_credits(
            db=db,
            user_id=current_user.id,
            amount=credits_required,
            description=f"AI写作内容优化 - {creation.tool_type}",
        )
    except BusinessException as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=e.detail,
        )

    try:
        # 获取AI模型
        ai_model = db.query(AIModel).filter(
            AIModel.id == creation.model_id,
            AIModel.user_id == current_user.id,
        ).first()

        if not ai_model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="AI模型不存在或无权访问",
            )

        content = creation.output_content or ""
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="创作内容为空，无法优化",
            )

        # 多类型按顺序优化：上一次结果作为下一次输入
        for opt_type in optimize_types:
            content = await WritingService.optimize_content(
                db=db,
                content=content,
                optimization_type=opt_type,
                ai_model=ai_model,
                user_id=current_user.id,
            )

        # 更新创作记录
        creation.output_content = content
        db.commit()
        db.refresh(creation)

        return creation

    except HTTPException:
        # 扣费成功后的业务失败（如模型不存在 404）也退还积分（D6）
        if not current_user.is_member:
            db.rollback()
            CreditService.add_credits(
                db=db,
                user_id=current_user.id,
                amount=credits_required,
                transaction_type=TransactionType.REFUND,
                description="AI写作失败退款"
            )
        raise
    except ValueError as e:
        # 不支持的优化类型等业务错误，退还积分
        if not current_user.is_member:
            db.rollback()
            CreditService.add_credits(
                db=db,
                user_id=current_user.id,
                amount=credits_required,
                transaction_type=TransactionType.REFUND,
                description=f"AI写作优化失败退款 - {creation.tool_type}",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Content optimization failed: {e}", exc_info=True)
        # 优化失败，退还积分
        if not current_user.is_member:
            db.rollback()
            CreditService.add_credits(
                db=db,
                user_id=current_user.id,
                amount=credits_required,
                transaction_type=TransactionType.REFUND,
                description=f"AI写作优化失败退款 - {creation.tool_type}",
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"优化内容失败: {str(e)}",
        )


# ============================================================================
# URL 内容抓取
# ============================================================================

import ipaddress
import re
import socket
from typing import Tuple
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel


def _is_public_ip(ip_str: str) -> bool:
    """判断 IP 是否可对外访问（拒绝回环/私网/链路本地/保留/组播/未指定）"""
    try:
        ip = ipaddress.ip_address(ip_str.split("%")[0])
    except ValueError:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _resolve_public_ips(host: str) -> list:
    """解析主机所有地址；解析失败视为不可访问"""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise ValueError("域名解析失败，无法访问该地址")
    addrs = [info[4][0] for info in infos]
    if not addrs:
        raise ValueError("域名解析失败，无法访问该地址")
    return addrs


def validate_fetch_url(url: str) -> str:
    """SSRF 防护：仅允许公网 http/https，且解析结果必须为公网地址"""
    url = (url or "").strip()
    if not url:
        raise ValueError("请输入URL")
    # 协议白名单：识别显式 scheme（含 javascript:alert(1) 这类无 "://" 的写法）
    scheme_match = re.match(r"^([a-zA-Z][a-zA-Z0-9+.\-]*):", url)
    if scheme_match and scheme_match.group(1).lower() not in ("http", "https"):
        raise ValueError("仅支持 http/https 协议")
    if "://" not in url:
        url = "https://" + url
    parts = urlsplit(url)
    if parts.scheme.lower() not in ("http", "https"):
        raise ValueError("仅支持 http/https 协议")
    host = parts.hostname or ""
    if not host:
        raise ValueError("URL 缺少有效主机名")

    host_lower = host.lower()
    if host_lower in ("localhost", "localhost.localdomain") or host_lower.endswith(".localhost"):
        raise ValueError("禁止访问本机地址")

    # IP 字面量直接判断
    try:
        ip = ipaddress.ip_address(host_lower.split("%")[0])
    except ValueError:
        # 域名：解析后逐地址校验，防止解析到内网
        for addr in _resolve_public_ips(host):
            if not _is_public_ip(addr):
                raise ValueError("目标域名解析到内网/保留地址，已拦截")
    else:
        if not _is_public_ip(str(ip)):
            raise ValueError("禁止访问内网或保留地址")

    # 去掉 fragment，保留协议/主机/路径/查询
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


_FETCH_HEADERS_SET = [
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    },
    {
        # 备用 UA：部分站点对常见 Chrome UA 拦截
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.4 Safari/605.1.15"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
    },
]

_CONTENT_SELECTORS = [
    "article",
    '[role="main"]',
    ".article-content",
    ".post-content",
    ".entry-content",
    ".content",
    ".main-content",
    "#content",
    "#article",
    ".article",
    ".post",
    "main",
]


def _extract_page_content(html: str) -> Tuple[str, str]:
    """从 HTML 提取标题与正文文本"""
    soup = BeautifulSoup(html, "html.parser")

    title = (soup.title.string or "").strip() if soup.title else ""

    for tag in soup(
        ["script", "style", "nav", "header", "footer", "aside",
         "iframe", "noscript", "form", "button", "input", "svg"]
    ):
        tag.decompose()

    main_content = None
    for selector in _CONTENT_SELECTORS:
        main_content = soup.select_one(selector)
        if main_content:
            break
    if not main_content:
        main_content = soup.body or soup

    text_parts = []
    for element in main_content.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "pre", "blockquote"]):
        text = element.get_text(strip=True)
        if text and len(text) > 10:
            text_parts.append(text)

    content = re.sub(r"\n{3,}", "\n\n", "\n\n".join(text_parts)).strip()

    # 兜底：语义标签提取不到时，按文本密度从页面主体提取（兼容 SPA/div 布局）
    if len(content) < 80:
        lines = []
        for raw_line in (soup.get_text(separator="\n") or "").split("\n"):
            line = raw_line.strip()
            if len(line) > 10 and line not in lines:
                lines.append(line)
        dense_content = re.sub(r"\n{3,}", "\n\n", "\n\n".join(lines)).strip()
        if len(dense_content) > len(content):
            content = dense_content

    if len(content) > 10000:
        content = content[:10000] + "\n\n...(内容过长，已截断)"
    return title, content


def _decode_response(response: httpx.Response) -> str:
    """按响应头 charset 解码，避免中文乱码"""
    content_type = response.headers.get("content-type", "")
    if "charset=" in content_type:
        encoding = content_type.split("charset=")[-1].split(";")[0].strip()
        try:
            return response.content.decode(encoding, errors="ignore")
        except LookupError:
            pass
    return response.content.decode(response.encoding or "utf-8", errors="ignore")


async def _fetch_with_ssrf_guard(
    client: httpx.AsyncClient, url: str, headers: dict
) -> httpx.Response:
    """手动跟随重定向并逐跳校验（防重定向 SSRF）"""
    current = url
    for _ in range(5):
        current = validate_fetch_url(current)
        response = await client.get(
            current, headers=headers, follow_redirects=False, timeout=20.0
        )
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("location")
            if not location:
                return response
            current = urljoin(current, location)
            continue
        return response
    raise ValueError("重定向次数过多")


async def _fetch_static_html(url: str) -> Optional[str]:
    """静态抓取（含重定向校验与 UA 重试），失败抛异常"""
    async with httpx.AsyncClient(timeout=20.0) as client:
        last_error = None
        for headers in _FETCH_HEADERS_SET:
            try:
                response = await _fetch_with_ssrf_guard(client, url, headers)
                if response.status_code in (403, 429):
                    last_error = response
                    continue  # 换 UA 再试
                response.raise_for_status()
                return _decode_response(response)
            except httpx.HTTPStatusError as e:
                last_error = e
                continue
            except (httpx.TimeoutException, httpx.RequestError) as e:
                last_error = str(e)
                continue
        if isinstance(last_error, httpx.Response):
            raise httpx.HTTPStatusError(
                f"HTTP {last_error.status_code}",
                request=last_error.request,
                response=last_error,
            )
        if isinstance(last_error, httpx.HTTPStatusError):
            raise last_error
        raise ValueError(last_error or "抓取失败")


async def _fetch_rendered_html(url: str) -> Optional[str]:
    """无头浏览器渲染 JS 页面；失败返回 None（反爬降级）"""
    try:
        from playwright.async_api import async_playwright
    except Exception:
        return None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
            )
            try:
                page = await browser.new_page(
                    user_agent=_FETCH_HEADERS_SET[0]["User-Agent"],
                    viewport={"width": 1280, "height": 800},
                )
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2500)  # 等待 JS 渲染
                return await page.content()
            finally:
                await browser.close()
    except Exception as e:
        logger.warning(f"Playwright render failed: {e}")
        return None


class UrlFetchRequest(BaseModel):
    """URL抓取请求"""
    url: str

class UrlFetchResponse(BaseModel):
    """URL抓取响应"""
    success: bool
    title: str = ""
    content: str = ""
    error: str = ""

@router.post("/fetch-url", response_model=UrlFetchResponse)
async def fetch_url_content(
    request: UrlFetchRequest,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    抓取URL内容

    从给定的URL抓取网页内容，提取正文文本。
    用于内容改写/扩写/缩写功能。

    安全与兼容性：
    - SSRF 防护：仅允许公网 http/https，拒绝内网/回环/保留地址，重定向逐跳校验
    - 反爬增强：完整浏览器请求头 + UA 重试；静态抓取失败或内容为空时，
      自动降级为无头浏览器渲染 JS 页面后再提取
    """
    try:
        url = validate_fetch_url(request.url)
    except ValueError as e:
        return UrlFetchResponse(success=False, error=str(e))

    html = None
    try:
        html = await _fetch_static_html(url)
    except httpx.TimeoutException:
        return UrlFetchResponse(success=False, error="请求超时，请检查URL是否可访问")
    except httpx.HTTPStatusError as e:
        # 403/429 等反爬拦截时降级为无头浏览器渲染
        if e.response.status_code not in (403, 429):
            return UrlFetchResponse(success=False, error=f"HTTP错误: {e.response.status_code}")
    except httpx.RequestError as e:
        return UrlFetchResponse(success=False, error=f"抓取失败: {str(e)}")
    except ValueError as e:
        return UrlFetchResponse(success=False, error=str(e))
    except Exception as e:
        logger.error(f"URL fetch error: {e}", exc_info=True)
        return UrlFetchResponse(success=False, error=f"抓取失败: {str(e)}")

    title, content = _extract_page_content(html) if html else ("", "")

    # 静态抓取内容为空、标题为空（JS 动态写入）或反爬被拦截 → 无头浏览器渲染后再提取
    if not content or not title:
        rendered_html = await _fetch_rendered_html(url)
        if rendered_html:
            title, content = _extract_page_content(rendered_html)

    if not content:
        return UrlFetchResponse(success=False, error="无法从该页面提取有效内容")

    return UrlFetchResponse(success=True, title=title, content=content)
