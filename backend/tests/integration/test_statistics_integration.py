# -*- coding: utf-8 -*-
"""
集成测试 4.2：数据统计跨模块聚合口径

造数：用户/创作/充值/会员/活动参与/优惠券/推荐结算，
验证 /statistics 与 /dashboard 各指标与造数一致。
"""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.models.creation import Creation, CreationType
from app.models.credit import (
    CreditTransaction,
    MembershipOrder,
    MembershipType,
    PaymentStatus,
    RechargeOrder,
    TransactionType,
)
from app.models.operation import (
    Activity,
    ActivityStatus,
    ActivityType,
    ActivityParticipation,
    Coupon,
    CouponStatus,
    CouponType,
    ReferralRecord,
    ReferralStatus,
    UserCoupon,
)
from app.models.user import User


@pytest.mark.integration
class TestStatisticsAggregation:
    """统计口径与多模块数据一致性"""

    def _seed_data(self, mysql_session):
        now = datetime.now()
        old = now - timedelta(days=40)

        u1 = User(username="stat_u1", email="stat_u1@example.com", password_hash="x", is_member=1)
        u2 = User(username="stat_u2", email="stat_u2@example.com", password_hash="x")
        u3 = User(
            username="stat_u3",
            email="stat_u3@example.com",
            password_hash="x",
            created_at=old,
        )
        mysql_session.add_all([u1, u2, u3])
        mysql_session.commit()
        for u in (u1, u2, u3):
            mysql_session.refresh(u)

        c1 = Creation(
            user_id=u1.id, creation_type=CreationType.WECHAT_ARTICLE, title="文章一"
        )
        c2 = Creation(
            user_id=u1.id, creation_type=CreationType.MARKETING_COPY, title="文案二"
        )
        mysql_session.add_all([c1, c2])

        r1 = RechargeOrder(
            order_no="RC1001",
            user_id=u1.id,
            amount=Decimal("100"),
            credits=1000,
            payment_status=PaymentStatus.PAID,
        )
        m1 = MembershipOrder(
            order_no="MB1001",
            user_id=u1.id,
            membership_type=MembershipType.MONTHLY,
            amount=Decimal("29"),
            payment_status=PaymentStatus.PAID,
        )
        mysql_session.add_all([r1, m1])

        consume = CreditTransaction(
            user_id=u1.id,
            transaction_type=TransactionType.CONSUME,
            amount=-50,
            balance_before=100,
            balance_after=50,
            description="测试消耗",
        )
        mysql_session.add(consume)

        activity = Activity(
            title="统计活动",
            activity_type=ActivityType.CREDIT_GIFT,
            status=ActivityStatus.ACTIVE,
            rules={},
            start_time=now - timedelta(days=1),
            end_time=now + timedelta(days=7),
        )
        mysql_session.add(activity)
        mysql_session.commit()
        mysql_session.refresh(activity)
        participation = ActivityParticipation(
            activity_id=activity.id, user_id=u1.id, reward_amount=10
        )
        mysql_session.add(participation)

        coupon = Coupon(
            code="STAT10",
            name="统计券",
            coupon_type=CouponType.RECHARGE_DISCOUNT,
            discount_type="percent",
            discount_value=10,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=7),
        )
        mysql_session.add(coupon)
        mysql_session.commit()
        mysql_session.refresh(coupon)
        user_coupon = UserCoupon(
            user_id=u1.id,
            coupon_id=coupon.id,
            status=CouponStatus.USED,
            # 固定偏移，避免系统时钟回拨导致 used_at 超过 end_date 的边界抖动
            used_at=now - timedelta(minutes=5),
        )
        mysql_session.add(user_coupon)

        referral = ReferralRecord(
            referrer_id=u1.id,
            referee_id=u2.id,
            status=ReferralStatus.SETTLED,
            reward_amount=Decimal("10"),
        )
        mysql_session.add(referral)
        mysql_session.commit()
        return u1, u2, u3

    def test_statistics_matches_seeded_data(
        self, client, mysql_session, admin_headers
    ):
        self._seed_data(mysql_session)

        r = client.get("/api/v1/admin/operation/statistics", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()["data"]

        # 新增用户：窗口内（含启动种子管理员，不含 40 天前的 u3）
        window_start = datetime.now() - timedelta(days=30)
        expected_new = mysql_session.query(User).filter(User.created_at >= window_start).count()
        assert data["new_users"] == expected_new

        # 创作与活跃用户
        assert data["generation_count"] == 2
        assert data["active_users"] == 1

        # 订单收入
        assert data["recharge_count"] == 1
        assert data["recharge_amount"] == 100.0
        assert data["membership_count"] == 1
        assert data["membership_amount"] == 29.0

        # 积分消耗、活动、优惠券、推荐
        assert data["credit_consume"] == 50
        assert data["activity_participants"] == 1
        assert data["coupon_used"] == 1
        assert data["referral_count"] == 1
        assert data["referral_rewards"] == 10.0

        # 新增指标：收入/会员/创作汇总
        assert data["total_revenue"] == 129.0
        assert data["total_members"] == 1
        assert data["total_creations"] == 2

        # 趋势与分布
        assert len(data["user_trend"]["dates"]) == 31
        assert round(sum(data["revenue_trend"]["amounts"]), 2) == 129.0
        assert len(data["creation_distribution"]) == 2
        assert sum(item["value"] for item in data["creation_distribution"]) == 2
        assert sum(item["value"] for item in data["payment_distribution"]) == 1

    def test_dashboard_totals_match_seeded_data(
        self, client, mysql_session, admin_headers
    ):
        self._seed_data(mysql_session)

        r = client.get("/api/v1/admin/operation/dashboard", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()["data"]

        assert data["total_users"] == mysql_session.query(User).count()
        assert data["total_creations"] == 2
        assert data["total_members"] == 1
        assert data["total_revenue"] == 129.0

    def test_out_of_window_user_not_counted(
        self, client, mysql_session, admin_headers
    ):
        self._seed_data(mysql_session)

        r = client.get("/api/v1/admin/operation/statistics", headers=admin_headers)
        data = r.json()["data"]

        # u3（40 天前注册）不计入 30 天窗口
        u3 = mysql_session.query(User).filter(User.username == "stat_u3").first()
        assert u3.created_at < datetime.now() - timedelta(days=35)
        window_start = datetime.now() - timedelta(days=30)
        in_window = mysql_session.query(User).filter(User.created_at >= window_start).count()
        assert data["new_users"] == in_window
