"""
认证相关API路由
"""
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    check_admin_ip,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from app.models.credit import TransactionType
from app.models.operation import ReferralRecord, ReferralStatus
from app.models.user import User, UserRole, UserStatus
from app.schemas.common import success_response
from app.schemas.user import (
    UserRegister,
    UserLogin,
    UserResponse,
    UserUpdate,
    PasswordChange,
    PasswordResetRequest,
    PasswordResetConfirm,
)
from app.services.credit_service import CreditService

router = APIRouter()


def _login_ip(request: Request) -> str:
    """获取登录来源 IP：仅信任可信反向代理（Nginx）传递的转发头"""
    forwarded = request.headers.get("X-Real-IP") or request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/register")
def register(user_in: UserRegister, db: Session = Depends(get_db)) -> Any:
    """
    用户注册
    """
    # 检查用户名是否已存在
    user = db.query(User).filter(User.username == user_in.username).first()
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在",
        )
    
    # 检查邮箱是否已存在
    user = db.query(User).filter(User.email == user_in.email).first()
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被注册",
        )

    # 先校验推荐码：无效则直接拒绝注册，避免产生半成品用户
    referrer = None
    if user_in.referral_code:
        referrer = db.query(User).filter(
            User.referral_code == user_in.referral_code
        ).first()
        if not referrer:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="推荐码无效",
            )
    
    # 创建新用户
    user = User(
        username=user_in.username,
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        nickname=user_in.nickname,
        role=UserRole.USER,  # T5：注册账号显式固定为普通用户，杜绝提权
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 推荐码注册：建立推荐关系
    if referrer is not None:
        db.add(ReferralRecord(
            referrer_id=referrer.id,
            referee_id=user.id,
            referral_code=user_in.referral_code,
            status=ReferralStatus.PENDING,
            trigger_event="register",
        ))
        db.commit()
        # 邀请注册返利：规则为固定积分时注册即结算，失败不影响注册
        try:
            from app.services.operation_service import ReferralService
            record = db.query(ReferralRecord).filter(
                ReferralRecord.referee_id == user.id,
                ReferralRecord.status == ReferralStatus.PENDING,
            ).first()
            if record:
                ReferralService.settle_referral_on_register(db, record)
        except Exception:
            db.rollback()
    
    # 新用户注册赠送 1000 积分
    try:
        CreditService.add_credits(
            db=db,
            user_id=user.id,
            amount=1000,
            transaction_type=TransactionType.REWARD,
            description="新用户注册奖励"
        )
    except Exception as e:
        # 赠送积分失败不影响注册流程
        import logging
        logging.error(f"新用户注册赠送积分失败：{e}")
    
    return success_response(data=UserResponse.model_validate(user).model_dump())


@router.post("/login")
def login(user_in: UserLogin, request: Request, db: Session = Depends(get_db)) -> Any:
    """
    用户登录（支持用户名或邮箱登录）
    """
    if settings.LOGIN_RATE_LIMIT_ENABLED:
        from app.utils.login_limits import (
            check_login_rate,
            clear_login_failures,
            is_login_locked,
            record_login_failure,
        )
        ip = _login_ip(request)
        if not check_login_rate("user", ip, settings.LOGIN_RATE_LIMIT_PER_MINUTE):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="登录尝试过于频繁，请稍后再试",
            )
        if is_login_locked("user", user_in.username):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"账号已锁定，请 {settings.LOGIN_LOCK_MINUTES} 分钟后再试",
            )

    # 查找用户 - 同时支持用户名和邮箱
    user = db.query(User).filter(
        (User.username == user_in.username) | 
        (User.email == user_in.username)
    ).first()
    
    if not user or not verify_password(user_in.password, user.password_hash):
        if settings.LOGIN_RATE_LIMIT_ENABLED:
            record_login_failure(
                "user",
                user_in.username,
                settings.LOGIN_FAIL_LOCK_THRESHOLD,
                settings.LOGIN_LOCK_MINUTES,
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码不正确，请重新输入",
        )
    
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )
    
    # 更新最后登录时间和IP
    from datetime import datetime
    user.last_login_at = datetime.utcnow()
    db.commit()

    if settings.LOGIN_RATE_LIMIT_ENABLED:
        clear_login_failures("user", user_in.username)
    
    # 生成访问令牌和刷新令牌
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)
    
    return success_response(data={
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": UserResponse.model_validate(user).model_dump()
    })


@router.post("/refresh")
def refresh_token(refresh_token: str = Body(..., embed=True), db: Session = Depends(get_db)) -> Any:
    """
    刷新访问令牌
    """
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌",
        )
    if payload.get("token_type") != "user":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌",
        )
    user_id: int = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌",
        )
    
    # 验证用户是否存在且活跃
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被禁用",
        )
    
    # 生成新的访问令牌和刷新令牌
    new_access_token = create_access_token(subject=user.id)
    new_refresh_token = create_refresh_token(subject=user.id)
    
    return success_response(data={
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    })


@router.post("/admin/login")
def admin_login(user_in: UserLogin, request: Request, db: Session = Depends(get_db)) -> Any:
    """
    管理员登录（仅 role=admin 可登录，签发独立 admin 令牌，T1 安全加固）
    """
    # T2 解耦：管理登录仅限白名单 IP（VPN/内网），未配置白名单时不限制
    if not check_admin_ip(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="管理接口仅限白名单 IP 访问",
        )

    if settings.LOGIN_RATE_LIMIT_ENABLED:
        from app.utils.login_limits import (
            check_login_rate,
            clear_login_failures,
            is_login_locked,
            record_login_failure,
        )
        ip = _login_ip(request)
        if not check_login_rate("admin", ip, settings.ADMIN_LOGIN_RATE_LIMIT_PER_MINUTE):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="登录尝试过于频繁，请稍后再试",
            )
        if is_login_locked("admin", user_in.username):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"账号已锁定，请 {settings.LOGIN_LOCK_MINUTES} 分钟后再试",
            )

    user = db.query(User).filter(
        (User.username == user_in.username) | (User.email == user_in.username)
    ).first()

    if not user or not verify_password(user_in.password, user.password_hash):
        if settings.LOGIN_RATE_LIMIT_ENABLED:
            record_login_failure(
                "admin",
                user_in.username,
                settings.LOGIN_FAIL_LOCK_THRESHOLD,
                settings.LOGIN_LOCK_MINUTES,
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码不正确，请重新输入",
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )

    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可登录管理端",
        )

    from datetime import datetime
    user.last_login_at = datetime.utcnow()
    db.commit()

    if settings.LOGIN_RATE_LIMIT_ENABLED:
        clear_login_failures("admin", user_in.username)

    access_token = create_access_token(subject=user.id, token_type="admin")
    refresh_token = create_refresh_token(subject=user.id, token_type="admin")

    return success_response(data={
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ADMIN_TOKEN_EXPIRE_MINUTES * 60,
        "user": UserResponse.model_validate(user).model_dump(),
    })


@router.post("/admin/refresh")
def admin_refresh_token(
    request: Request,
    refresh_token: str = Body(..., embed=True),
    db: Session = Depends(get_db),
) -> Any:
    """
    刷新管理员令牌（仅接受 admin 作用域刷新令牌）
    """
    # T2 解耦：管理刷新仅限白名单 IP
    if not check_admin_ip(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="管理接口仅限白名单 IP 访问",
        )
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌",
        )
    if payload.get("token_type") != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌",
        )
    user_id: int = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被禁用",
        )
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可刷新管理端令牌",
        )

    new_access_token = create_access_token(subject=user.id, token_type="admin")
    new_refresh_token = create_refresh_token(subject=user.id, token_type="admin")

    return success_response(data={
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ADMIN_TOKEN_EXPIRE_MINUTES * 60,
    })


@router.get("/me")
def get_current_user_info(
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    获取当前用户信息
    """
    return success_response(data=UserResponse.model_validate(current_user).model_dump())


@router.put("/me")
def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    更新当前用户信息
    """
    update_data = user_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(current_user, key, value)

    db.commit()
    db.refresh(current_user)
    
    return success_response(data=UserResponse.model_validate(current_user).model_dump())


@router.post("/change-password")
def change_password(
    password_change: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    修改密码
    """
    if not verify_password(password_change.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="原密码错误",
        )
    
    current_user.password_hash = get_password_hash(password_change.new_password)
    db.commit()
    
    return success_response(message="密码修改成功")


@router.post("/password-reset/request")
def request_password_reset(
    reset_request: PasswordResetRequest,
    db: Session = Depends(get_db),
) -> Any:
    """
    请求密码重置（发送重置令牌）
    
    由于当前未集成邮件服务，此接口会直接返回重置令牌。
    生产环境应通过邮件发送令牌。
    """
    from jose import jwt
    from datetime import datetime, timedelta
    
    user = db.query(User).filter(User.email == reset_request.email).first()
    if not user:
        # 为防止邮箱枚举攻击，即使用户不存在也返回成功
        return success_response(message="如果该邮箱已注册，重置链接已发送")
    
    # 生成重置令牌（有效期30分钟）
    reset_token = jwt.encode(
        {
            "sub": str(user.id),
            "type": "password_reset",
            "exp": datetime.utcnow() + timedelta(minutes=30),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    
    # TODO: 集成邮件服务后，通过邮件发送重置链接
    # 当前开发阶段直接返回令牌
    return success_response(
        data={"reset_token": reset_token},
        message="密码重置令牌已生成（开发模式下直接返回令牌）"
    )


@router.post("/password-reset/confirm")
def confirm_password_reset(
    reset_confirm: PasswordResetConfirm,
    db: Session = Depends(get_db),
) -> Any:
    """
    确认密码重置
    """
    from jose import JWTError, jwt
    
    try:
        payload = jwt.decode(
            reset_confirm.token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        
        if payload.get("type") != "password_reset":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的重置令牌",
            )
        
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的重置令牌",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="重置令牌已过期或无效",
        )
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )
    
    user.password_hash = get_password_hash(reset_confirm.new_password)
    db.commit()
    
    return success_response(message="密码重置成功，请使用新密码登录")
