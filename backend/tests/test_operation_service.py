# -*- coding: utf-8 -*-
"""
运营管理模块服务层单元测试
覆盖：活动、优惠券、推广返利、运营统计
"""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.core.exceptions import BusinessException, NotFoundException
from app.models.operation import (
    Activity,
    ActivityParticipation,
    ActivityStatus,
    ActivityType,
    Coupon,
    CouponStatus,
    CouponType,
    ReferralRecord,
    ReferralStatus,
    UserCoupon,
)
from app.models.user import User
from app.models.credit import CreditTransaction, TransactionType
from app.schemas.operation import ActivityCreate, ActivityUpdate, CouponCreate
from app.services.operation_service import (
    ActivityService,
    CouponService,
    OperationService,
    ReferralService,
)


def _make_activity(db, **kwargs):
    """构造活动并落库"""
    defaults = dict(
        title="测试活动",
        activity_type=ActivityType.CREDIT_GIFT,
        status=ActivityStatus.ACTIVE,
        rules={},
        start_time=datetime.now() - timedelta(days=1),
        end_time=datetime.now() + timedelta(days=7),
    )
    defaults.update(kwargs)
    activity = Activity(**defaults)
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


def _make_coupon(db, **kwargs):
    """构造优惠券并落库"""
    defaults = dict(
        code="TEST100",
        name="测试优惠券",
        coupon_type=CouponType.RECHARGE_DISCOUNT,
        discount_type="percent",
        discount_value=Decimal("10"),
        valid_from=datetime.now() - timedelta(days=1),
        valid_until=datetime.now() + timedelta(days=7),
        is_active=True,
    )
    defaults.update(kwargs)
    coupon = Coupon(**defaults)
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return coupon


def _make_user_coupon(db, coupon, user, status=CouponStatus.UNUSED):
    user_coupon = UserCoupon(user_id=user.id, coupon_id=coupon.id, status=status)
    db.add(user_coupon)
    db.commit()
    db.refresh(user_coupon)
    return user_coupon


def _make_user(db, username, email, **kwargs):
    defaults = dict(password_hash="hashed")
    defaults.update(kwargs)
    user = User(username=username, email=email, **defaults)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class TestActivityService:
    """活动服务测试"""

    def test_create_activity_merges_reward_into_rules(self, db_session, test_user):
        data = ActivityCreate(
            title="积分赠送活动",
            activity_type="credit_gift",
            start_time=datetime.now() - timedelta(days=1),
            end_time=datetime.now() + timedelta(days=7),
            reward_type="credits",
            reward_amount=100,
        )
        activity = ActivityService.create_activity(db_session, data, test_user.id)

        assert activity.rules == {"reward_type": "credits", "reward_amount": 100}
        assert activity.created_by == test_user.id
        assert activity.status == ActivityStatus.DRAFT

    def test_create_activity_keeps_rules_when_no_reward_fields(self, db_session, test_user):
        data = ActivityCreate(
            title="无奖励活动",
            activity_type="referral",
            rules={"note": "仅记录"},
            start_time=datetime.now() - timedelta(days=1),
            end_time=datetime.now() + timedelta(days=7),
        )
        activity = ActivityService.create_activity(db_session, data, test_user.id)

        assert activity.rules == {"note": "仅记录"}
        assert activity.status == ActivityStatus.DRAFT

    def test_update_activity_not_found(self, db_session):
        with pytest.raises(NotFoundException, match="活动不存在"):
            ActivityService.update_activity(db_session, 9999, ActivityUpdate(title="新标题"))

    def test_update_activity_merges_reward_into_existing_rules(self, db_session):
        activity = _make_activity(
            db_session,
            rules={"reward_type": "credits", "reward_amount": 10, "note": "保留"},
        )
        updated = ActivityService.update_activity(
            db_session, activity.id, ActivityUpdate(reward_amount=50)
        )

        assert updated.rules == {"reward_type": "credits", "reward_amount": 50, "note": "保留"}

    def test_update_activity_fields(self, db_session):
        activity = _make_activity(db_session)
        updated = ActivityService.update_activity(
            db_session, activity.id, ActivityUpdate(title="改标题", max_participants=10)
        )
        assert updated.title == "改标题"
        assert updated.max_participants == 10

    def test_get_activity(self, db_session):
        activity = _make_activity(db_session)
        assert ActivityService.get_activity(db_session, activity.id).id == activity.id
        assert ActivityService.get_activity(db_session, 9999) is None

    def test_list_activities_filters_and_pagination(self, db_session):
        _make_activity(db_session, title="草稿", status=ActivityStatus.DRAFT)
        _make_activity(db_session, title="进行中A", status=ActivityStatus.ACTIVE)
        _make_activity(db_session, title="进行中B", status=ActivityStatus.ACTIVE)

        activities, total = ActivityService.list_activities(db_session, status="active")
        assert total == 2
        assert len(activities) == 2

        activities, total = ActivityService.list_activities(db_session, status="active", skip=1, limit=1)
        assert total == 2
        assert len(activities) == 1

    def test_participate_activity_not_found(self, db_session, test_user):
        with pytest.raises(BusinessException, match="活动不存在"):
            ActivityService.participate_activity(db_session, 9999, test_user.id)

    def test_participate_activity_inactive(self, db_session, test_user):
        activity = _make_activity(db_session, status=ActivityStatus.DRAFT)
        with pytest.raises(BusinessException, match="未开始或已结束"):
            ActivityService.participate_activity(db_session, activity.id, test_user.id)

    def test_participate_activity_out_of_time_range(self, db_session, test_user):
        activity = _make_activity(
            db_session,
            start_time=datetime.now() - timedelta(days=10),
            end_time=datetime.now() - timedelta(days=3),
        )
        with pytest.raises(BusinessException, match="不在活动时间范围内"):
            ActivityService.participate_activity(db_session, activity.id, test_user.id)

    def test_participate_activity_duplicate(self, db_session, test_user):
        activity = _make_activity(db_session, rules={"credits": 10})
        ActivityService.participate_activity(db_session, activity.id, test_user.id)
        with pytest.raises(BusinessException, match="已参与过"):
            ActivityService.participate_activity(db_session, activity.id, test_user.id)

    def test_participate_activity_full(self, db_session, test_user):
        activity = _make_activity(db_session, max_participants=1, current_participants=1)
        with pytest.raises(BusinessException, match="人数已满"):
            ActivityService.participate_activity(db_session, activity.id, test_user.id)

    def test_participate_credit_gift_rewards_credits(self, db_session, test_user):
        activity = _make_activity(db_session, rules={"credits": 50})
        user = db_session.query(User).filter(User.id == test_user.id).first()
        before = user.credits

        participation = ActivityService.participate_activity(db_session, activity.id, test_user.id)

        after = db_session.query(User).filter(User.id == test_user.id).first().credits
        assert after == before + 50
        assert participation.reward_type == "credits"
        assert participation.reward_amount == 50

        tx = db_session.query(CreditTransaction).filter(
            CreditTransaction.related_type == "activity",
            CreditTransaction.transaction_type == TransactionType.REWARD,
        ).first()
        assert tx is not None
        assert tx.amount == 50

        refreshed = db_session.query(Activity).filter(Activity.id == activity.id).first()
        assert refreshed.current_participants == 1


class TestCouponService:
    """优惠券服务测试"""

    def _coupon_create_data(self, code="SAVE10"):
        return CouponCreate(
            code=code,
            name="满减券",
            coupon_type="recharge_discount",
            discount_type="percent",
            discount_value=Decimal("10"),
            valid_from=datetime.now() - timedelta(days=1),
            valid_until=datetime.now() + timedelta(days=7),
        )

    def test_create_coupon_success(self, db_session):
        coupon = CouponService.create_coupon(db_session, self._coupon_create_data())
        assert coupon.code == "SAVE10"
        assert coupon.is_active is True

    def test_create_coupon_duplicate_code(self, db_session):
        CouponService.create_coupon(db_session, self._coupon_create_data())
        with pytest.raises(BusinessException, match="已存在"):
            CouponService.create_coupon(db_session, self._coupon_create_data())

    def test_receive_coupon_success(self, db_session, test_user):
        coupon = _make_coupon(db_session)
        user_coupon = CouponService.receive_coupon(db_session, coupon.id, test_user.id)
        assert user_coupon.status == CouponStatus.UNUSED
        assert user_coupon.coupon_id == coupon.id

    def test_receive_coupon_not_found(self, db_session, test_user):
        with pytest.raises(BusinessException, match="优惠券不存在"):
            CouponService.receive_coupon(db_session, 9999, test_user.id)

    def test_receive_coupon_inactive(self, db_session, test_user):
        coupon = _make_coupon(db_session, is_active=False)
        with pytest.raises(BusinessException, match="已失效"):
            CouponService.receive_coupon(db_session, coupon.id, test_user.id)

    def test_receive_coupon_out_of_window(self, db_session, test_user):
        coupon = _make_coupon(
            db_session,
            valid_from=datetime.now() - timedelta(days=10),
            valid_until=datetime.now() - timedelta(days=3),
        )
        with pytest.raises(BusinessException, match="不在领取有效期内"):
            CouponService.receive_coupon(db_session, coupon.id, test_user.id)

    def test_receive_coupon_duplicate(self, db_session, test_user):
        coupon = _make_coupon(db_session)
        CouponService.receive_coupon(db_session, coupon.id, test_user.id)
        with pytest.raises(BusinessException, match="已领取过"):
            CouponService.receive_coupon(db_session, coupon.id, test_user.id)

    def test_receive_coupon_quantity_limit(self, db_session, test_user):
        coupon = _make_coupon(db_session, total_quantity=1)
        other = _make_user(db_session, "otheruser", "other@example.com")
        CouponService.receive_coupon(db_session, coupon.id, other.id)
        with pytest.raises(BusinessException, match="已被领完"):
            CouponService.receive_coupon(db_session, coupon.id, test_user.id)

    def test_use_coupon_percent(self, db_session, test_user):
        coupon = _make_coupon(db_session, discount_type="percent", discount_value=Decimal("10"))
        user_coupon = _make_user_coupon(db_session, coupon, test_user)

        result = CouponService.use_coupon(db_session, user_coupon.id, Decimal("100"))

        assert result["discount_amount"] == 10.0
        assert result["final_amount"] == 90.0
        refreshed = db_session.query(UserCoupon).filter(UserCoupon.id == user_coupon.id).first()
        assert refreshed.status == CouponStatus.USED

    def test_use_coupon_percent_with_cap(self, db_session, test_user):
        coupon = _make_coupon(
            db_session,
            discount_type="percent",
            discount_value=Decimal("50"),
            max_discount=Decimal("20"),
        )
        user_coupon = _make_user_coupon(db_session, coupon, test_user)
        result = CouponService.use_coupon(db_session, user_coupon.id, Decimal("100"))
        assert result["discount_amount"] == 20.0

    def test_use_coupon_fixed(self, db_session, test_user):
        coupon = _make_coupon(db_session, discount_type="fixed", discount_value=Decimal("30"))
        user_coupon = _make_user_coupon(db_session, coupon, test_user)
        result = CouponService.use_coupon(db_session, user_coupon.id, Decimal("100"))
        assert result["discount_amount"] == 30.0
        assert result["final_amount"] == 70.0

    def test_use_coupon_fixed_not_exceed_order_amount(self, db_session, test_user):
        coupon = _make_coupon(db_session, discount_type="fixed", discount_value=Decimal("500"))
        user_coupon = _make_user_coupon(db_session, coupon, test_user)
        result = CouponService.use_coupon(db_session, user_coupon.id, Decimal("100"))
        assert result["discount_amount"] == 100.0
        assert result["final_amount"] == 0.0

    def test_use_coupon_min_amount(self, db_session, test_user):
        coupon = _make_coupon(db_session, min_amount=Decimal("50"))
        user_coupon = _make_user_coupon(db_session, coupon, test_user)
        with pytest.raises(BusinessException, match="订单金额需满"):
            CouponService.use_coupon(db_session, user_coupon.id, Decimal("30"))

    def test_use_coupon_expired(self, db_session, test_user):
        coupon = _make_coupon(db_session, valid_until=datetime.now() - timedelta(days=1))
        user_coupon = _make_user_coupon(db_session, coupon, test_user)
        with pytest.raises(BusinessException, match="已过期"):
            CouponService.use_coupon(db_session, user_coupon.id, Decimal("100"))
        refreshed = db_session.query(UserCoupon).filter(UserCoupon.id == user_coupon.id).first()
        assert refreshed.status == CouponStatus.EXPIRED

    def test_use_coupon_invalid_status(self, db_session, test_user):
        coupon = _make_coupon(db_session)
        user_coupon = _make_user_coupon(db_session, coupon, test_user, status=CouponStatus.USED)
        with pytest.raises(BusinessException, match="已使用或已过期"):
            CouponService.use_coupon(db_session, user_coupon.id, Decimal("100"))


class TestOperationServiceCoupon:
    """OperationService 优惠券相关方法测试"""

    async def test_calculate_coupon_discount_percent(self, db_session, test_user):
        _make_coupon(db_session, code="CALC10", discount_type="percent", discount_value=Decimal("20"))
        svc = OperationService(db_session)
        result = await svc.calculate_coupon_discount(test_user.id, "CALC10", Decimal("100"))
        assert result["discount_amount"] == 20.0
        assert result["final_amount"] == 80.0

    async def test_calculate_coupon_discount_not_found(self, db_session, test_user):
        svc = OperationService(db_session)
        with pytest.raises(BusinessException, match="不存在或未启用"):
            await svc.calculate_coupon_discount(test_user.id, "NOPE", Decimal("100"))

    async def test_use_coupon_by_code(self, db_session, test_user):
        _make_coupon(db_session, code="USE10", discount_type="percent", discount_value=Decimal("10"))
        svc = OperationService(db_session)
        result = await svc.use_coupon(test_user.id, {
            "coupon_code": "USE10",
            "order_type": "recharge",
            "amount": Decimal("100"),
        })
        assert result["discount_amount"] == 10.0
        assert result["final_amount"] == 90.0
        assert result["coupon_code"] == "USE10"


class TestReferralService:
    """推广返利服务测试"""

    def test_generate_referral_code(self, db_session, test_user):
        code = ReferralService.generate_referral_code(db_session, test_user.id)
        assert len(code) == 8
        again = ReferralService.generate_referral_code(db_session, test_user.id)
        assert again == code

    def test_generate_referral_code_user_not_found(self, db_session):
        with pytest.raises(BusinessException, match="用户不存在"):
            ReferralService.generate_referral_code(db_session, 9999)

    def test_process_referral_invalid_code(self, db_session, test_user):
        with pytest.raises(BusinessException, match="推荐码无效"):
            ReferralService.process_referral(db_session, test_user.id, "NOPE1234")

    def test_process_referral_self(self, db_session, test_user):
        user = db_session.query(User).filter(User.id == test_user.id).first()
        user.referral_code = "SELF1234"
        db_session.commit()
        with pytest.raises(BusinessException, match="不能使用自己的推荐码"):
            ReferralService.process_referral(db_session, test_user.id, "SELF1234")

    def test_process_referral_success_and_duplicate(self, db_session, test_user):
        referrer = _make_user(db_session, "referrer", "referrer@example.com", referral_code="ABC12345")
        record = ReferralService.process_referral(db_session, test_user.id, "ABC12345")

        assert record.referrer_id == referrer.id
        assert record.referee_id == test_user.id
        assert record.status == ReferralStatus.PENDING

        with pytest.raises(BusinessException, match="已使用过推荐码"):
            ReferralService.process_referral(db_session, test_user.id, "ABC12345")

    def test_complete_referral(self, db_session):
        referrer = _make_user(db_session, "referrer2", "referrer2@example.com", referral_code="DEF12345")
        referee = _make_user(db_session, "referee2", "referee2@example.com")
        record = ReferralService.process_referral(db_session, referee.id, "DEF12345")

        settled = ReferralService.complete_referral(db_session, record.id, Decimal("10"))

        assert settled.status == ReferralStatus.SETTLED
        assert settled.reward_amount == Decimal("10")
        updated = db_session.query(User).filter(User.id == referrer.id).first()
        assert updated.credits == 1000
        tx = db_session.query(CreditTransaction).filter(
            CreditTransaction.transaction_type == TransactionType.REWARD
        ).first()
        assert tx is not None
        assert tx.amount == 1000

    def test_complete_referral_not_found(self, db_session):
        with pytest.raises(BusinessException, match="推荐记录不存在"):
            ReferralService.complete_referral(db_session, 9999, Decimal("10"))

    def test_complete_referral_bad_status(self, db_session):
        referrer = _make_user(db_session, "referrer3", "referrer3@example.com", referral_code="GHI12345")
        referee = _make_user(db_session, "referee3", "referee3@example.com")
        record = ReferralService.process_referral(db_session, referee.id, "GHI12345")
        ReferralService.complete_referral(db_session, record.id, Decimal("10"))

        with pytest.raises(BusinessException, match="状态异常"):
            ReferralService.complete_referral(db_session, record.id, Decimal("10"))


class TestOperationServiceStatistics:
    """运营统计服务测试"""

    async def test_get_statistics_empty(self, db_session):
        svc = OperationService(db_session)
        result = await svc.get_statistics()
        for key in (
            "new_users", "active_users", "recharge_amount", "recharge_count",
            "membership_amount", "membership_count", "credit_consume",
            "generation_count", "activity_participants", "coupon_used",
            "referral_count", "referral_rewards",
        ):
            assert key in result
        assert result["new_users"] == 0
        assert result["recharge_amount"] == 0.0

    async def test_get_statistics_counts_new_users(self, db_session):
        _make_user(db_session, "newuser", "newuser@example.com")
        svc = OperationService(db_session)
        result = await svc.get_statistics(
            start_date=datetime.now() - timedelta(days=1),
            end_date=datetime.now() + timedelta(days=1),
        )
        assert result["new_users"] == 1

    async def test_get_dashboard_statistics_empty(self, db_session):
        svc = OperationService(db_session)
        result = await svc.get_dashboard_statistics()
        assert result["total_users"] == 0
        assert result["today_new_users"] == 0
        assert result["total_creations"] == 0
        assert result["total_revenue"] == 0.0

    async def test_get_user_statistics_empty(self, db_session, test_user):
        svc = OperationService(db_session)
        result = await svc.get_user_statistics(test_user.id)
        assert result["total_creations"] == 0
        assert result["activities_participated"] == 0
        assert result["coupons_received"] == 0
