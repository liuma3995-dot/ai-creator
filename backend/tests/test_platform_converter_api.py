# -*- coding: utf-8 -*-
"""平台内容转换接口测试：验证积分扣减/退款/会员免扣规则"""
import pytest
from unittest.mock import patch

from app.models.credit import CreditTransaction, TransactionType
from app.models.user import User


def _make_user_with_model(db_session, test_user, credits=100, is_member=False):
    """给测试用户配置积分与默认 AI 模型"""
    from app.models.ai_model import AIModel

    test_user.credits = credits
    test_user.is_member = is_member
    db_session.add(AIModel(
        user_id=test_user.id,
        name="转换测试模型",
        provider="openai",
        model_name="gpt-4",
        api_key="test-key",
        is_active=True,
    ))
    db_session.commit()


def _convert_result():
    from app.schemas.platform_converter import ConvertResult

    return ConvertResult(
        original_platform="xiaohongshu_note",
        target_platform="wechat_article",
        original_title="原标题",
        converted_title="转换后标题",
        converted_content="转换后内容",
        tags=["#AI"],
        word_count=10,
        conversion_notes=[],
        creation_id=99,
    )


def _batch_result():
    from app.schemas.platform_converter import BatchConvertResult

    return BatchConvertResult(
        original_creation_id=1,
        results=[_convert_result(), _convert_result()],
        success_count=2,
        failed_count=0,
    )


class TestPlatformConverterCredits:
    """平台转换积分规则测试"""

    @patch('app.services.platform_converter_service.PlatformConverterService.convert')
    def test_convert_consumes_credits(self, mock_convert, client, auth_headers, db_session, test_user):
        """单次转换消耗 10 积分"""
        _make_user_with_model(db_session, test_user)

        async def fake_convert(*args, **kwargs):
            return _convert_result()

        mock_convert.side_effect = fake_convert

        response = client.post(
            "/api/v1/converter/convert",
            headers=auth_headers,
            json={"creation_id": 1, "target_platform": "wechat_article"},
        )
        assert response.status_code == 200
        assert response.json()["target_platform"] == "wechat_article"

        refreshed = db_session.query(User).filter(User.id == test_user.id).first()
        assert refreshed.credits == 90

        tx = db_session.query(CreditTransaction).filter(
            CreditTransaction.user_id == test_user.id,
            CreditTransaction.transaction_type == TransactionType.CONSUME,
        ).first()
        assert tx is not None
        assert tx.amount == -10

    @patch('app.services.platform_converter_service.PlatformConverterService.convert')
    def test_convert_insufficient_credits(self, mock_convert, client, auth_headers, db_session, test_user):
        """积分不足返回 402 且不调用转换服务"""
        _make_user_with_model(db_session, test_user, credits=5)

        response = client.post(
            "/api/v1/converter/convert",
            headers=auth_headers,
            json={"creation_id": 1, "target_platform": "wechat_article"},
        )
        assert response.status_code == 402
        mock_convert.assert_not_called()

    @patch('app.services.platform_converter_service.PlatformConverterService.batch_convert')
    def test_batch_convert_consumes_per_platform(self, mock_batch, client, auth_headers, db_session, test_user):
        """批量转换按平台数量扣积分（2 个平台 = 20 积分）"""
        _make_user_with_model(db_session, test_user)

        async def fake_batch(*args, **kwargs):
            return _batch_result()

        mock_batch.side_effect = fake_batch

        response = client.post(
            "/api/v1/converter/batch-convert",
            headers=auth_headers,
            json={
                "creation_id": 1,
                "target_platforms": ["wechat_article", "zhihu_answer"],
            },
        )
        assert response.status_code == 200
        assert response.json()["success_count"] == 2

        refreshed = db_session.query(User).filter(User.id == test_user.id).first()
        assert refreshed.credits == 80

    @patch('app.services.platform_converter_service.PlatformConverterService.convert')
    def test_convert_refund_on_failure(self, mock_convert, client, auth_headers, db_session, test_user):
        """转换失败退还积分"""
        _make_user_with_model(db_session, test_user)
        mock_convert.side_effect = ValueError("转换失败")

        response = client.post(
            "/api/v1/converter/convert",
            headers=auth_headers,
            json={"creation_id": 1, "target_platform": "wechat_article"},
        )
        assert response.status_code == 400

        refreshed = db_session.query(User).filter(User.id == test_user.id).first()
        assert refreshed.credits == 100

        tx = db_session.query(CreditTransaction).filter(
            CreditTransaction.user_id == test_user.id,
            CreditTransaction.transaction_type == TransactionType.REFUND,
        ).first()
        assert tx is not None
        assert tx.amount == 10

    @patch('app.services.platform_converter_service.PlatformConverterService.convert')
    def test_convert_member_no_deduction(self, mock_convert, client, auth_headers, db_session, test_user):
        """会员转换不扣积分"""
        from datetime import datetime, timedelta

        _make_user_with_model(db_session, test_user, is_member=True)
        test_user.member_expired_at = datetime.now() + timedelta(days=30)
        db_session.commit()

        async def fake_convert(*args, **kwargs):
            return _convert_result()

        mock_convert.side_effect = fake_convert

        response = client.post(
            "/api/v1/converter/convert",
            headers=auth_headers,
            json={"creation_id": 1, "target_platform": "wechat_article"},
        )
        assert response.status_code == 200

        refreshed = db_session.query(User).filter(User.id == test_user.id).first()
        assert refreshed.credits == 100
