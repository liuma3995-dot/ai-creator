# -*- coding: utf-8 -*-
"""
集成测试 4.1：活动参与 → 积分发放链路

验证：参与活动 → 用户积分增加、CreditTransaction 落库、参与记录、
活动人数/成本更新；失败场景不产生半截数据。
"""
from datetime import datetime, timedelta

import pytest

from app.models.operation import Activity, ActivityParticipation, ActivityStatus, ActivityType
from app.models.user import User
from app.models.credit import CreditTransaction


def _activity_payload(**kwargs):
    data = dict(
        title="积分活动",
        activity_type="credit_gift",
        start_time=(datetime.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S"),
        end_time=(datetime.now() + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S"),
        reward_type="credits",
        reward_amount=50,
    )
    data.update(kwargs)
    return data


def _make_activity(db, **kwargs):
    defaults = dict(
        title="库内活动",
        activity_type=ActivityType.CREDIT_GIFT,
        status=ActivityStatus.ACTIVE,
        rules={"credits": 30},
        start_time=datetime.now() - timedelta(days=1),
        end_time=datetime.now() + timedelta(days=7),
    )
    defaults.update(kwargs)
    activity = Activity(**defaults)
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


@pytest.mark.integration
class TestActivityCreditLink:
    """活动 → 积分 全链路"""

    def test_participate_grants_credits_and_records_transaction(
        self, client, mysql_session, admin_headers, it_user, it_user_headers
    ):
        # 管理员创建活动
        created = client.post(
            "/api/v1/admin/operation/activities",
            json=_activity_payload(),
            headers=admin_headers,
        )
        assert created.status_code == 200
        activity_id = created.json()["data"]["id"]

        # 管理员将活动激活后才能参与
        activated = client.put(
            f"/api/v1/admin/operation/activities/{activity_id}",
            json={"status": "active"},
            headers=admin_headers,
        )
        assert activated.status_code == 200

        mysql_session.expire_all()
        before = mysql_session.query(User).filter(User.id == it_user.id).first().credits

        # 用户参与
        participated = client.post(
            f"/api/v1/operation/activities/{activity_id}/participate",
            json={"activity_id": activity_id},
            headers=it_user_headers,
        )
        assert participated.status_code == 200
        assert participated.json()["data"]["reward_amount"] == 50

        # 积分到账
        mysql_session.expire_all()
        after = mysql_session.query(User).filter(User.id == it_user.id).first().credits
        assert after == before + 50

        # 交易流水落库
        mysql_session.expire_all()
        tx = mysql_session.query(CreditTransaction).filter(
            CreditTransaction.related_type == "activity",
            CreditTransaction.user_id == it_user.id,
        ).first()
        assert tx is not None
        assert tx.amount == 50

        # 参与记录与活动人数
        participation = mysql_session.query(ActivityParticipation).filter(
            ActivityParticipation.activity_id == activity_id,
            ActivityParticipation.user_id == it_user.id,
        ).first()
        assert participation is not None
        refreshed = mysql_session.query(Activity).filter(Activity.id == activity_id).first()
        assert refreshed.current_participants == 1

    def test_duplicate_participate_no_double_reward(
        self, client, mysql_session, admin_headers, it_user, it_user_headers
    ):
        activity = _make_activity(mysql_session, rules={"credits": 30})
        payload = {"activity_id": activity.id}

        first = client.post(
            f"/api/v1/operation/activities/{activity.id}/participate",
            json=payload,
            headers=it_user_headers,
        )
        assert first.status_code == 200
        mysql_session.expire_all()
        before = mysql_session.query(User).filter(User.id == it_user.id).first().credits

        second = client.post(
            f"/api/v1/operation/activities/{activity.id}/participate",
            json=payload,
            headers=it_user_headers,
        )
        assert second.status_code == 400

        mysql_session.expire_all()
        after = mysql_session.query(User).filter(User.id == it_user.id).first().credits
        assert after == before
        mysql_session.expire_all()
        tx_count = mysql_session.query(CreditTransaction).filter(
            CreditTransaction.related_type == "activity",
            CreditTransaction.user_id == it_user.id,
        ).count()
        assert tx_count == 1

    def test_full_activity_rejects_and_keeps_data_consistent(
        self, client, mysql_session, admin_headers, it_user, it_user_headers
    ):
        activity = _make_activity(
            mysql_session, rules={"credits": 30}, max_participants=1, current_participants=1
        )
        mysql_session.expire_all()
        before = mysql_session.query(User).filter(User.id == it_user.id).first().credits

        r = client.post(
            f"/api/v1/operation/activities/{activity.id}/participate",
            json={"activity_id": activity.id},
            headers=it_user_headers,
        )
        assert r.status_code == 400

        mysql_session.expire_all()
        after = mysql_session.query(User).filter(User.id == it_user.id).first().credits
        assert after == before
        mysql_session.expire_all()
        assert mysql_session.query(CreditTransaction).filter(
            CreditTransaction.related_type == "activity",
            CreditTransaction.user_id == it_user.id,
        ).count() == 0
