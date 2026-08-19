# -*- coding: utf-8 -*-
"""管理员操作审计日志测试（S7）"""
from app.models.audit_log import AdminAuditLog


def test_admin_operation_written_to_audit(client, db_session, admin_headers):
    r = client.post(
        "/api/v1/admin/operation/coupons",
        json={
            "code": "AUDIT01",
            "name": "审计测试券",
            "coupon_type": "general",
            "discount_type": "fixed",
            "discount_value": "1.00",
            "min_amount": None,
            "valid_from": "2026-01-01T00:00:00",
            "valid_until": "2026-12-31T00:00:00",
        },
        headers=admin_headers,
    )
    assert r.status_code == 200

    log = db_session.query(AdminAuditLog).filter(
        AdminAuditLog.path == "/api/v1/admin/operation/coupons",
        AdminAuditLog.method == "POST",
    ).order_by(AdminAuditLog.id.desc()).first()
    assert log is not None
    assert log.username == "adminuser"
    assert log.status_code == 200


def test_forbidden_admin_call_still_logged(client, db_session, auth_headers):
    r = client.post(
        "/api/v1/admin/operation/coupons",
        json={
            "code": "AUDIT02",
            "name": "越权券",
            "coupon_type": "general",
            "discount_type": "fixed",
            "discount_value": "1.00",
            "valid_from": "2026-01-01T00:00:00",
            "valid_until": "2026-12-31T00:00:00",
        },
        headers=auth_headers,
    )
    assert r.status_code in (401, 403)

    log = db_session.query(AdminAuditLog).filter(
        AdminAuditLog.path == "/api/v1/admin/operation/coupons",
        AdminAuditLog.username == "testuser",
    ).order_by(AdminAuditLog.id.desc()).first()
    assert log is not None
    assert log.status_code in (401, 403)
