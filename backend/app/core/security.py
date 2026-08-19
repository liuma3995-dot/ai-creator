"""
安全认证模块
"""
import ipaddress
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer认证
security = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码
    
    Args:
        plain_password: 明文密码
        hashed_password: 哈希密码
        
    Returns:
        bool: 是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    获取密码哈希值
    
    Args:
        password: 明文密码
        
    Returns:
        str: 哈希密码
    """
    return pwd_context.hash(password)


def _secret_keys() -> list:
    """按优先级返回可用的签名密钥（管理端独立密钥优先，去重）"""
    keys = []
    if settings.ADMIN_SECRET_KEY:
        keys.append(settings.ADMIN_SECRET_KEY)
    keys.append(settings.SECRET_KEY)
    seen = set()
    unique = []
    for key in keys:
        if key not in seen:
            seen.add(key)
            unique.append(key)
    return unique


def _signing_secret(token_type: str) -> str:
    """管理端令牌使用独立密钥（若配置），其余使用主密钥"""
    if token_type == "admin" and settings.ADMIN_SECRET_KEY:
        return settings.ADMIN_SECRET_KEY
    return settings.SECRET_KEY


def create_access_token(
    subject: int,
    expires_delta: Optional[timedelta] = None,
    token_type: str = "user",
) -> str:
    """
    创建访问令牌（user-用户端 / admin-管理端，T1 安全加固）
    
    Args:
        subject: 用户ID
        expires_delta: 过期时间增量
        token_type: 令牌类型
        
    Returns:
        str: JWT令牌
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=(
                settings.ADMIN_TOKEN_EXPIRE_MINUTES
                if token_type == "admin"
                else settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
        )
    to_encode = {"exp": expire, "sub": str(subject), "type": token_type}
    encoded_jwt = jwt.encode(
        to_encode, _signing_secret(token_type), algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(subject: int, token_type: str = "user") -> str:
    """
    创建刷新令牌（携带作用域 token_type，user 刷新只能刷 user 令牌）
    
    Args:
        subject: 用户ID
        token_type: 令牌类型
        
    Returns:
        str: JWT令牌
    """
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "refresh",
        "token_type": token_type,
    }
    encoded_jwt = jwt.encode(
        to_encode, _signing_secret(token_type), algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def decode_token(token: str, expected_type: Optional[str] = None) -> dict:
    """
    解码令牌
    
    Args:
        token: JWT令牌
        expected_type: 期望的令牌类型（user/admin/refresh），为空不校验
        
    Returns:
        dict: 解码后的数据
        
    Raises:
        HTTPException: 令牌无效或过期
    """
    payload = None
    for secret in _secret_keys():
        try:
            payload = jwt.decode(token, secret, algorithms=[settings.ALGORITHM])
            break
        except JWTError:
            continue
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )
    print(f"Token decoded successfully: {payload}")
    if expected_type and payload.get("type") != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    获取当前用户
    
    Args:
        credentials: HTTP认证凭证
        db: 数据库会话
        
    Returns:
        User: 当前用户
        
    Raises:
        HTTPException: 认证失败
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭证，请先登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    payload = decode_token(token, expected_type="user")
    
    user_id_str: str = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用"
        )
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    获取当前活跃用户
    
    Args:
        current_user: 当前用户
        
    Returns:
        User: 当前活跃用户
        
    Raises:
        HTTPException: 用户未激活
    """
    if current_user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户未激活"
        )
    return current_user


def _client_ip(request: Request) -> str:
    """获取客户端真实 IP：仅信任可信反向代理（Nginx）传递的转发头"""
    forwarded = request.headers.get("X-Real-IP") or request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return ""


def _admin_ip_allowed(request: Request) -> bool:
    """管理接口 IP 白名单校验（T2）：未配置白名单默认放行"""
    whitelist = settings.ADMIN_IP_WHITELIST or []
    if not whitelist:
        return True
    ip = _client_ip(request)
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for entry in whitelist:
        entry = str(entry).strip()
        try:
            if "/" in entry:
                if addr in ipaddress.ip_network(entry, strict=False):
                    return True
            elif addr == ipaddress.ip_address(entry):
                return True
        except ValueError:
            continue
    return False


def check_admin_ip(request: Request) -> bool:
    """管理域 IP 白名单校验（公开入口，供管理登录/刷新等端点复用）"""
    return _admin_ip_allowed(request)


async def get_current_admin_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    获取当前管理员用户：必须持有 admin 类型令牌且角色为管理员

    Args:
        credentials: HTTP认证凭证
        db: 数据库会话

    Returns:
        User: 当前管理员用户

    Raises:
        HTTPException: 令牌无效或权限不足
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭证，请先登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not _admin_ip_allowed(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="管理接口仅限白名单 IP 访问",
        )

    token = credentials.credentials
    payload = decode_token(token, expected_type="admin")

    user_id_str: str = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )

    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    return user
