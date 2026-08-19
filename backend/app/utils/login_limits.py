# -*- coding: utf-8 -*-
"""登录限流与失败锁定工具（T4）：优先 Redis，Redis 不可用时内存兜底"""
import time

from app.utils.cache import REDIS_AVAILABLE, redis_client


_mem = {}


def _now() -> float:
    return time.time()


def _incr_with_ttl(key: str, ttl: int) -> int:
    """计数 +1，首次命中设置 TTL（秒）；返回当前计数"""
    if REDIS_AVAILABLE and redis_client:
        try:
            val = redis_client.incr(key)
            if val == 1:
                redis_client.expire(key, ttl)
            return int(val)
        except Exception:
            pass
    now = _now()
    item = _mem.get(key)
    if item is None or item[1] <= now:
        _mem[key] = [1, now + ttl]
        return 1
    item[0] += 1
    return item[0]


def _get_count(key: str) -> int:
    now = _now()
    if REDIS_AVAILABLE and redis_client:
        try:
            val = redis_client.get(key)
            return int(val) if val else 0
        except Exception:
            return 0
    item = _mem.get(key)
    if item is None or item[1] <= now:
        return 0
    return item[0]


def _set_with_ttl(key: str, value: int, ttl: int) -> None:
    if REDIS_AVAILABLE and redis_client:
        try:
            redis_client.setex(key, ttl, value)
            return
        except Exception:
            pass
    _mem[key] = [value, _now() + ttl]


def _delete(key: str) -> None:
    if REDIS_AVAILABLE and redis_client:
        try:
            redis_client.delete(key)
            return
        except Exception:
            pass
    _mem.pop(key, None)


def check_login_rate(scope: str, ip: str, max_requests: int, window: int = 60) -> bool:
    """IP 维度登录限流：窗口内超过 max_requests 返回 False（拒绝）"""
    key = f"login_rate:{scope}:{ip}"
    return _incr_with_ttl(key, window) <= max_requests


def record_login_failure(scope: str, account: str, threshold: int, lock_minutes: int) -> bool:
    """记录一次失败；达到阈值返回 True 并进入锁定"""
    key = f"login_fail:{scope}:{account}"
    count = _incr_with_ttl(key, lock_minutes * 60)
    if count >= threshold:
        _set_with_ttl(f"login_lock:{scope}:{account}", 1, lock_minutes * 60)
        return True
    return False


def is_login_locked(scope: str, account: str) -> bool:
    return _get_count(f"login_lock:{scope}:{account}") > 0


def clear_login_failures(scope: str, account: str) -> None:
    _delete(f"login_fail:{scope}:{account}")
    _delete(f"login_lock:{scope}:{account}")


def clear_login_rate(scope: str, ip: str) -> None:
    """清理 IP 维度登录限流计数（测试与解锁场景使用）"""
    _delete(f"login_rate:{scope}:{ip}")
