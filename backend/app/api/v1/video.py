"""
视频生成API
"""
from typing import Optional
import uuid
import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
import logging

from app.core.database import get_db
from app.models.user import User
from app.models.creation import Creation
from app.models.credit import CreditTransaction, TransactionType
from app.schemas.common import success_response
from app.utils.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


def _refund_creation(db, creation, description: str):
    """生成失败时退还该创作已扣的积分（无扣费记录则无操作）"""
    from app.services.credit_service import CreditService
    CreditService.refund_creation_credits(db, creation.id, description)


def _consume_credits(db, user_id: int, amount: int, description: str, creation_id: int):
    """统一消费入口：会员不扣积分，非会员延迟提交（随业务记录一起 commit）"""
    from app.core.exceptions import BusinessException
    from app.services.credit_service import CreditService
    try:
        CreditService.check_and_consume_credits(
            db=db,
            user_id=user_id,
            amount=amount,
            description=description,
            related_id=creation_id,
            related_type="creation",
            commit=False,
        )
    except BusinessException as e:
        db.rollback()
        raise HTTPException(status_code=402, detail=e.detail)


class VideoGenerateRequest(BaseModel):
    """视频生成请求"""
    prompt: str
    duration: int = 5
    fps: int = 30
    resolution: str = "1080p"
    platform: Optional[str] = None  # 支持Cookie模式


class TextToVideoRequest(BaseModel):
    """文本转视频请求"""
    text: str
    model_id: Optional[int] = None
    voice: Optional[str] = None
    background_music: bool = False
    subtitle: bool = True
    duration: int = 6
    resolution: str = "768P"
    platform: Optional[str] = None  # 支持Cookie模式


class ImageToVideoRequest(BaseModel):
    """图片转视频请求"""
    images: list[str]
    model_id: Optional[int] = None
    transition: str = "fade"
    duration_per_image: int = 3
    motion_prompt: Optional[str] = None
    duration: int = 6
    resolution: str = "768P"
    platform: Optional[str] = None  # 支持Cookie模式


class VideoTaskResponse(BaseModel):
    """视频任务响应"""
    task_id: str
    status: str
    video_url: Optional[str] = None
    script: Optional[str] = None
    progress: Optional[int] = None
    error: Optional[str] = None


# 视频存储目录
VIDEO_STORAGE_DIR = "uploads/videos"


def save_video_from_url(url: str, filename: str = None) -> str:
    """
    下载视频到本地存储，返回保存后的URL

    Args:
        url: 视频下载地址（临时链接）
        filename: 可选的文件名

    Returns:
        保存后的URL路径
    """
    import os
    import httpx

    os.makedirs(VIDEO_STORAGE_DIR, exist_ok=True)
    if not filename:
        filename = f"video_{uuid.uuid4().hex[:12]}.mp4"
    if not filename.lower().endswith((".mp4", ".webm", ".mov", ".mkv")):
        filename = f"{filename}.mp4"

    filepath = os.path.join(VIDEO_STORAGE_DIR, filename)
    response = httpx.get(url, timeout=180.0, follow_redirects=True)
    response.raise_for_status()
    with open(filepath, "wb") as f:
        f.write(response.content)
    return f"/uploads/videos/{os.path.basename(filepath)}"


def _resolve_video_model(db: Session, user_id: int, requested_model_id: Optional[int] = None):
    """解析用户启用的视频生成模型：优先前端选择，未传则取第一个"""
    from app.models.ai_model import AIModel

    active_models = (
        db.query(AIModel)
        .filter(AIModel.user_id == user_id, AIModel.is_active == True)
        .all()
    )
    # capabilities 是 JSON 数组，Python 侧过滤（不能用 SQL contains 做子串匹配）
    video_models = [m for m in active_models if "video" in (m.capabilities or [])]

    if requested_model_id:
        ai_model = next((m for m in video_models if m.id == requested_model_id), None)
        if not ai_model:
            raise ValueError("所选模型不存在、未启用或不支持视频生成")
    else:
        ai_model = video_models[0] if video_models else None

    if not ai_model:
        raise ValueError("请先配置支持视频生成的AI模型")
    return ai_model


# Background task processing functions
async def process_video_generation(db: Session, creation_id: int, request_data: dict, user_id: int = None, platform: Optional[str] = None):
    """后台处理视频生成任务"""
    try:
        logger.info(f"Starting video generation for creation {creation_id}, platform={platform}")

        creation = db.query(Creation).filter(Creation.id == creation_id).first()
        if not creation:
            logger.error(f"Creation {creation_id} not found")
            return

        if platform:
            # Cookie模式
            logger.info(f"Using Cookie mode for platform: {platform}")
            
            from app.models.oauth_account import OAuthAccount
            from app.services.oauth.encryption import decrypt_credentials
            from app.services.ai.video_service import DoubaoVideoService

            # 获取用户的OAuth账号
            oauth_account = db.query(OAuthAccount).filter(
                OAuthAccount.user_id == user_id,
                OAuthAccount.platform == platform,
                OAuthAccount.is_active == True,
                OAuthAccount.is_expired == False
            ).first()

            if not oauth_account:
                logger.error(f"No active OAuth account for platform {platform}")
                creation.status = "failed"
                creation.error_message = f"未找到有效的 {platform} 账号"
                creation.output_data = {"error": f"未找到有效的 {platform} 账号"}
                db.commit()
                return

            # 解密凭证
            try:
                credentials = decrypt_credentials(oauth_account.credentials)
                cookies = credentials.get("cookies", {})
            except Exception as e:
                logger.error(f"Failed to decrypt credentials: {e}")
                creation.status = "failed"
                creation.error_message = f"解密凭证失败: {str(e)}"
                creation.output_data = {"error": f"解密凭证失败: {str(e)}"}
                db.commit()
                return

            # 调用视频生成服务
            if platform == "doubao":
                service = DoubaoVideoService(cookies=cookies)
                
                # 验证Cookie
                is_valid = await service.validate_cookies()
                if not is_valid:
                    logger.warning(f"Cookie validation failed for {platform}")
                    creation.status = "failed"
                    creation.error_message = f"{platform} Cookie已过期"
                    creation.output_data = {"error": f"{platform} Cookie已过期"}
                    db.commit()
                    return
                
                # 生成视频脚本
                result = await service.generate_video(
                    prompt=request_data.get("prompt", ""),
                    duration=request_data.get("duration"),
                )
                
                logger.info(f"Video generation result: {result}")
                
                if "error" in result:
                    creation.status = "failed"
                    creation.error_message = result.get("error", "视频生成失败")
                    creation.output_data = result
                else:
                    creation.status = "completed"
                    creation.output_data = result
                
                db.commit()
            else:
                logger.error(f"Unsupported platform: {platform}")
                creation.status = "failed"
                creation.error_message = f"不支持的平台: {platform}"
                creation.output_data = {"error": f"不支持的平台: {platform}"}
                db.commit()
        else:
            # API Key模式 - 模拟
            await asyncio.sleep(5)
            video_url = f"https://example.com/generated_{uuid.uuid4().hex[:8]}.mp4"
            creation.status = "completed"
            creation.output_data = {"video_url": video_url}
            creation.completed_at = datetime.utcnow()
            db.commit()

    except Exception as e:
        logger.error(f"Video generation failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        try:
            creation = db.query(Creation).filter(Creation.id == creation_id).first()
            if creation:
                _refund_creation(db, creation, "视频生成失败退款")
                creation.status = "failed"
                creation.error_message = str(e)
                creation.output_data = {"error": str(e)}
                db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update creation status: {db_error}")


async def process_text_to_video(db: Session, creation_id: int, request_data: dict):
    """后台处理文本转视频任务 - 真实调用用户配置的视频模型"""
    try:
        creation = db.query(Creation).filter(Creation.id == creation_id).first()
        if not creation:
            logger.error(f"Creation {creation_id} not found")
            return

        ai_model = _resolve_video_model(
            db, creation.user_id, (creation.input_data or {}).get("model_id")
        )

        from app.services.langchain.video.factory import VideoGeneratorFactory

        generator = VideoGeneratorFactory.create(
            provider=ai_model.provider,
            api_key=ai_model.api_key,
            model=ai_model.model_name,
            api_base=ai_model.base_url,
        )

        result = await generator.generate(
            prompt=request_data.get("text", ""),
            duration=request_data.get("duration", 6),
            resolution=request_data.get("resolution", "768P"),
        )

        if not result.success or not result.videos:
            raise ValueError(result.error or "视频生成失败")

        # 下载视频到本地存储，历史记录永久可看
        video_url = save_video_from_url(result.videos[0])

        creation.status = "completed"
        creation.output_data = {"video_url": video_url}
        creation.error_message = None
        creation.completed_at = datetime.utcnow()
        db.commit()
        logger.info(f"Text-to-video completed: creation={creation_id}, url={video_url}")
    except Exception as e:
        logger.error(f"Text-to-video failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        try:
            creation = db.query(Creation).filter(Creation.id == creation_id).first()
            if creation:
                _refund_creation(db, creation, "文本转视频失败退款")
                creation.status = "failed"
                creation.error_message = str(e)
                creation.output_data = {"error": str(e)}
                db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update creation status: {db_error}")


async def process_image_to_video(db: Session, creation_id: int, request_data: dict):
    """后台处理图片转视频任务 - 真实调用用户配置的视频模型"""
    try:
        creation = db.query(Creation).filter(Creation.id == creation_id).first()
        if not creation:
            logger.error(f"Creation {creation_id} not found")
            return

        ai_model = _resolve_video_model(
            db, creation.user_id, (creation.input_data or {}).get("model_id")
        )

        from app.services.langchain.video.factory import VideoGeneratorFactory

        generator = VideoGeneratorFactory.create(
            provider=ai_model.provider,
            api_key=ai_model.api_key,
            model=ai_model.model_name,
            api_base=ai_model.base_url,
        )

        images = request_data.get("images") or []
        image_url = images[0] if images else None
        prompt = request_data.get("motion_prompt") or "让图片中的内容自然动起来，保持画面主体与风格一致"

        result = await generator.generate(
            prompt=prompt,
            image_url=image_url,
            duration=request_data.get("duration", 6),
            resolution=request_data.get("resolution", "768P"),
        )

        if not result.success or not result.videos:
            raise ValueError(result.error or "视频生成失败")

        video_url = save_video_from_url(result.videos[0])

        creation.status = "completed"
        creation.output_data = {"video_url": video_url}
        creation.error_message = None
        creation.completed_at = datetime.utcnow()
        db.commit()
        logger.info(f"Image-to-video completed: creation={creation_id}, url={video_url}")
    except Exception as e:
        logger.error(f"Image-to-video failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        try:
            creation = db.query(Creation).filter(Creation.id == creation_id).first()
            if creation:
                _refund_creation(db, creation, "图片转视频失败退款")
                creation.status = "failed"
                creation.error_message = str(e)
                creation.output_data = {"error": str(e)}
                db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update creation status: {db_error}")


@router.post("/generate")
async def generate_video(
    request: VideoGenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """生成视频 - 支持Cookie和API Key模式"""
    try:
        # 计算所需积分（根据时长和分辨率；Cookie模式免费）
        required_credits = 0
        if not request.platform:
            base_credits = 200
            duration_multiplier = request.duration / 5  # 基准5秒
            resolution_multiplier = {"720p": 1.0, "1080p": 1.5, "4k": 2.5}.get(request.resolution, 1.0)
            required_credits = int(base_credits * duration_multiplier * resolution_multiplier)
        
        task_id = f"video_{uuid.uuid4().hex[:16]}"
        
        creation = Creation(
            user_id=current_user.id,
            creation_type="video",
            title=f"视频生成: {request.prompt[:50]}",
            input_data={
                "prompt": request.prompt,
                "duration": request.duration,
                "fps": request.fps,
                "resolution": request.resolution,
                "platform": request.platform,
                "task_id": task_id
            },
            status="processing"
        )
        db.add(creation)
        db.flush()  # 先落库获取 creation.id，保证扣费流水可关联（D7）
        
        # 仅在API Key模式下扣除积分（会员不扣）
        if not request.platform:
            _consume_credits(
                db,
                current_user.id,
                required_credits,
                f"视频生成: {request.duration}秒 {request.resolution}",
                creation.id,
            )
        
        db.commit()
        db.refresh(creation)
        
        background_tasks.add_task(
            process_video_generation,
            db, creation.id, request.dict(), current_user.id, request.platform
        )
        
        return success_response(
            data=VideoTaskResponse(
                task_id=task_id,
                status="processing",
                progress=0
            ),
            message="视频生成任务已创建"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"视频生成失败: {str(e)}")


@router.post("/text-to-video")
async def text_to_video(
    request: TextToVideoRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """文本转视频"""
    try:
        required_credits = 150
        if request.background_music:
            required_credits += 30
        if request.subtitle:
            required_credits += 20

        # 校验前端选择的模型（属于当前用户且已启用）
        if request.model_id:
            from app.models.ai_model import AIModel
            ai_model = db.query(AIModel).filter(
                AIModel.id == request.model_id,
                AIModel.user_id == current_user.id,
                AIModel.is_active == True
            ).first()
            if not ai_model:
                raise HTTPException(status_code=400, detail="AI模型不存在或未启用")
        
        task_id = f"t2v_{uuid.uuid4().hex[:16]}"
        
        creation = Creation(
            user_id=current_user.id,
            creation_type="video",
            tool_type="text_to_video",
            title=f"文本转视频: {request.text[:50]}",
            input_data={
                "text": request.text,
                "model_id": request.model_id,
                "voice": request.voice,
                "background_music": request.background_music,
                "subtitle": request.subtitle,
                "duration": request.duration,
                "resolution": request.resolution
            },
            model_id=request.model_id,
            status="processing",
            task_id=task_id
        )
        db.add(creation)
        db.flush()  # 先落库获取 creation.id，保证扣费流水可关联（D7）
        
        _consume_credits(db, current_user.id, required_credits, "文本转视频", creation.id)
        db.commit()
        db.refresh(creation)
        
        background_tasks.add_task(
            process_text_to_video,
            db, creation.id, request.dict()
        )
        
        return success_response(
            data=VideoTaskResponse(
                task_id=task_id,
                status="processing",
                progress=0
            ),
            message="文本转视频任务已创建"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"文本转视频失败: {str(e)}")


@router.post("/image-to-video")
async def image_to_video(
    request: ImageToVideoRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """图片转视频"""
    try:
        required_credits = 100 + len(request.images) * 20

        # 校验前端选择的模型（属于当前用户且已启用）
        if request.model_id:
            from app.models.ai_model import AIModel
            ai_model = db.query(AIModel).filter(
                AIModel.id == request.model_id,
                AIModel.user_id == current_user.id,
                AIModel.is_active == True
            ).first()
            if not ai_model:
                raise HTTPException(status_code=400, detail="AI模型不存在或未启用")
        
        task_id = f"i2v_{uuid.uuid4().hex[:16]}"
        
        creation = Creation(
            user_id=current_user.id,
            creation_type="video",
            tool_type="image_to_video",
            title=f"图片转视频: {len(request.images)}张图片",
            input_data={
                "images": request.images,
                "model_id": request.model_id,
                "transition": request.transition,
                "duration_per_image": request.duration_per_image,
                "motion_prompt": request.motion_prompt,
                "duration": request.duration,
                "resolution": request.resolution
            },
            model_id=request.model_id,
            status="processing",
            task_id=task_id
        )
        db.add(creation)
        db.flush()  # 先落库获取 creation.id，保证扣费流水可关联（D7）
        
        _consume_credits(
            db,
            current_user.id,
            required_credits,
            f"图片转视频: {len(request.images)}张",
            creation.id,
        )
        db.commit()
        db.refresh(creation)
        
        background_tasks.add_task(
            process_image_to_video,
            db, creation.id, request.dict()
        )
        
        return success_response(
            data=VideoTaskResponse(
                task_id=task_id,
                status="processing",
                progress=0
            ),
            message="图片转视频任务已创建"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"图片转视频失败: {str(e)}")


@router.get("/task/{task_id}")
async def get_video_task_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取视频任务状态"""
    try:
        creation = db.query(Creation).filter(
            Creation.task_id == task_id,
            Creation.user_id == current_user.id
        ).first()
        
        if not creation:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        video_url = None
        if creation.status == "completed" and creation.output_data:
            video_url = creation.output_data.get("video_url")
        
        progress = 100 if creation.status == "completed" else (
            50 if creation.status == "processing" else 0
        )
        
        return success_response(
            data=VideoTaskResponse(
                task_id=task_id,
                status=creation.status,
                video_url=video_url,
                progress=progress,
                error=creation.error_message if creation.status == "failed" else None,
            ),
            message="获取成功"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务状态失败: {str(e)}")


@router.post("/voiceover")
async def generate_voiceover(
    request: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """AI配音"""
    try:
        text = request.get("text", "")
        voice = request.get("voice", "default")
        
        required_credits = 50
        
        if current_user.credits < required_credits:
            raise HTTPException(status_code=402, detail="积分不足")
        
        # 模拟生成配音
        audio_url = f"https://example.com/voiceover_{uuid.uuid4().hex[:8]}.mp3"
        
        current_user.credits -= required_credits
        transaction = CreditTransaction(
            user_id=current_user.id,
            transaction_type=TransactionType.CONSUME,
            amount=-required_credits,
            balance_before=current_user.credits + required_credits,
            balance_after=current_user.credits,
            description="AI配音",
            related_type="voiceover"
        )
        db.add(transaction)
        db.commit()
        
        return success_response(
            data={"audio_url": audio_url},
            message="配音生成成功"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"配音生成失败: {str(e)}")


@router.post("/subtitles")
async def generate_subtitles(
    request: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """生成字幕"""
    try:
        video_url = request.get("video_url", "")
        
        required_credits = 30
        
        if current_user.credits < required_credits:
            raise HTTPException(status_code=402, detail="积分不足")
        
        # 模拟生成字幕
        subtitles = [
            {"start": 0, "end": 2, "text": "示例字幕1"},
            {"start": 2, "end": 4, "text": "示例字幕2"}
        ]
        
        current_user.credits -= required_credits
        transaction = CreditTransaction(
            user_id=current_user.id,
            transaction_type=TransactionType.CONSUME,
            amount=-required_credits,
            balance_before=current_user.credits + required_credits,
            balance_after=current_user.credits,
            description="生成字幕",
            related_type="subtitle"
        )
        db.add(transaction)
        db.commit()
        
        return success_response(
            data={"subtitles": subtitles},
            message="字幕生成成功"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"字幕生成失败: {str(e)}")


@router.get("/gallery")
async def get_video_gallery(
    page: int = 1,
    page_size: int = 12,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取用户视频库"""
    try:
        from sqlalchemy import desc
        
        # 只查视频创作记录（过滤掉 PPT 等含大 output_data 的记录，避免排序内存超限），
        # 且只查列表所需字段
        query = db.query(
            Creation.id, Creation.input_data, Creation.output_data, Creation.created_at
        ).filter(
            Creation.user_id == current_user.id,
            Creation.creation_type == "video",
            Creation.status == "completed",
            Creation.output_data.isnot(None)
        )
        
        creations = query.order_by(desc(Creation.created_at)).offset((page - 1) * page_size).limit(page_size).all()
        
        items = []
        for creation in creations:
            if creation.output_data and isinstance(creation.output_data, dict):
                video_url = creation.output_data.get("video_url")
                if video_url and isinstance(video_url, str):
                    items.append({
                        "id": creation.id,
                        "url": video_url,
                        "prompt": creation.input_data.get("prompt", creation.input_data.get("text", "")) if creation.input_data else "",
                        "created_at": str(creation.created_at) if creation.created_at else None,
                    })
        
        # 重新查询总数
        total = len(items)
        
        return success_response(
            data={
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": items,
            },
            message="获取成功"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取视频库失败: {str(e)}")
