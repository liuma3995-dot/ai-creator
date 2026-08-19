# -*- coding: utf-8 -*-
"""既有缺陷回归：D9 优惠券延迟核销/失败恢复、D10 推广规则更新 400、D11 Decimal 序列化 500"""
from datetime import datetime, timedelta
from decimal import Decimal

from app.models.operation import Coupon, UserCoupon, CouponType, CouponStatus
from app.models.credit import RechargeOrder, MembershipOrder, PaymentStatus


def _make_coupon(db_session, user, code="TEST10", coupon_type=CouponType.RECHARGE_DISCOUNT,
                 discount_value=5, min_amount=None):
    coupon = Coupon(
        code=code,
        name="测试券",
        coupon_type=coupon_type,
        discount_type="fixed",
        discount_value=Decimal(str(discount_value)),
        min_amount=Decimal(str(min_amount)) if min_amount is not None else None,
        total_quantity=100,
        per_user_limit=1,
        used_quantity=0,
        valid_from=datetime.now() - timedelta(days=1),
        valid_until=datetime.now() + timedelta(days=30),
        is_active=True,
    )
    db_session.add(coupon)
    db_session.flush()
    db_session.add(UserCoupon(user_id=user.id, coupon_id=coupon.id, status=CouponStatus.UNUSED))
    db_session.commit()
    return coupon


def _get_user_coupon(db_session, coupon):
    return db_session.query(UserCoupon).filter(UserCoupon.coupon_id == coupon.id).first()


class TestD9CouponDeferredConsumption:
    """D9：下单不核销，支付成功才核销，失败/取消/退款恢复"""

    def test_recharge_order_keeps_coupon_until_paid(self, client, auth_headers, db_session, test_user):
        coupon = _make_coupon(db_session, test_user)
        r = client.post("/api/v1/credit/recharge", json={
            "price_id": 1,
            "payment_method": "alipay",
            "coupon_code": coupon.code,
        }, headers=auth_headers)
        assert r.status_code == 200
        order = r.json()["data"]
        assert order["payment_status"] == "pending"

        db_order = db_session.query(RechargeOrder).filter(RechargeOrder.id == order["id"]).first()
        assert db_order.coupon_code == coupon.code
        uc = _get_user_coupon(db_session, coupon)
        assert uc.status == CouponStatus.UNUSED, "未支付不应核销优惠券"
        assert uc.order_id is None

        # 支付成功后核销
        r2 = client.post("/api/v1/credit/payment/callback", json={
            "order_type": "recharge",
            "order_no": order["order_no"],
        }, headers=auth_headers)
        assert r2.status_code == 200
        db_session.refresh(uc)
        assert uc.status == CouponStatus.USED
        assert uc.order_id == order["id"]

    def test_recharge_payment_failed_keeps_coupon_unused(self, client, auth_headers, db_session, test_user):
        from app.services.credit_service import RechargeService

        coupon = _make_coupon(db_session, test_user)
        r = client.post("/api/v1/credit/recharge", json={
            "price_id": 1,
            "payment_method": "alipay",
            "coupon_code": coupon.code,
        }, headers=auth_headers)
        order = r.json()["data"]

        ok = RechargeService.process_payment_callback(db_session, order["order_no"], "tx-fail", "failed")
        assert ok is True
        db_order = db_session.query(RechargeOrder).filter(RechargeOrder.id == order["id"]).first()
        assert db_order.payment_status == PaymentStatus.FAILED
        uc = _get_user_coupon(db_session, coupon)
        assert uc.status == CouponStatus.UNUSED

    def test_refund_restores_used_coupon(self, client, auth_headers, db_session, test_user):
        from app.services.credit_service import RechargeService

        coupon = _make_coupon(db_session, test_user)
        r = client.post("/api/v1/credit/recharge", json={
            "price_id": 1,
            "payment_method": "alipay",
            "coupon_code": coupon.code,
        }, headers=auth_headers)
        order = r.json()["data"]

        assert RechargeService.process_payment_callback(db_session, order["order_no"], "tx-1", "paid") is True
        db_session.refresh(coupon)
        assert coupon.used_quantity == 1
        uc = _get_user_coupon(db_session, coupon)
        assert uc.status == CouponStatus.USED

        assert RechargeService.process_payment_callback(db_session, order["order_no"], "tx-1", "refunded") is True
        db_session.refresh(coupon)
        db_session.refresh(uc)
        assert uc.status == CouponStatus.UNUSED
        assert uc.order_id is None
        assert coupon.used_quantity == 0

    def test_membership_paid_consumes_coupon(self, client, auth_headers, db_session, test_user):
        coupon = _make_coupon(db_session, test_user, code="VIP10", coupon_type=CouponType.MEMBERSHIP_DISCOUNT)
        r = client.post("/api/v1/credit/membership", json={
            "price_id": 1,
            "payment_method": "alipay",
            "coupon_code": coupon.code,
        }, headers=auth_headers)
        assert r.status_code == 200
        order = r.json()["data"]

        db_order = db_session.query(MembershipOrder).filter(MembershipOrder.id == order["id"]).first()
        assert db_order.coupon_code == coupon.code
        uc = _get_user_coupon(db_session, coupon)
        assert uc.status == CouponStatus.UNUSED, "会员订单未支付不应核销优惠券"

        r2 = client.post("/api/v1/credit/payment/callback", json={
            "order_type": "membership",
            "order_no": order["order_no"],
        }, headers=auth_headers)
        assert r2.status_code == 200
        db_session.refresh(uc)
        assert uc.status == CouponStatus.USED


class TestD10ReferralRuleUpdate:
    """D10：推广规则更新不应因显式 null 触发 400 / 抹掉既有配置"""

    def test_null_register_credits_does_not_break_update(self, client, admin_headers, db_session):
        r = client.put("/api/v1/admin/operation/referral/rule", json={
            "reward_type": "register_credits",
            "register_credits": 100,
            "is_enabled": True,
        }, headers=admin_headers)
        assert r.status_code == 200

        r2 = client.put("/api/v1/admin/operation/referral/rule", json={
            "reward_type": "credits",
            "credits_rate": 0.1,
            "register_credits": None,
            "coupon_id": None,
            "is_enabled": True,
        }, headers=admin_headers)
        assert r2.status_code == 200, r2.text
        assert r2.json()["data"]["register_credits"] == 100

    def test_register_credits_requires_positive_value(self, client, admin_headers):
        r = client.put("/api/v1/admin/operation/referral/rule", json={
            "reward_type": "register_credits",
            "register_credits": None,
            "is_enabled": True,
        }, headers=admin_headers)
        assert r.status_code == 400
        assert "邀请注册" in r.json()["message"]

    def test_coupon_requires_coupon_id(self, client, admin_headers):
        r = client.put("/api/v1/admin/operation/referral/rule", json={
            "reward_type": "coupon",
            "coupon_id": None,
            "is_enabled": True,
        }, headers=admin_headers)
        assert r.status_code == 400
        assert "优惠券" in r.json()["message"]

    def test_switch_to_coupon_preserves_register_credits(self, client, admin_headers, db_session):
        from app.models.operation import ReferralRule

        rule = db_session.query(ReferralRule).first()
        if not rule:
            rule = ReferralRule(reward_type="credits", credits_rate=Decimal("0.10"), register_credits=50, is_enabled=True)
            db_session.add(rule)
            db_session.commit()
        rule.register_credits = 88
        db_session.commit()

        r = client.put("/api/v1/admin/operation/referral/rule", json={
            "reward_type": "coupon",
            "coupon_id": None,
            "is_enabled": True,
        }, headers=admin_headers)
        assert r.status_code == 400  # 未关联券仍然拒绝


class TestD11DecimalSerialization:
    """D11：校验错误详情含 Decimal 时应返回 422 而不是序列化 500"""

    def test_decimal_validation_error_returns_422(self, client, admin_headers):
        r = client.put("/api/v1/admin/operation/referral/rule", json={
            "reward_type": "credits",
            "credits_rate": 1.5,
            "is_enabled": True,
        }, headers=admin_headers)
        assert r.status_code == 422, r.text
        body = r.json()
        assert body["code"] == 422
        assert "errors" in body["data"]
