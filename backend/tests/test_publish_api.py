# -*- coding: utf-8 -*-
"""发布管理 API 测试：创建草稿的业务失败/异常/成功与积分、失败记录处理"""


def _create_platform_account(db_session, user_id):
    from app.models.publish import PlatformAccount, PlatformStatus, CookieStatus

    account = PlatformAccount(
        user_id=user_id,
        platform="xiaohongshu",
        account_name="test_xhs",
        cookies="encrypted-fake",
        cookies_valid="valid",
        is_active="active",
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


def _create_creation(db_session, user_id):
    from app.models.creation import Creation

    creation = Creation(
        user_id=user_id,
        creation_type="xiaohongshu_note",
        tool_type="writing",
        title="测试创作",
        output_content="测试内容",
        status="completed",
    )
    db_session.add(creation)
    db_session.commit()
    db_session.refresh(creation)
    return creation


def _build_mock_publisher(result=None, exc=None):
    class MockPublisher:
        def __init__(self, result, exc):
            self.result = result
            self.exc = exc

        async def check_cookies_or_raise(self, account):
            return {}

        async def create_draft(self, **kwargs):
            if self.exc:
                raise self.exc
            return self.result

    return MockPublisher(result, exc)


def _publish_payload(account_id, creation_id):
    return {
        "account_id": account_id,
        "creation_id": creation_id,
        "content_type": "article",
        "title": "测试发布",
        "content": "测试内容",
        "rendered_content": "<p>测试内容</p>",
    }


def test_publish_draft_business_failure_returns_400_and_saves_failed_record(
    client, db_session, auth_headers, test_user, monkeypatch
):
    """草稿创建返回 success=False（如超时）→ 400 + 失败记录 + 积分退款"""
    from app.api.v1 import publish as publish_api
    from app.models.publish import PublishRecord, PublishStatus

    test_user.credits = 100
    db_session.commit()

    account = _create_platform_account(db_session, test_user.id)
    creation = _create_creation(db_session, test_user.id)

    monkeypatch.setattr(
        publish_api,
        "get_platform",
        lambda _platform: _build_mock_publisher(
            result={"success": False, "message": "创建草稿失败: Timeout 30000ms exceeded"}
        ),
    )

    response = client.post(
        "/api/v1/publish/publish",
        headers=auth_headers,
        json=_publish_payload(account.id, creation.id),
    )

    assert response.status_code == 400
    assert response.json()["message"] == "创建草稿失败: Timeout 30000ms exceeded"

    record = (
        db_session.query(PublishRecord)
        .filter(PublishRecord.creation_id == creation.id)
        .first()
    )
    assert record is not None
    assert record.status == PublishStatus.FAILED
    assert "Timeout" in (record.error_message or "")

    # 扣 10 后退还 10，余额不变
    db_session.refresh(test_user)
    assert test_user.credits == 100


def test_publish_draft_exception_returns_400_and_saves_failed_record(
    client, db_session, auth_headers, test_user, monkeypatch
):
    """草稿创建抛异常（如 Playwright 超时）→ 业务失败 400 + 失败记录 + 积分退款"""
    from app.api.v1 import publish as publish_api
    from app.models.publish import PublishRecord, PublishStatus

    test_user.credits = 100
    db_session.commit()

    account = _create_platform_account(db_session, test_user.id)
    creation = _create_creation(db_session, test_user.id)

    monkeypatch.setattr(
        publish_api,
        "get_platform",
        lambda _platform: _build_mock_publisher(
            exc=TimeoutError("Timeout 30000ms exceeded")
        ),
    )

    response = client.post(
        "/api/v1/publish/publish",
        headers=auth_headers,
        json=_publish_payload(account.id, creation.id),
    )

    assert response.status_code == 400
    assert "Timeout 30000ms exceeded" in response.json()["message"]

    record = (
        db_session.query(PublishRecord)
        .filter(PublishRecord.creation_id == creation.id)
        .first()
    )
    assert record is not None
    assert record.status == PublishStatus.FAILED

    db_session.refresh(test_user)
    assert test_user.credits == 100


def test_publish_draft_success_returns_200_consumes_credits_and_saves_record(
    client, db_session, auth_headers, test_user, monkeypatch
):
    """草稿创建成功 → 200 + 成功记录 + 扣除 10 积分"""
    from app.api.v1 import publish as publish_api
    from app.models.publish import PublishRecord, PublishStatus

    test_user.credits = 100
    db_session.commit()

    account = _create_platform_account(db_session, test_user.id)
    creation = _create_creation(db_session, test_user.id)

    monkeypatch.setattr(
        publish_api,
        "get_platform",
        lambda _platform: _build_mock_publisher(
            result={
                "success": True,
                "draft_id": "draft_1",
                "draft_url": "https://creator.xiaohongshu.com/creator/post-manage",
                "message": "草稿已保存",
            }
        ),
    )

    response = client.post(
        "/api/v1/publish/publish",
        headers=auth_headers,
        json=_publish_payload(account.id, creation.id),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["platform_post_id"] == "draft_1"

    record = (
        db_session.query(PublishRecord)
        .filter(PublishRecord.creation_id == creation.id)
        .first()
    )
    assert record is not None
    assert record.status == PublishStatus.SUCCESS

    db_session.refresh(test_user)
    assert test_user.credits == 90


def test_publish_without_account_returns_404(client, auth_headers, test_user, db_session):
    """账号不存在/未激活 → 404，不扣积分"""
    from app.models.publish import PublishRecord

    test_user.credits = 100
    db_session.commit()

    creation = _create_creation(db_session, test_user.id)

    response = client.post(
        "/api/v1/publish/publish",
        headers=auth_headers,
        json=_publish_payload(account_id=999999, creation_id=creation.id),
    )

    assert response.status_code == 404
    assert db_session.query(PublishRecord).count() == 0
    db_session.refresh(test_user)
    assert test_user.credits == 100
