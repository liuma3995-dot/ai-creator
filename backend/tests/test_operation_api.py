# -*- coding: utf-8 -*-
"""
运营管理模块 API 层单元测试
覆盖：活动、优惠券、推广、统计接口的权限校验与响应契约
"""
from datetime import datetime, timedelta

from app.models.operation import (
    Activity,
    ActivityStatus,
    ActivityType,
    Coupon,
    CouponStatus,
    CouponType,
)
from app.models.user import User, UserRole


def _activity_payload(**kwargs):
    data = dict(
        title="API测试活动",
        activity_type="credit_gift",
        start_time=(datetime.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S"),
        end_time=(datetime.now() + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S"),
        reward_type="credits",
        reward_amount=20,
    )
    data.update(kwargs)
    return data


def _coupon_payload(code="API100", **kwargs):
    data = dict(
        code=code,
        name="API优惠券",
        coupon_type="recharge_discount",
        discount_type="percent",
        discount_value=10,
        valid_from=(datetime.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S"),
        valid_until=(datetime.now() + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S"),
    )
    data.update(kwargs)
    return data


def _make_activity(db, **kwargs):
    defaults = dict(
        title="库内活动",
        activity_type=ActivityType.CREDIT_GIFT,
        status=ActivityStatus.ACTIVE,
        rules={"credits": 10},
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
    defaults = dict(
        code="API500",
        name="库内优惠券",
        coupon_type=CouponType.RECHARGE_DISCOUNT,
        discount_type="percent",
        discount_value=10,
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


class TestActivityAPI:
    """活动接口测试"""

    def test_create_activity_requires_admin(self, client, auth_headers):
        r = client.post("/api/v1/admin/operation/activities", json=_activity_payload(), headers=auth_headers)
        assert r.status_code == 403

    def test_create_activity_as_admin(self, client, admin_headers):
        r = client.post("/api/v1/admin/operation/activities", json=_activity_payload(), headers=admin_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 200
        assert body["data"]["reward_type"] == "credits"
        assert body["data"]["reward_amount"] == 20

    def test_create_activity_anonymous(self, client):
        r = client.post("/api/v1/admin/operation/activities", json=_activity_payload())
        assert r.status_code in (401, 403)

    def test_get_activities_list(self, client, auth_headers):
        r = client.get("/api/v1/operation/activities", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["data"]["items"] == []

    def test_get_activity_not_found(self, client, admin_headers):
        r = client.get("/api/v1/operation/activities/99999", headers=admin_headers)
        assert r.status_code == 404

    def test_get_activity_detail(self, client, db_session, auth_headers):
        activity = _make_activity(db_session)
        r = client.get(f"/api/v1/operation/activities/{activity.id}", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["data"]["id"] == activity.id
        assert r.json()["data"]["reward_amount"] == 10

    def test_update_activity_requires_admin(self, client, db_session, auth_headers):
        activity = _make_activity(db_session)
        r = client.put(
            f"/api/v1/admin/operation/activities/{activity.id}",
            json={"title": "普通用户改"},
            headers=auth_headers,
        )
        assert r.status_code == 403

    def test_update_activity_as_admin(self, client, db_session, admin_headers):
        activity = _make_activity(db_session)
        r = client.put(
            f"/api/v1/admin/operation/activities/{activity.id}",
            json={"title": "管理员改", "reward_amount": 66},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["data"]["title"] == "管理员改"
        assert r.json()["data"]["reward_amount"] == 66

    def test_update_activity_not_found(self, client, admin_headers):
        r = client.put(
            "/api/v1/admin/operation/activities/99999",
            json={"title": "不存在"},
            headers=admin_headers,
        )
        assert r.status_code == 404

    def test_delete_activity_as_admin(self, client, db_session, admin_headers):
        activity = _make_activity(db_session)
        r = client.delete(f"/api/v1/admin/operation/activities/{activity.id}", headers=admin_headers)
        assert r.status_code == 200
        assert db_session.query(Activity).filter(Activity.id == activity.id).first() is None

    def test_delete_activity_not_found(self, client, admin_headers):
        r = client.delete("/api/v1/admin/operation/activities/99999", headers=admin_headers)
        assert r.status_code == 404

    def test_participate_activity_twice(self, client, db_session, auth_headers):
        activity = _make_activity(db_session, rules={"credits": 10})
        payload = {"activity_id": activity.id}

        first = client.post(
            f"/api/v1/operation/activities/{activity.id}/participate",
            json=payload,
            headers=auth_headers,
        )
        assert first.status_code == 200
        assert first.json()["data"]["reward_amount"] == 10

        second = client.post(
            f"/api/v1/operation/activities/{activity.id}/participate",
            json=payload,
            headers=auth_headers,
        )
        assert second.status_code == 400

    def test_participate_activity_not_found(self, client, auth_headers):
        r = client.post(
            "/api/v1/operation/activities/99999/participate",
            json={"activity_id": 99999},
            headers=auth_headers,
        )
        assert r.status_code == 400


class TestCouponAPI:
    """优惠券接口测试"""

    def test_create_coupon_requires_admin(self, client, auth_headers):
        r = client.post("/api/v1/admin/operation/coupons", json=_coupon_payload(), headers=auth_headers)
        assert r.status_code == 403

    def test_create_coupon_as_admin(self, client, admin_headers):
        r = client.post("/api/v1/admin/operation/coupons", json=_coupon_payload(), headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["data"]["code"] == "API100"

    def test_create_coupon_duplicate_code(self, client, admin_headers):
        payload = _coupon_payload()
        assert client.post("/api/v1/admin/operation/coupons", json=payload, headers=admin_headers).status_code == 200
        duplicate = client.post("/api/v1/admin/operation/coupons", json=payload, headers=admin_headers)
        assert duplicate.status_code == 400

    def test_get_coupons_list(self, client, auth_headers):
        r = client.get("/api/v1/operation/coupons", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["data"]["items"] == []

    def test_get_coupon_not_found(self, client, admin_headers):
        r = client.get("/api/v1/operation/coupons/99999", headers=admin_headers)
        assert r.status_code == 404

    def test_receive_coupon_and_duplicate(self, client, db_session, auth_headers):
        coupon = _make_coupon(db_session)
        first = client.post(f"/api/v1/operation/coupons/{coupon.id}/receive", headers=auth_headers)
        assert first.status_code == 200
        second = client.post(f"/api/v1/operation/coupons/{coupon.id}/receive", headers=auth_headers)
        assert second.status_code == 400

    def test_use_coupon(self, client, db_session, auth_headers):
        coupon = _make_coupon(db_session, code="USEAPI10", discount_type="percent", discount_value=10)
        recv = client.post(
            f"/api/v1/operation/coupons/{coupon.id}/receive",
            headers=auth_headers,
        )
        assert recv.status_code == 200
        r = client.post(
            "/api/v1/operation/coupons/use",
            json={"coupon_code": "USEAPI10", "order_type": "recharge", "amount": 100},
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["discount_amount"] == 10.0
        assert data["final_amount"] == 90.0

    def test_use_coupon_updates_usage_status(self, client, db_session, auth_headers):
        coupon = _make_coupon(db_session, code="USEAPI12", discount_type="percent", discount_value=10)
        client.post(f"/api/v1/operation/coupons/{coupon.id}/receive", headers=auth_headers)
        r = client.post(
            "/api/v1/operation/coupons/use",
            json={"coupon_code": "USEAPI12", "order_type": "recharge", "amount": 100},
            headers=auth_headers,
        )
        assert r.status_code == 200

        listed = client.get("/api/v1/operation/coupons", headers=auth_headers)
        assert listed.status_code == 200
        items = listed.json()["data"]["items"]
        target = next(item for item in items if item["code"] == "USEAPI12")
        assert target["used_quantity"] == 1
        assert target["total_quantity"] == coupon.total_quantity

    def test_use_coupon_not_owned(self, client, db_session, auth_headers):
        _make_coupon(db_session, code="USEAPI11", discount_type="percent", discount_value=10)
        r = client.post(
            "/api/v1/operation/coupons/use",
            json={"coupon_code": "USEAPI11", "order_type": "recharge", "amount": 100},
            headers=auth_headers,
        )
        assert r.status_code == 400

    def test_use_coupon_not_found(self, client, auth_headers):
        r = client.post(
            "/api/v1/operation/coupons/use",
            json={"coupon_code": "NOCODE1", "order_type": "recharge", "amount": 100},
            headers=auth_headers,
        )
        assert r.status_code == 400

    def test_calculate_coupon_discount(self, client, db_session, auth_headers):
        coupon = _make_coupon(db_session, code="CALCAPI20", discount_type="percent", discount_value=20)
        recv = client.post(
            f"/api/v1/operation/coupons/{coupon.id}/receive",
            headers=auth_headers,
        )
        assert recv.status_code == 200
        r = client.post(
            "/api/v1/operation/coupons/calculate",
            json={"coupon_code": "CALCAPI20", "original_amount": 100},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["data"]["discount_amount"] == 20.0

    def test_get_user_coupons(self, client, auth_headers):
        r = client.get("/api/v1/operation/user/coupons", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["data"]["items"] == []

    def test_recharge_order_with_coupon_discount(self, client, db_session, auth_headers):
        from app.models.operation import CouponStatus, UserCoupon

        coupon = _make_coupon(db_session, code="ORDER10", discount_type="percent", discount_value=10)
        recv = client.post(
            f"/api/v1/operation/coupons/{coupon.id}/receive",
            headers=auth_headers,
        )
        assert recv.status_code == 200
        r = client.post(
            "/api/v1/credit/recharge",
            json={"price_id": 1, "payment_method": "alipay", "coupon_code": "ORDER10"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        order = r.json()["data"]
        # 10 元套餐 9 折 = 9.00
        assert float(order["amount"]) == 9.0
        uc = db_session.query(UserCoupon).filter(
            UserCoupon.order_id == order["id"]
        ).first()
        assert uc is not None
        assert uc.status == CouponStatus.USED

    def test_membership_order_with_coupon_discount(self, client, db_session, auth_headers):
        coupon = _make_coupon(
            db_session,
            code="MEMBER10",
            coupon_type=CouponType.MEMBERSHIP_DISCOUNT,
            discount_type="percent",
            discount_value=10,
        )
        recv = client.post(
            f"/api/v1/operation/coupons/{coupon.id}/receive",
            headers=auth_headers,
        )
        assert recv.status_code == 200
        r = client.post(
            "/api/v1/credit/membership",
            json={"price_id": 1, "payment_method": "alipay", "coupon_code": "MEMBER10"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        order = r.json()["data"]
        # 29 元月度会员 9 折 = 26.10
        assert float(order["amount"]) == 26.1

    def test_recharge_order_wrong_coupon_type(self, client, db_session, auth_headers):
        _make_coupon(
            db_session,
            code="MEMBERSONLY",
            coupon_type=CouponType.MEMBERSHIP_DISCOUNT,
            discount_type="percent",
            discount_value=10,
        )
        r = client.post(
            "/api/v1/credit/recharge",
            json={"price_id": 1, "payment_method": "alipay", "coupon_code": "MEMBERSONLY"},
            headers=auth_headers,
        )
        assert r.status_code == 400

    def test_recharge_order_invalid_coupon(self, client, auth_headers):
        r = client.post(
            "/api/v1/credit/recharge",
            json={"price_id": 1, "payment_method": "alipay", "coupon_code": "NOCODE9"},
            headers=auth_headers,
        )
        assert r.status_code == 400

    def test_issue_coupon_as_admin(self, client, db_session, admin_headers, test_user):
        from app.models.operation import UserCoupon

        coupon = _make_coupon(db_session, code="ISSUE10")
        r = client.post(
            f"/api/v1/admin/operation/coupons/{coupon.id}/issue",
            json={"user_ids": [test_user.id]},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["data"]["issued"] == 1

        # 重复发放跳过
        r2 = client.post(
            f"/api/v1/admin/operation/coupons/{coupon.id}/issue",
            json={"user_ids": [test_user.id]},
            headers=admin_headers,
        )
        assert r2.json()["data"]["issued"] == 0
        assert db_session.query(UserCoupon).filter(
            UserCoupon.coupon_id == coupon.id,
            UserCoupon.user_id == test_user.id,
        ).count() == 1

    def test_issue_coupon_requires_admin(self, client, db_session, auth_headers, test_user):
        coupon = _make_coupon(db_session, code="ISSUE11")
        r = client.post(
            f"/api/v1/admin/operation/coupons/{coupon.id}/issue",
            json={"user_ids": [test_user.id]},
            headers=auth_headers,
        )
        assert r.status_code == 403

    def test_issue_coupon_not_found(self, client, admin_headers):
        r = client.post(
            "/api/v1/admin/operation/coupons/99999/issue",
            json={"user_ids": [1]},
            headers=admin_headers,
        )
        assert r.status_code == 404

    def test_create_general_coupon_applies_to_both_orders(
        self, client, db_session, admin_headers, auth_headers
    ):
        coupon = _make_coupon(
            db_session,
            code="GENERAL10",
            coupon_type=CouponType.GENERAL,
            discount_type="percent",
            discount_value=10,
            per_user_limit=2,
        )
        recv1 = client.post(f"/api/v1/operation/coupons/{coupon.id}/receive", headers=auth_headers)
        assert recv1.status_code == 200
        recharge = client.post(
            "/api/v1/credit/recharge",
            json={"price_id": 1, "payment_method": "alipay", "coupon_code": "GENERAL10"},
            headers=auth_headers,
        )
        assert recharge.status_code == 200
        assert float(recharge.json()["data"]["amount"]) == 9.0

        recv2 = client.post(f"/api/v1/operation/coupons/{coupon.id}/receive", headers=auth_headers)
        assert recv2.status_code == 200

        membership = client.post(
            "/api/v1/credit/membership",
            json={"price_id": 1, "payment_method": "alipay", "coupon_code": "GENERAL10"},
            headers=auth_headers,
        )
        assert membership.status_code == 200
        assert float(membership.json()["data"]["amount"]) == 26.1

    def test_receive_coupon_per_user_limit(self, client, db_session, auth_headers):
        coupon = _make_coupon(db_session, code="LIMIT3", per_user_limit=2)
        first = client.post(f"/api/v1/operation/coupons/{coupon.id}/receive", headers=auth_headers)
        second = client.post(f"/api/v1/operation/coupons/{coupon.id}/receive", headers=auth_headers)
        third = client.post(f"/api/v1/operation/coupons/{coupon.id}/receive", headers=auth_headers)
        assert first.status_code == 200
        assert second.status_code == 200
        assert third.status_code == 400

    def test_void_coupon_marks_unused_as_voided(
        self, client, db_session, admin_headers, auth_headers
    ):
        from app.models.operation import CouponStatus, UserCoupon

        coupon = _make_coupon(db_session, code="VOID10")
        assert client.post(
            f"/api/v1/operation/coupons/{coupon.id}/receive", headers=auth_headers
        ).status_code == 200

        r = client.post(f"/api/v1/admin/operation/coupons/{coupon.id}/void", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["data"]["is_active"] is False

        refreshed = db_session.query(UserCoupon).filter(
            UserCoupon.coupon_id == coupon.id,
        ).first()
        assert refreshed.status == CouponStatus.VOIDED

    def test_void_coupon_requires_admin(self, client, db_session, auth_headers):
        coupon = _make_coupon(db_session, code="VOID11")
        r = client.post(f"/api/v1/admin/operation/coupons/{coupon.id}/void", headers=auth_headers)
        assert r.status_code == 403

    def test_void_coupon_not_found(self, client, admin_headers):
        r = client.post("/api/v1/admin/operation/coupons/99999/void", headers=admin_headers)
        assert r.status_code == 404


class TestReferralAPI:
    """推广返利接口测试"""

    def test_generate_referral_code(self, client, auth_headers):
        r = client.post("/api/v1/operation/referral/generate", json={}, headers=auth_headers)
        assert r.status_code == 200
        code = r.json()["data"]["referral_code"]
        assert len(code) == 8

    def test_get_referral_code_auto_generate(self, client, auth_headers):
        r = client.get("/api/v1/operation/referral/code", headers=auth_headers)
        assert r.status_code == 200
        assert len(r.json()["data"]["referral_code"]) == 8

    def test_get_referral_records(self, client, auth_headers):
        r = client.get("/api/v1/operation/referral/records", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["data"]["items"] == []

    def test_get_referral_statistics(self, client, auth_headers):
        r = client.get("/api/v1/operation/referral/statistics", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total_referrals"] == 0
        assert data["completed_referrals"] == 0

    def test_register_with_referral_code_binds_relationship(
        self, client, db_session, auth_headers
    ):
        from app.models.operation import ReferralRecord, ReferralStatus
        from app.models.user import User

        code = client.post(
            "/api/v1/operation/referral/generate", json={}, headers=auth_headers
        ).json()["data"]["referral_code"]

        r = client.post(
            "/api/v1/auth/register",
            json={
                "username": "referee_ok",
                "email": "referee_ok@example.com",
                "password": "pass123456",
                "referral_code": code,
            },
        )
        assert r.status_code == 200
        new_user = db_session.query(User).filter(User.username == "referee_ok").first()
        assert new_user is not None

        record = db_session.query(ReferralRecord).filter(
            ReferralRecord.referee_id == new_user.id
        ).first()
        assert record is not None
        assert record.referrer_id == db_session.query(User).filter(
            User.username == "testuser"
        ).first().id
        assert record.status == ReferralStatus.PENDING

    def test_register_with_invalid_referral_code_rejected(self, client, db_session):
        from app.models.user import User

        r = client.post(
            "/api/v1/auth/register",
            json={
                "username": "referee_bad",
                "email": "referee_bad@example.com",
                "password": "pass123456",
                "referral_code": "NOPE1234",
            },
        )
        assert r.status_code == 400
        assert db_session.query(User).filter(User.username == "referee_bad").first() is None

    def test_approve_referral_as_admin(self, client, db_session, admin_headers, test_user):
        from app.models.operation import ReferralRecord, ReferralStatus
        from app.models.user import User
        from app.services.operation_service import ReferralService

        code = ReferralService.generate_referral_code(db_session, test_user.id)
        referee = User(
            username="referee_appr", email="referee_appr@example.com", password_hash="x"
        )
        db_session.add(referee)
        db_session.commit()
        db_session.refresh(referee)
        record = ReferralService.process_referral(db_session, referee.id, code)
        before = db_session.query(User).filter(User.id == test_user.id).first().credits

        r = client.post(
            f"/api/v1/admin/operation/referral/{record.id}/approve",
            json={},
            headers=admin_headers,
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["status"] == "settled"
        assert data["reward_amount"] == 10.0

        after = db_session.query(User).filter(User.id == test_user.id).first().credits
        assert after == before + 1000
        refreshed = db_session.query(ReferralRecord).filter(
            ReferralRecord.id == record.id
        ).first()
        assert refreshed.status == ReferralStatus.SETTLED

    def test_approve_referral_requires_admin(
        self, client, db_session, auth_headers, test_user
    ):
        from app.models.user import User
        from app.services.operation_service import ReferralService

        code = ReferralService.generate_referral_code(db_session, test_user.id)
        referee = User(
            username="referee_appr2", email="referee_appr2@example.com", password_hash="x"
        )
        db_session.add(referee)
        db_session.commit()
        db_session.refresh(referee)
        record = ReferralService.process_referral(db_session, referee.id, code)

        r = client.post(
            f"/api/v1/admin/operation/referral/{record.id}/approve",
            json={},
            headers=auth_headers,
        )
        assert r.status_code == 403

    def test_approve_referrals_batch(
        self, client, db_session, admin_headers, test_user
    ):
        from app.models.operation import ReferralRecord
        from app.models.user import User
        from app.services.operation_service import ReferralService

        code = ReferralService.generate_referral_code(db_session, test_user.id)
        ids = []
        for i in range(2):
            referee = User(
                username=f"referee_batch{i}",
                email=f"referee_batch{i}@example.com",
                password_hash="x",
            )
            db_session.add(referee)
            db_session.commit()
            db_session.refresh(referee)
            record = ReferralService.process_referral(db_session, referee.id, code)
            ids.append(record.id)

        r = client.post(
            "/api/v1/admin/operation/referral/approve-batch",
            json={"record_ids": ids},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["data"]["settled"] == 2

        # 再次批量结算，全部跳过
        r2 = client.post(
            "/api/v1/admin/operation/referral/approve-batch",
            json={"record_ids": ids},
            headers=admin_headers,
        )
        assert r2.json()["data"]["settled"] == 0

    def test_approve_referral_not_found(self, client, admin_headers):
        r = client.post(
            "/api/v1/admin/operation/referral/99999/approve",
            json={},
            headers=admin_headers,
        )
        assert r.status_code == 400


class TestStatisticsAPI:
    """运营统计接口测试"""

    def test_statistics_requires_admin(self, client, auth_headers):
        r = client.get("/api/v1/admin/operation/statistics", headers=auth_headers)
        assert r.status_code == 403

    def test_statistics_as_admin(self, client, admin_headers, db_session):
        from app.models.user import User
        r = client.get("/api/v1/admin/operation/statistics", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()["data"]
        # 启动时会初始化种子管理员，按库内实际用户数断言
        assert data["new_users"] == db_session.query(User).count()
        assert data["recharge_amount"] == 0.0

    def test_dashboard_requires_admin(self, client, auth_headers):
        r = client.get("/api/v1/admin/operation/dashboard", headers=auth_headers)
        assert r.status_code == 403

    def test_dashboard_as_admin(self, client, admin_headers, db_session):
        from app.models.user import User
        r = client.get("/api/v1/admin/operation/dashboard", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total_users"] == db_session.query(User).count()
        assert "today_new_users" in data
        assert "total_revenue" in data
