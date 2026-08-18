# -*- coding: utf-8 -*-
"""失败退款回归测试：D6 写作 404 退款、D5 图片后台失败退款、D7 流水关联创作记录"""
import time

from app.models.credit import CreditTransaction, TransactionType
from app.models.creation import Creation


def _set_credits(db_session, user, amount=1000):
    user.credits = amount
    db_session.commit()
    db_session.refresh(user)


class TestWritingRefund:
    def test_writing_model_not_found_refunds(self, client, auth_headers, db_session, test_user):
        _set_credits(db_session, test_user)
        r = client.post(
            "/api/v1/writing/generate",
            json={
                "tool_type": "xiaohongshu_note",
                "parameters": {"topic": "测试", "keywords": "AI"},
                "model_id": 999999,
            },
            headers=auth_headers,
        )
        assert r.status_code == 404

        txs = db_session.query(CreditTransaction).filter(
            CreditTransaction.user_id == test_user.id,
            CreditTransaction.description.like("%AI写作%"),
        ).all()
        types = [t.transaction_type.value for t in txs]
        assert "consume" in types and "refund" in types
        db_session.refresh(test_user)
        assert test_user.credits == 1000, f"余额={test_user.credits}（应退款恢复为1000）"


class TestImageFailureRefund:
    def test_image_failure_refunds_and_links_transaction(self, client, auth_headers, db_session, test_user):
        _set_credits(db_session, test_user)
        r = client.post(
            "/api/v1/image/generate",
            json={"prompt": "测试图片", "model_id": 999999, "num_images": 1},
            headers=auth_headers,
        )
        assert r.status_code == 200
        time.sleep(1)

        creation = db_session.query(Creation).filter(
            Creation.user_id == test_user.id,
            Creation.creation_type == "image",
        ).order_by(Creation.id.desc()).first()
        assert creation is not None
        assert creation.status == "failed"

        consume = db_session.query(CreditTransaction).filter(
            CreditTransaction.user_id == test_user.id,
            CreditTransaction.transaction_type == TransactionType.CONSUME,
        ).order_by(CreditTransaction.id.desc()).first()
        assert consume is not None
        assert consume.related_id == creation.id, f"流水未关联创作记录（D7）：related_id={consume.related_id}"

        refund = db_session.query(CreditTransaction).filter(
            CreditTransaction.user_id == test_user.id,
            CreditTransaction.transaction_type == TransactionType.REFUND,
        ).order_by(CreditTransaction.id.desc()).first()
        assert refund is not None, "生成失败后应有退款流水（D5）"
        assert refund.related_id == creation.id

        db_session.refresh(test_user)
        assert test_user.credits == 1000, f"余额={test_user.credits}（应退款恢复为1000）"
