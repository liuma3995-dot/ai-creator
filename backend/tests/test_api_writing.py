"""
测试写作API
"""
import pytest
from unittest.mock import patch, AsyncMock


class TestWritingAPI:
    """测试写作相关API"""
    
    def test_get_writing_tools(self, client, auth_headers):
        """测试获取写作工具列表"""
        response = client.get(
            "/api/v1/writing/tools",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        
        # 验证工具信息结构
        tool = data[0]
        assert "tool_type" in tool
        assert "name" in tool
        assert "description" in tool
    
    @patch('app.services.writing_service.WritingService.generate_content')
    def test_generate_content_success(self, mock_generate, client, auth_headers, db_session, test_user):
        """测试成功生成内容"""
        from app.models.user import User
        from app.core.exceptions import BusinessException

        test_user.credits = 100
        db_session.commit()
        model = self._make_model(db_session, test_user)
        mock_generate.return_value = "这是生成的内容"
        
        response = client.post(
            "/api/v1/writing/generate",
            headers=auth_headers,
            json={
                "tool_type": "wechat_article",
                "model_id": model.id,
                "parameters": {
                    "topic": "AI文章",
                }
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["output_content"] == "这是生成的内容"
        assert data["tool_type"] == "wechat_article"
        # 非会员生成扣 10 积分
        refreshed = db_session.query(User).filter(User.id == test_user.id).first()
        assert refreshed.credits == 90
    
    def test_generate_content_unauthorized(self, client):
        """测试未授权生成内容"""
        response = client.post(
            "/api/v1/writing/generate",
            json={
                "tool_type": "wechat_article",
            }
        )
        assert response.status_code == 401
    
    @patch('app.services.writing_service.WritingService.generate_content')
    def test_generate_content_invalid_tool_type(self, mock_generate, client, auth_headers, db_session, test_user):
        """测试无效的工具类型"""
        from app.core.exceptions import BusinessException

        test_user.credits = 100
        db_session.commit()
        model = self._make_model(db_session, test_user)
        mock_generate.side_effect = BusinessException("不支持的写作工具类型")

        response = client.post(
            "/api/v1/writing/generate",
            headers=auth_headers,
            json={
                "tool_type": "invalid_tool",
                "model_id": model.id,
            }
        )
        assert response.status_code == 400
    
    def test_generate_content_missing_prompt(self, client, auth_headers):
        """测试缺少提示词"""
        response = client.post(
            "/api/v1/writing/generate",
            headers=auth_headers,
            json={}
        )
        assert response.status_code == 422
    
    @patch('app.services.writing_service.WritingService.generate_content')
    def test_regenerate_content_with_parameters(self, mock_generate, client, auth_headers, db_session, test_user):
        """测试重新生成携带当前表单参数（含补充说明）"""
        from app.models.user import User

        test_user.credits = 100
        db_session.commit()
        creation = self._make_creation_with_model(db_session, test_user)

        async def fake_generate(*args, **kwargs):
            return "重新生成内容"

        mock_generate.side_effect = fake_generate

        response = client.post(
            f"/api/v1/writing/creations/{creation.id}/regenerate",
            headers=auth_headers,
            json={
                "parameters": {
                    "topic": "AI主题",
                    "additional_description": "字数要求：不少于500字",
                }
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == creation.id
        assert data["output_content"] == "重新生成内容"

        # 校验补充说明确实传入了生成服务
        user_input = mock_generate.call_args.kwargs["user_input"]
        assert user_input.get("additional_description") == "字数要求：不少于500字"

        # 积分扣减（非会员每次10积分）
        refreshed = db_session.query(User).filter(User.id == test_user.id).first()
        assert refreshed.credits == 90

    @patch('app.services.writing_service.WritingService.generate_content')
    def test_regenerate_content_fallback_to_saved_input(self, mock_generate, client, auth_headers, db_session, test_user):
        """测试不传参数时回退到已保存的输入数据"""
        test_user.credits = 100
        db_session.commit()
        creation = self._make_creation_with_model(db_session, test_user)
        creation.input_data = {"topic": "旧主题", "additional_description": "旧补充说明"}
        db_session.commit()

        async def fake_generate(*args, **kwargs):
            return "内容"

        mock_generate.side_effect = fake_generate

        response = client.post(
            f"/api/v1/writing/creations/{creation.id}/regenerate",
            headers=auth_headers,
        )
        assert response.status_code == 200
        user_input = mock_generate.call_args.kwargs["user_input"]
        assert user_input.get("additional_description") == "旧补充说明"
    
    def _make_creation_with_model(self, db_session, test_user):
        """构造带模型的创作记录"""
        from app.models.creation import Creation, CreationType
        ai_model = self._make_model(db_session, test_user)

        creation = Creation(
            user_id=test_user.id,
            creation_type=CreationType.WECHAT_ARTICLE,
            tool_type="wechat_article",
            title="测试",
            output_content="原内容",
            model_id=ai_model.id,
            status="completed",
        )
        db_session.add(creation)
        db_session.commit()
        db_session.refresh(creation)
        return creation

    def _make_model(self, db_session, test_user):
        """构造 AI 模型"""
        from app.models.ai_model import AIModel

        ai_model = AIModel(
            user_id=test_user.id,
            name="测试模型",
            provider="openai",
            model_name="gpt-4o-mini",
            api_key="test-key",
        )
        db_session.add(ai_model)
        db_session.commit()
        db_session.refresh(ai_model)
        return ai_model

    @patch('app.services.writing_service.WritingService.optimize_content')
    def test_optimize_content_multi_types(self, mock_optimize, client, auth_headers, db_session, test_user):
        """测试多类型顺序优化内容"""
        from app.models.user import User

        test_user.credits = 100
        db_session.commit()
        creation = self._make_creation_with_model(db_session, test_user)

        mock_optimize.return_value = "优化后的内容"

        response = client.post(
            f"/api/v1/writing/{creation.id}/optimize",
            headers=auth_headers,
            json={"optimize_types": ["seo", "style"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == creation.id
        assert data["output_content"] == "优化后的内容"
        assert mock_optimize.call_count == 2

        # 积分应扣减（非会员每次优化10积分）
        refreshed = db_session.query(User).filter(User.id == test_user.id).first()
        assert refreshed.credits == 90

    @patch('app.services.writing_service.WritingService.optimize_content')
    def test_optimize_content_single_type(self, mock_optimize, client, auth_headers, db_session, test_user):
        """测试兼容单类型 optimization_type 参数"""
        test_user.credits = 100
        db_session.commit()
        creation = self._make_creation_with_model(db_session, test_user)

        mock_optimize.return_value = "SEO优化后的内容"

        response = client.post(
            f"/api/v1/writing/{creation.id}/optimize",
            headers=auth_headers,
            json={"optimization_type": "seo"},
        )
        assert response.status_code == 200
        assert response.json()["output_content"] == "SEO优化后的内容"
        assert mock_optimize.call_count == 1

    def test_optimize_content_not_found(self, client, auth_headers):
        """测试优化不存在的创作"""
        response = client.post(
            "/api/v1/writing/99999/optimize",
            headers=auth_headers,
            json={"optimize_types": ["seo"]},
        )
        assert response.status_code == 404

    def test_optimize_content_missing_type(self, client, auth_headers, db_session, test_user):
        """测试未选择优化类型"""
        creation = self._make_creation_with_model(db_session, test_user)
        response = client.post(
            f"/api/v1/writing/{creation.id}/optimize",
            headers=auth_headers,
            json={},
        )
        assert response.status_code == 400

    @patch('app.services.writing_service.WritingService.optimize_content')
    def test_optimize_content_invalid_type(self, mock_optimize, client, auth_headers, db_session, test_user):
        """测试不支持的优化类型返回400并退还积分"""
        from app.models.user import User

        test_user.credits = 100
        db_session.commit()
        creation = self._make_creation_with_model(db_session, test_user)

        mock_optimize.side_effect = ValueError("不支持的优化类型: xxx")

        response = client.post(
            f"/api/v1/writing/{creation.id}/optimize",
            headers=auth_headers,
            json={"optimize_types": ["xxx"]},
        )
        assert response.status_code == 400

        refreshed = db_session.query(User).filter(User.id == test_user.id).first()
        assert refreshed.credits == 100
    
    def test_get_creation_detail(self, client, auth_headers, db_session, test_user):
        """测试获取创作详情"""
        from app.models.creation import Creation, CreationType
        
        creation = Creation(
            user_id=test_user.id,
            creation_type=CreationType.WECHAT_ARTICLE,
            tool_type="wechat_article",
            title="测试文章",
            output_content="内容",
            input_data={"topic": "提示词"},
            status="completed"
        )
        db_session.add(creation)
        db_session.commit()
        db_session.refresh(creation)
        
        response = client.get(
            f"/api/v1/creations/{creation.id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == creation.id
        assert data["title"] == "测试文章"
    
    def test_update_creation(self, client, auth_headers, db_session, test_user):
        """测试更新创作内容"""
        from app.models.creation import Creation, CreationType
        
        creation = Creation(
            user_id=test_user.id,
            creation_type=CreationType.WECHAT_ARTICLE,
            tool_type="wechat_article",
            title="原标题",
            output_content="原内容",
            input_data={"topic": "提示词"},
            status="completed"
        )
        db_session.add(creation)
        db_session.commit()
        db_session.refresh(creation)
        
        response = client.put(
            f"/api/v1/creations/{creation.id}",
            headers=auth_headers,
            json={
                "title": "新标题",
                "content": "新内容"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "新标题"
        assert data["output_content"] == "新内容"
    
    def test_delete_creation(self, client, auth_headers, db_session, test_user):
        """测试删除创作"""
        from app.models.creation import Creation, CreationType
        
        creation = Creation(
            user_id=test_user.id,
            creation_type=CreationType.WECHAT_ARTICLE,
            tool_type="wechat_article",
            title="测试",
            output_content="内容",
            input_data={"topic": "提示词"},
            status="completed"
        )
        db_session.add(creation)
        db_session.commit()
        db_session.refresh(creation)
        
        response = client.delete(
            f"/api/v1/creations/{creation.id}",
            headers=auth_headers
        )
        assert response.status_code == 200
    
    def test_list_creations(self, client, auth_headers, db_session, test_user):
        """测试获取创作列表"""
        from app.models.creation import Creation, CreationType
        
        # 创建多个创作记录
        for i in range(5):
            creation = Creation(
                user_id=test_user.id,
                creation_type=CreationType.WECHAT_ARTICLE,
                tool_type="wechat_article",
                title=f"测试文章{i}",
                output_content=f"内容{i}",
                input_data={"topic": "提示词"},
                status="completed"
            )
            db_session.add(creation)
        db_session.commit()
        
        response = client.get(
            "/api/v1/creations",
            headers=auth_headers,
            params={"skip": 0, "limit": 10}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 5
        assert data["total"] == 5
    
    def test_list_creations_with_filter(self, client, auth_headers, db_session, test_user):
        """测试带过滤条件的创作列表"""
        from app.models.creation import Creation, CreationType
        
        # 创建不同类型的创作
        wechat = Creation(
            user_id=test_user.id,
            creation_type=CreationType.WECHAT_ARTICLE,
            tool_type="wechat_article",
            title="微信文章",
            output_content="内容",
            input_data={"topic": "提示词"},
            status="completed"
        )
        xhs = Creation(
            user_id=test_user.id,
            creation_type=CreationType.XIAOHONGSHU_NOTE,
            tool_type="xiaohongshu_note",
            title="小红书笔记",
            output_content="内容",
            input_data={"topic": "提示词"},
            status="completed"
        )
        db_session.add(wechat)
        db_session.add(xhs)
        db_session.commit()
        
        response = client.get(
            "/api/v1/creations",
            headers=auth_headers,
            params={"tool_type": "wechat_article"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["tool_type"] == "wechat_article"
