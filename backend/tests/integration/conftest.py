# -*- coding: utf-8 -*-
"""
运营管理集成测试 fixtures

使用真实 MySQL（ai_creator_test）与 Redis（db 1）验证跨模块协作链路。
MySQL 测试库不可用时，集成测试整体跳过。
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.main import app


def _mysql_test_url() -> str:
    """从 backend/.env 读取生效 DATABASE_URL，替换库名为 ai_creator_test"""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    url = None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("DATABASE_URL="):
            url = line.split("=", 1)[1].strip().strip('"').strip("'")
            break
    if not url or "mysql" not in url:
        raise RuntimeError("backend/.env 未找到 MySQL DATABASE_URL")
    return url.rsplit("/", 1)[0] + "/ai_creator_test"


@pytest.fixture(scope="session", autouse=True)
def mysql_available():
    """MySQL 测试库不可用时整体跳过集成测试"""
    url = _mysql_test_url()
    try:
        engine = create_engine(url, connect_args={"connect_timeout": 5})
        with engine.connect():
            pass
        engine.dispose()
    except Exception:
        pytest.skip("MySQL 测试库 ai_creator_test 不可用，跳过集成测试")
    return url


@pytest.fixture(scope="session")
def mysql_engine(mysql_available):
    """创建/重建 ai_creator_test 表结构，并临时替换 app 的数据库引擎"""
    import app.core.database as db_module
    from app.core import config

    url = mysql_available
    # READ COMMITTED：让测试内的验证会话能立即看到 API 会话提交的数据
    test_engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=1800,
        isolation_level="READ COMMITTED",
    )

    # 干净起点：先删后建
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    original_engine = db_module.engine
    original_session = db_module.SessionLocal
    db_module.engine = test_engine
    db_module.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    config.settings.DATABASE_URL = url

    yield test_engine

    db_module.engine = original_engine
    db_module.SessionLocal = original_session
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


@pytest.fixture(autouse=True)
def clean_tables(mysql_engine):
    """每个用例结束后清空全部表，保证用例隔离"""
    yield
    with mysql_engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f"TRUNCATE TABLE `{table.name}`"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


@pytest.fixture
def mysql_session(mysql_engine):
    """用于测试内直接验证数据库结果的会话"""
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=mysql_engine, expire_on_commit=False
    )
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def client(mysql_engine, monkeypatch):
    """真实 MySQL 的 API 测试客户端，禁用后台同步线程"""
    # 不启动 60 秒后台同步线程，由测试手动触发
    monkeypatch.setattr(
        "app.tasks.background_tracker.start_tracker_background", lambda: None
    )

    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=mysql_engine, expire_on_commit=False
    )

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(mysql_session):
    """管理员测试用户"""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole, UserStatus

    user = User(
        username="it_admin",
        email="it_admin@example.com",
        password_hash=get_password_hash("adminpass123"),
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
    )
    mysql_session.add(user)
    mysql_session.commit()
    mysql_session.refresh(user)
    return user


@pytest.fixture
def admin_headers(client, admin_user):
    """管理员认证头"""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": admin_user.username, "password": "adminpass123"},
    )
    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def it_user(mysql_session):
    """普通测试用户"""
    from app.core.security import get_password_hash
    from app.models.user import User, UserStatus

    user = User(
        username="it_user",
        email="it_user@example.com",
        password_hash=get_password_hash("userpass123"),
        status=UserStatus.ACTIVE,
    )
    mysql_session.add(user)
    mysql_session.commit()
    mysql_session.refresh(user)
    return user


@pytest.fixture
def it_user_headers(client, it_user):
    """普通用户认证头"""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": it_user.username, "password": "userpass123"},
    )
    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def clean_tracker_redis():
    """清理流量统计在 Redis db1 中的缓存键"""
    from app.services.tracker_service import tracker_service

    keys = [
        tracker_service.PAGE_VIEW_KEY,
        tracker_service.USER_EVENT_KEY,
        tracker_service.PAGE_VIEW_UPDATE_KEY,
    ]
    if tracker_service.redis_client:
        tracker_service.redis_client.delete(*keys)
    yield
    if tracker_service.redis_client:
        tracker_service.redis_client.delete(*keys)
