# -*- coding: utf-8 -*-
"""
AI 模型列表与选择链路 API 回归测试
"""


class TestModelsAPI:
    """AI 模型列表接口回归测试"""

    def _create_model(
        self,
        db_session,
        user,
        name="TestModel",
        provider="openai",
        model_name="gpt-4o",
        capabilities=("text",),
    ):
        from app.models.ai_model import AIModel

        model = AIModel(
            user_id=user.id,
            name=name,
            provider=provider,
            model_name=model_name,
            api_key="sk-test-123",
            is_active=True,
            capabilities=list(capabilities),
        )
        db_session.add(model)
        db_session.commit()
        db_session.refresh(model)
        return model

    @staticmethod
    def _unwrap(response_json):
        """兼容 {code,data} 包装与裸列表两种响应形态"""
        return response_json["data"] if isinstance(response_json, dict) else response_json

    def test_capability_filter_returns_multi_capability_models(
        self, client, auth_headers, db_session, test_user
    ):
        """多能力模型（text+image）在 text/image 过滤下都应返回（回归：JSON contains 过滤失效）"""
        text_only = self._create_model(db_session, test_user, name="文本模型", capabilities=["text"])
        multi = self._create_model(
            db_session, test_user, name="多能力模型", capabilities=["text", "image"]
        )

        response = client.get("/api/v1/models?capability=text", headers=auth_headers)
        assert response.status_code == 200
        ids = {m["id"] for m in self._unwrap(response.json())}
        assert text_only.id in ids
        assert multi.id in ids

        response = client.get("/api/v1/models?capability=image", headers=auth_headers)
        assert response.status_code == 200
        ids = {m["id"] for m in self._unwrap(response.json())}
        assert multi.id in ids
        assert text_only.id not in ids

    def test_capability_filter_returns_video_models(self, client, auth_headers, db_session, test_user):
        """video 过滤能返回包含 video 能力的模型"""
        multi = self._create_model(
            db_session, test_user, name="视频模型", capabilities=["text", "video"]
        )

        response = client.get("/api/v1/models?capability=video", headers=auth_headers)
        assert response.status_code == 200
        ids = {m["id"] for m in self._unwrap(response.json())}
        assert multi.id in ids

    def test_models_response_includes_provider_and_model_name(
        self, client, auth_headers, db_session, test_user
    ):
        """模型列表响应必须包含 provider/model_name（回归：写作页显示 (undefined)）"""
        model = self._create_model(
            db_session, test_user, name="GPT-4", provider="openai", model_name="gpt-4o"
        )

        response = client.get("/api/v1/models", headers=auth_headers)
        assert response.status_code == 200
        item = next(x for x in self._unwrap(response.json()) if x["id"] == model.id)
        assert item["provider"] == "openai"
        assert item["model_name"] == "gpt-4o"
