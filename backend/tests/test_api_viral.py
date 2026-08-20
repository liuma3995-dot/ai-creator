"""
爆款分析/模仿 API 与历史记录联动测试
"""
import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


AI_ANALYZE_RESPONSE = json.dumps({
    "title": "爆款分析测试",
    "category": "knowledge",
    "viral_score": 85,
    "tone": "轻松活泼",
    "target_audience": "职场人群",
    "emotional_triggers": ["身份认同"],
    "viral_elements": [
        {
            "name": "开头钩子",
            "description": "前3秒抓住注意力",
            "score": 90,
            "examples": ["文中示例1"],
        }
    ],
    "structure": {
        "sections": ["第一段：xxx", "第二段：xxx"],
        "opening_hook": "开头钩子分析",
        "closing_cta": "结尾CTA分析",
        "transition_style": "过渡风格",
    },
    "writing_techniques": ["技巧1", "技巧2"],
    "keywords": ["关键词1", "关键词2"],
    "improvement_suggestions": ["改进建议1"],
})

AI_IMITATE_RESPONSE = json.dumps({
    "title": "模仿生成的标题",
    "content": "这是模仿生成的正文内容。",
    "imitation_notes": ["保留原文语气"],
    "elements_applied": ["hook"],
    "word_count": 12,
    "estimated_viral_score": 70,
})


class TestViralAPI:
    """测试爆款分析/模仿 API"""

    def _make_model(self, db_session, test_user):
        """构造用户默认 AI 模型"""
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

    @patch("app.services.langchain.LangChainService")
    def test_analyze_saves_creation(self, mock_lc, client, auth_headers, db_session, test_user):
        """爆款分析成功后必须落库，历史记录可见、使用次数可统计"""
        from app.models.creation import Creation, CreationStatus, CreationType

        test_user.credits = 100
        db_session.commit()
        self._make_model(db_session, test_user)
        mock_service = mock_lc.return_value
        mock_service.chat = AsyncMock(return_value=SimpleNamespace(content=AI_ANALYZE_RESPONSE))

        response = client.post(
            "/api/v1/viral/analyze",
            headers=auth_headers,
            json={
                "content": "这是一段足够长的爆款分析测试内容。" * 8,
                "title": "测试标题",
                "platform": "xiaohongshu",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "爆款分析测试"
        assert data["creation_id"] is not None

        creation = (
            db_session.query(Creation)
            .filter(Creation.tool_type == "viral_analyze")
            .first()
        )
        assert creation is not None
        assert creation.creation_type == CreationType.WECHAT_ARTICLE
        assert creation.status == CreationStatus.COMPLETED
        assert creation.title == "爆款分析测试"
        assert "# 爆款分析报告" in creation.output_content

    def test_get_creations_filter_by_tool_type(self, client, auth_headers, db_session, test_user):
        """历史记录按 tool_type 筛选必须命中（修复 creation_type 误过滤）"""
        from app.models.creation import Creation, CreationStatus, CreationType

        creation = Creation(
            user_id=test_user.id,
            creation_type=CreationType.WECHAT_ARTICLE,
            tool_type="viral_imitate",
            title="爆款模仿记录",
            output_content="模仿生成的内容",
            status=CreationStatus.COMPLETED,
        )
        db_session.add(creation)
        db_session.commit()

        response = client.get(
            "/api/v1/creations",
            params={"tool_type": "viral_imitate"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["tool_type"] == "viral_imitate"

    def test_create_creation_saves_tool_type(self, client, auth_headers, db_session, test_user):
        """通用创建接口必须写入 tool_type"""
        from app.models.creation import Creation

        response = client.post(
            "/api/v1/creations",
            headers=auth_headers,
            json={
                "title": "通用创建测试",
                "content": "正文内容",
                "creation_type": "WECHAT_ARTICLE",
                "tool_type": "viral_analyze",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tool_type"] == "viral_analyze"

        creation = db_session.query(Creation).filter(Creation.id == data["id"]).first()
        assert creation.tool_type == "viral_analyze"

    @patch("app.services.langchain.LangChainService")
    def test_analyze_consumes_credits_for_normal_user(self, mock_lc, client, auth_headers, db_session, test_user):
        """C1 非会员调用爆款分析：扣 10 积分并记录交易流水"""
        from app.models.credit import CreditTransaction
        from app.models.user import User

        test_user.credits = 100
        db_session.commit()
        self._make_model(db_session, test_user)
        mock_service = mock_lc.return_value
        mock_service.chat = AsyncMock(return_value=SimpleNamespace(content=AI_ANALYZE_RESPONSE))

        response = client.post(
            "/api/v1/viral/analyze",
            headers=auth_headers,
            json={"content": "这是一段足够长的爆款分析测试内容。" * 8, "title": "测试标题"},
        )
        assert response.status_code == 200

        refreshed = db_session.query(User).filter(User.id == test_user.id).first()
        assert refreshed.credits == 90

        tx = (
            db_session.query(CreditTransaction)
            .filter(CreditTransaction.user_id == test_user.id)
            .order_by(CreditTransaction.id.desc())
            .first()
        )
        assert tx is not None
        assert tx.amount == -10
        assert "viral_analyze" in tx.description

    @patch("app.services.langchain.LangChainService")
    def test_imitate_consumes_credits_for_normal_user(self, mock_lc, client, auth_headers, db_session, test_user):
        """C2 非会员调用爆款模仿：扣 10 积分并记录交易流水"""
        from app.models.credit import CreditTransaction
        from app.models.user import User

        test_user.credits = 100
        db_session.commit()
        self._make_model(db_session, test_user)
        mock_service = mock_lc.return_value
        mock_service.chat = AsyncMock(return_value=SimpleNamespace(content=AI_IMITATE_RESPONSE))

        response = client.post(
            "/api/v1/viral/imitate",
            headers=auth_headers,
            json={
                "reference_content": "这是一段足够长的爆款参考内容。" * 8,
                "new_topic": "新主题",
            },
        )
        assert response.status_code == 200

        refreshed = db_session.query(User).filter(User.id == test_user.id).first()
        assert refreshed.credits == 90

        tx = (
            db_session.query(CreditTransaction)
            .filter(CreditTransaction.user_id == test_user.id)
            .order_by(CreditTransaction.id.desc())
            .first()
        )
        assert tx is not None
        assert tx.amount == -10
        assert "viral_imitate" in tx.description

    @patch("app.services.langchain.LangChainService")
    def test_analyze_member_not_charged(self, mock_lc, client, auth_headers, db_session, test_user):
        """C3 会员调用爆款分析：不扣积分"""
        from app.models.user import User

        test_user.credits = 100
        test_user.is_member = 1
        test_user.member_expired_at = datetime.utcnow() + timedelta(days=30)
        db_session.commit()
        self._make_model(db_session, test_user)
        mock_service = mock_lc.return_value
        mock_service.chat = AsyncMock(return_value=SimpleNamespace(content=AI_ANALYZE_RESPONSE))

        response = client.post(
            "/api/v1/viral/analyze",
            headers=auth_headers,
            json={"content": "这是一段足够长的爆款分析测试内容。" * 8, "title": "测试标题"},
        )
        assert response.status_code == 200

        refreshed = db_session.query(User).filter(User.id == test_user.id).first()
        assert refreshed.credits == 100

    @patch("app.services.langchain.LangChainService")
    def test_analyze_insufficient_credits(self, mock_lc, client, auth_headers, db_session, test_user):
        """C4 积分不足：HTTP 402，不生成、不落库"""
        from app.models.creation import Creation
        from app.models.user import User

        test_user.credits = 5
        db_session.commit()
        self._make_model(db_session, test_user)

        response = client.post(
            "/api/v1/viral/analyze",
            headers=auth_headers,
            json={"content": "这是一段足够长的爆款分析测试内容。" * 8, "title": "测试标题"},
        )
        assert response.status_code == 402

        refreshed = db_session.query(User).filter(User.id == test_user.id).first()
        assert refreshed.credits == 5
        creation = db_session.query(Creation).filter(Creation.tool_type == "viral_analyze").first()
        assert creation is None

    @patch("app.services.viral_analyzer_service.ViralAnalyzerService.analyze", new_callable=AsyncMock)
    def test_analyze_refunds_on_failure(self, mock_analyze, client, auth_headers, db_session, test_user):
        """C5 爆款分析 AI 调用失败：自动退款，积分与流水一致"""
        from app.models.credit import CreditTransaction
        from app.models.user import User

        test_user.credits = 100
        db_session.commit()
        self._make_model(db_session, test_user)
        mock_analyze.side_effect = Exception("AI 服务异常")

        response = client.post(
            "/api/v1/viral/analyze",
            headers=auth_headers,
            json={"content": "这是一段足够长的爆款分析测试内容。" * 8, "title": "测试标题"},
        )
        assert response.status_code == 500

        refreshed = db_session.query(User).filter(User.id == test_user.id).first()
        assert refreshed.credits == 100

        txs = (
            db_session.query(CreditTransaction)
            .filter(CreditTransaction.user_id == test_user.id)
            .order_by(CreditTransaction.id)
            .all()
        )
        assert len(txs) == 2
        assert txs[0].amount == -10
        assert txs[1].amount == 10
