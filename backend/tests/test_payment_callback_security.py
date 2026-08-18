# -*- coding: utf-8 -*-
"""支付回调安全测试：统一回调需登录且仅限订单本人；网关回调需 HMAC 签名"""
import hashlib
import hmac
import time

from app.core.config import settings


def _sign(order_no, amount, status, transaction_id, timestamp):
    secret = settings.PAYMENT_CALLBACK_SECRET or ""
    canonical = f"{order_no}:{amount}:{status}:{transaction_id}:{timestamp}"
    return hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()


def _create_recharge_order(client, auth_headers):
    r = client.post(
        "/api/v1/credit/recharge",
        json={"price_id": 1, "payment_method": "alipay"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    return r.json()["data"]["order_no"]


class TestUnifiedCallbackAuth:
    def test_callback_without_token_401(self, client, auth_headers):
        order_no = _create_recharge_order(client, auth_headers)
        r = client.post(
            "/api/v1/credit/payment/callback",
            json={"order_type": "recharge", "order_no": order_no},
        )
        assert r.status_code == 401

    def test_callback_other_users_order_403(self, client, auth_headers, second_user_headers):
        order_no = _create_recharge_order(client, auth_headers)
        r = client.post(
            "/api/v1/credit/payment/callback",
            json={"order_type": "recharge", "order_no": order_no},
            headers=second_user_headers,
        )
        assert r.status_code == 403

    def test_callback_owner_success(self, client, auth_headers):
        order_no = _create_recharge_order(client, auth_headers)
        r = client.post(
            "/api/v1/credit/payment/callback",
            json={"order_type": "recharge", "order_no": order_no},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["data"]["success"] is True


class TestGatewayCallbackSignature:
    def test_callback_without_signature_403(self, client, auth_headers):
        order_no = _create_recharge_order(client, auth_headers)
        r = client.post(
            "/api/v1/credit/recharge/callback",
            json={
                "order_no": order_no,
                "transaction_id": "TXN1",
                "payment_method": "alipay",
                "amount": "1.00",
                "status": "paid",
            },
        )
        assert r.status_code == 403

    def test_callback_wrong_signature_403(self, client, auth_headers):
        order_no = _create_recharge_order(client, auth_headers)
        ts = str(int(time.time()))
        good = _sign(order_no, "1.00", "paid", "TXN2", ts)
        r = client.post(
            "/api/v1/credit/recharge/callback",
            json={
                "order_no": order_no,
                "transaction_id": "TXN2",
                "payment_method": "alipay",
                "amount": "1.00",
                "status": "paid",
            },
            headers={"X-Callback-Timestamp": ts, "X-Callback-Sign": "0" * 64},
        )
        assert r.status_code == 403
        assert good != "0" * 64

    def test_callback_valid_signature_success(self, client, auth_headers):
        order_no = _create_recharge_order(client, auth_headers)
        ts = str(int(time.time()))
        sign = _sign(order_no, "1.00", "paid", "TXN3", ts)
        r = client.post(
            "/api/v1/credit/recharge/callback",
            json={
                "order_no": order_no,
                "transaction_id": "TXN3",
                "payment_method": "alipay",
                "amount": "1.00",
                "status": "paid",
            },
            headers={"X-Callback-Timestamp": ts, "X-Callback-Sign": sign},
        )
        assert r.status_code == 200
        assert r.json()["data"]["success"] is True

    def test_callback_stale_timestamp_403(self, client, auth_headers):
        order_no = _create_recharge_order(client, auth_headers)
        ts = str(int(time.time()) - 3600)
        sign = _sign(order_no, "1.00", "paid", "TXN4", ts)
        r = client.post(
            "/api/v1/credit/recharge/callback",
            json={
                "order_no": order_no,
                "transaction_id": "TXN4",
                "payment_method": "alipay",
                "amount": "1.00",
                "status": "paid",
            },
            headers={"X-Callback-Timestamp": ts, "X-Callback-Sign": sign},
        )
        assert r.status_code == 403
