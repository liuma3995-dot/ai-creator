"""
管理员用户管理接口
提供用户列表、详情、模型管理等功能
"""
from typing import Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from app import models
from app.utils.deps import get_db, get_admin_user as get_current_admin_user
from app.schemas.common import success_response

router = APIRouter()


@router.get("/list")
def get_user_list(
    page: int = 1,
    page_size: int = 20,
    keyword: str = None,
    current_user: models.User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    获取用户列表（分页）
    
    **权限要求**: 管理员
    
    **参数**:
    - page: 页码（默认 1）
    - page_size: 每页数量（默认 20）
    - keyword: 搜索关键词（用户名/邮箱）
    
    **返回**:
    - 用户列表及分页信息
    """
    query = db.query(models.User).filter(models.User.deleted_at.is_(None))
    
    # 关键词搜索
    if keyword:
        query = query.filter(
            or_(
                models.User.username.like(f"%{keyword}%"),
                models.User.email.like(f"%{keyword}%")
            )
        )
    
    # 总数
    total = query.count()
    
    # 分页
    offset = (page - 1) * page_size
    users = query.order_by(models.User.created_at.desc()).offset(offset).limit(page_size).all()
    
    data = []
    for user in users:
        data.append({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "nickname": user.nickname,
            "role": user.role,
            "status": user.status,
            "credits": user.credits,
            "is_member": user.is_member,
            "total_creations": user.total_creations,
            "created_at": user.created_at,
            "last_login_at": user.last_login_at
        })
    
    return success_response(
        data={
            "users": data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
    )


@router.get("/{user_id}")
def get_user_detail(
    user_id: int,
    current_user: models.User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    获取用户详情（包含 AIModel 列表）
    
    **权限要求**: 管理员
    
    **参数**:
    - user_id: 用户 ID
    
    **返回**:
    - 用户详细信息、模型列表
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 获取用户的 AIModel 列表（包括用户自己的和系统内置的）
    ai_models = db.query(models.AIModel).filter(
        or_(
            models.AIModel.user_id == user_id,
            models.AIModel.is_system_builtin == True
        ),
        models.AIModel.is_active == True
    ).all()
    
    models_data = []
    for model in ai_models:
        models_data.append({
            "id": model.id,
            "name": model.name,
            "provider": model.provider,
            "model_name": model.model_name,
            "is_default": model.is_default,
            "is_active": model.is_active,
            "is_system_builtin": model.is_system_builtin,
            "created_at": model.created_at
        })
    
    return success_response(
        data={
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "nickname": user.nickname,
                "avatar": user.avatar,
                "phone": user.phone,
                "role": user.role,
                "status": user.status,
                "credits": user.credits,
                "daily_quota": user.daily_quota,
                "used_quota": user.used_quota,
                "total_creations": user.total_creations,
                "is_member": user.is_member,
                "member_expired_at": user.member_expired_at,
                "last_login_at": user.last_login_at,
                "last_login_ip": user.last_login_ip,
                "created_at": user.created_at,
                "referral_code": user.referral_code
            },
            "ai_models": models_data
        }
    )


@router.post("/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    current_user: models.User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    重置用户密码
    
    **权限要求**: 管理员
    
    **说明**:
    - 将用户密码重置为 123456
    - 用户下次登录需使用新密码
    
    **参数**:
    - user_id: 用户 ID
    
    **返回**:
    - 重置结果
    """
    from app.core.security import get_password_hash
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 不能重置自己
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能重置自己的密码"
        )
    
    # 重置密码为 123456
    user.password_hash = get_password_hash("123456")
    db.commit()
    
    return success_response(message="密码已重置为 123456")


@router.post("/{user_id}/toggle-model-status")
def toggle_model_status(
    user_id: int,
    model_id: int,
    is_active: bool,
    current_user: models.User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    切换用户模型的启用/禁用状态
    
    **权限要求**: 管理员
    
    **说明**:
    - 管理员可以禁用系统内置模型（对该用户）
    - 禁用后用户无法看到该模型
    
    **参数**:
    - user_id: 用户 ID
    - model_id: 模型 ID
    - is_active: 是否启用
    
    **返回**:
    - 更新后的模型信息
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    model = db.query(models.AIModel).filter(
        models.AIModel.id == model_id
    ).first()
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模型不存在"
        )
    
    model.is_active = is_active
    db.commit()
    db.refresh(model)
    
    return success_response(
        data={
            "id": model.id,
            "name": model.name,
            "is_active": model.is_active
        },
        message=f"模型已{'启用' if is_active else '禁用'}"
    )


@router.post("/{user_id}/toggle-status")
def toggle_user_status(
    user_id: int,
    is_active: bool,
    current_user: models.User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    停用/启用用户账号（日常管理手段，代替删除）

    **权限要求**: 管理员

    **说明**:
    - 停用后用户无法登录、无法调用任何接口，数据保留可恢复；
    - 不修改 deleted_at，与归档互不干扰；
    - 禁止停用/启用自己的账号。
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能停用/启用自己的账号"
        )

    user.status = models.UserStatus.ACTIVE if is_active else models.UserStatus.INACTIVE
    db.commit()
    db.refresh(user)

    return success_response(
        data={
            "id": user.id,
            "username": user.username,
            "status": user.status,
        },
        message="账号已启用" if is_active else "账号已停用",
    )


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    confirm_user_id: int,
    current_user: models.User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    归档用户（软删除兜底，前端已下线，仅限数据库级兜底操作）
    
    **权限要求**: 管理员
    
    **参数**:
    - user_id: 用户 ID
    - confirm_user_id: 二次确认参数，必须等于 user_id，否则拒绝执行
    
    **返回**:
    - 归档结果

    **说明**:
    - 仅软删除（deleted_at + status=inactive），禁止任何硬删除；
    - 关联数据（积分、订单、推荐、创作等）全部保留，可恢复；
    - 禁止归档管理员账号，禁止归档自己。
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # 二次确认：防止误调接口
    if confirm_user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="确认参数不一致，已取消归档"
        )
    
    # 不能归档自己
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能归档自己的账号"
        )

    # 禁止归档管理员账号
    if user.role == models.UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不允许归档管理员账号"
        )
    
    # 仅软删除（归档），绝不硬删
    user.deleted_at = datetime.now()
    user.status = models.UserStatus.INACTIVE
    db.commit()
    
    return success_response(message="用户已归档（软删除），数据保留可恢复")
