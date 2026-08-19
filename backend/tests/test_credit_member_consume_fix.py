# -*- coding: utf-8 -*-
"""会员不扣积分 + 统一消费入口回归测试（D4）"""
from datetime import datetime, timedelta

import pytest


class TestMemberAwareConsume:
    def test_member_not_deducted(self, db_session, test_user):
        """会员调用统一消费入口不扣积分、不产生流水"""
        from app.models.user import User
        from app.models.credit import CreditTransaction
        from app.services.credit_service import CreditService

        user = db_session.query(User).filter(User.id == test_user.id).first()
        user.is_member = 1
        user.member_expired_at = datetime.now() + timedelta(days=30)
        before = user.credits

        ok = CreditService.check_and_consume_credits(
            db=db_session,
            user_id=user.id,
            amount=10,
            description="视频生成测试",
            related_id=999,
            related_type="creation",
            commit=False,
        )
        db_session.commit()
        db_session.refresh(user)

        assert ok
        assert user.credits == before
        tx = (
            db_session.query(CreditTransaction)
            .filter(CreditTransaction.related_id == 999)
            .first()
        )
        assert tx is None

    def test_non_member_deducted_on_commit(self, db_session, test_user):
        """非会员：commit=False 时先挂起扣费，调用方 commit 后落库"""
        from app.models.user import User
        from app.models.credit import CreditTransaction
        from app.services.credit_service import CreditService

        user = db_session.query(User).filter(User.id == test_user.id).first()
        user.is_member = 0
        user.member_expired_at = None
        user.credits = 100
        db_session.commit()
        before = user.credits

        CreditService.check_and_consume_credits(
            db=db_session,
            user_id=user.id,
            amount=10,
            description="视频生成测试",
            related_id=998,
            related_type="creation",
            commit=False,
        )
        # 未提交前数据库余额不变
        db_session.commit()
        db_session.refresh(user)
        assert user.credits == before - 10

        tx = (
            db_session.query(CreditTransaction)
            .filter(CreditTransaction.related_id == 998)
            .first()
        )
        assert tx is not None
        assert tx.amount == -10

    def test_insufficient_raises_business_exception(self, db_session, test_user):
        """非会员余额不足时抛 BusinessException 且不扣费"""
        from app.core.exceptions import BusinessException
        from app.models.user import User
        from app.services.credit_service import CreditService

        user = db_session.query(User).filter(User.id == test_user.id).first()
        user.is_member = 0
        user.credits = 1
        db_session.commit()

        with pytest.raises(BusinessException):
            CreditService.check_and_consume_credits(
                db=db_session,
                user_id=user.id,
                amount=10,
                description="测试",
                commit=False,
            )
        db_session.rollback()
        db_session.refresh(user)
        assert user.credits == 1
