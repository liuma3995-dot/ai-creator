# -*- coding: utf-8 -*-
"""
AI 选题建议模型选择链路接口测试
"""
import json
from types import SimpleNamespace


def _make_ai_response():
    """构造模拟 AI 返回的选题建议 JSON"""
    return json.dumps({
        "background": "这是一个热点背景",
        "angles": [
            {
                "angle": "深度解读",
                "title_suggestion": "标题示例",
                "content_direction": "内容方向",
                "recommended_tools": ["wechat_article"],
                "target_audience": "目标受众",
            }
        ],
        "keywords": ["关键词1", "关键词2"],
    }, ensure_ascii=False)


def _install_fake_langchain(monkeypatch, fail=False):
    """替换服务层 LangChainService，避免真实调用模型"""

    class FakeLangChainService:
        def __init__(self, *args, **kwargs):
            pass

        async def chat(self, prompt):
            if fail:
                raise RuntimeError("mock AI 调用失败")
            return SimpleNamespace(content=_make_ai_response())

    monkeypatch.setattr(
        "app.services.langchain.LangChainService", FakeLangChainService
    )


def _create_model(db_session, user, name="测试模型", capabilities=("text",), is_default=False):
    from app.models.ai_model import AIModel

    model = AIModel(
        user_id=user.id,
        name=name,
        provider="minimax",
        model_name="MiniMax-M3",
        api_key="sk-test",
        base_url="https://api.minimaxi.com/v1",
        is_active=True,
        is_default=is_default,
        capabilities=list(capabilities),
    )
    db_session.add(model)
    db_session.commit()
    db_session.refresh(model)
    return model


class TestTopicSuggestModelSelection:
    def test_suggest_without_text_model_returns_400(
        self, client, db_session, auth_headers, test_user, monkeypatch
    ):
        """没有任何文本模型时返回 400 明确提示（不再静默用第一个模型）"""
        _install_fake_langchain(monkeypatch)

        response = client.post(
            "/api/v1/hotspot/suggest",
            headers=auth_headers,
            json={"hot_title": "热点标题", "url": None},
        )

        assert response.status_code == 400
        assert "文本生成" in response.json()["message"]

    def test_suggest_filters_video_models(
        self, client, db_session, auth_headers, test_user, monkeypatch
    ):
        """只有视频能力模型时同样 400（text 能力过滤生效）"""
        _install_fake_langchain(monkeypatch)
        _create_model(db_session, test_user, name="视频模型", capabilities=("video",))

        response = client.post(
            "/api/v1/hotspot/suggest",
            headers=auth_headers,
            json={"hot_title": "热点标题", "url": None},
        )

        assert response.status_code == 400

    def test_suggest_with_specified_model_id(
        self, client, db_session, auth_headers, test_user, monkeypatch
    ):
        """前端指定 model_id 时使用该模型，响应返回模型信息"""
        _install_fake_langchain(monkeypatch)
        m1 = _create_model(db_session, test_user, name="模型A")
        m2 = _create_model(db_session, test_user, name="模型B")

        response = client.post(
            "/api/v1/hotspot/suggest",
            headers=auth_headers,
            json={"hot_title": "热点标题", "url": None, "model_id": m2.id},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["model"]["name"] == "模型B"
        assert data["model"]["provider"] == "minimax"
        assert data["is_fallback"] is False
        assert data["background"] == "这是一个热点背景"

    def test_suggest_with_invalid_model_id_returns_400(
        self, client, db_session, auth_headers, test_user, monkeypatch
    ):
        """指定的 model_id 不属于用户/未启用时返回 400"""
        _install_fake_langchain(monkeypatch)
        _create_model(db_session, test_user, name="模型A")

        response = client.post(
            "/api/v1/hotspot/suggest",
            headers=auth_headers,
            json={"hot_title": "热点标题", "url": None, "model_id": 99999},
        )

        assert response.status_code == 400
        assert "不存在" in response.json()["message"]

    def test_suggest_uses_default_model_when_not_specified(
        self, client, db_session, auth_headers, test_user, monkeypatch
    ):
        """未传 model_id 时优先使用默认模型"""
        _install_fake_langchain(monkeypatch)
        _create_model(db_session, test_user, name="普通模型")
        default_model = _create_model(
            db_session, test_user, name="默认模型", is_default=True
        )

        response = client.post(
            "/api/v1/hotspot/suggest",
            headers=auth_headers,
            json={"hot_title": "热点标题", "url": None},
        )

        assert response.status_code == 200
        assert response.json()["model"]["name"] == "默认模型"
        assert default_model.id is not None

    def test_suggest_marks_fallback_when_ai_fails(
        self, client, db_session, auth_headers, test_user, monkeypatch
    ):
        """AI 调用失败时返回 is_fallback=True 的模板建议（不再静默）"""
        _install_fake_langchain(monkeypatch, fail=True)
        _create_model(db_session, test_user, name="模型A")

        response = client.post(
            "/api/v1/hotspot/suggest",
            headers=auth_headers,
            json={"hot_title": "热点标题", "url": None},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_fallback"] is True
        assert data["model"]["name"] == "模型A"
        assert data["keywords"]

    def test_suggest_unauthenticated_returns_fallback(
        self, client, monkeypatch
    ):
        """未登录用户返回模板建议且 is_fallback=True"""
        _install_fake_langchain(monkeypatch)

        response = client.post(
            "/api/v1/hotspot/suggest",
            json={"hot_title": "热点标题", "url": None},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_fallback"] is True
        assert data["model"] is None
