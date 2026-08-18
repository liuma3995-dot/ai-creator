# -*- coding: utf-8 -*-
"""会员模块缺陷回归测试：D1 订单绑定套餐、D2 会员统计 500"""
from datetime import datetime


def _buy_membership(client, headers, price_id):
    r = client.post(
        "/api/v1/credit/membership",
        json={"price_id": price_id, "payment_method": "alipay"},
        headers=headers,
    )
    assert r.status_code == 200
    order = r.json()["data"]
    r2 = client.post(
        "/api/v1/credit/payment/callback",
        json={"order_type": "membership", "order_no": order["order_no"]},
        headers=headers,
    )
    assert r2.status_code == 200
    return order


class TestMembershipPriceBinding:
    def test_order_binds_price_id_and_grants_its_duration(self, client, auth_headers, db_session, test_user):
        from app.models.user import User

        order = _buy_membership(client, auth_headers, 2)  # 季度会员 90 天
        assert order["price_id"] == 2

        user = db_session.query(User).filter(User.id == test_user.id).first()
        assert user.is_member == 1
        days = (user.member_expired_at - datetime.now()).total_seconds() / 86400
        assert 89 < days < 91, f"到期天数={days}（应约90天，而不是30天）"

    def test_renew_extends_from_current_expiry(self, client, auth_headers, db_session, test_user):
        from app.models.user import User

        order1 = _buy_membership(client, auth_headers, 2)
        user = db_session.query(User).filter(User.id == test_user.id).first()
        first_expiry = user.member_expired_at

        order2 = _buy_membership(client, auth_headers, 2)
        user = db_session.query(User).filter(User.id == test_user.id).first()
        days = (user.member_expired_at - first_expiry).total_seconds() / 86400
        assert 89 < days < 91, f"续费顺延天数={days}"

    def test_membership_statistics_ok(self, client, auth_headers):
        _buy_membership(client, auth_headers, 2)
        r = client.get("/api/v1/credit/membership/statistics", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total_orders"] >= 1
        assert data["active_membership"] is True
        assert data["is_member"] is True
        assert data["days_remaining"] >= 89
        assert data["expired_at"] is not None
