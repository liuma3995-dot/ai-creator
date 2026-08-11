# -*- coding: utf-8 -*-
"""
集成测试 4.3：调用监控 ← AI 调用链路

验证：模拟 LLM 调用回调 → AIModelUsageLog 落库 → 监控 API 查询与统计正确；
失败调用被记录为 failed 并计入失败数。
"""
from types import SimpleNamespace

import pytest

from app.models.model_usage_log import AIModelUsageLog
from app.services.langchain.callbacks import UsageCallbackHandler


def _run_success_callback(user_id):
    handler = UsageCallbackHandler(
        user_id=user_id,
        ai_model_id=1,
        provider="openai",
        model_name="gpt-4",
        tool="writing",
        request_type="chat",
    )
    handler.on_llm_start(
        {}, ["你好"],
        invocation_params={"messages": [{"role": "user", "content": "你好"}]},
    )
    generation = SimpleNamespace(text="这是回复", generation_info=None)
    response = SimpleNamespace(
        generations=[[generation]],
        llm_output={
            "token_usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        },
    )
    handler.on_llm_end(response)


def _run_failed_callback(user_id):
    handler = UsageCallbackHandler(
        user_id=user_id,
        ai_model_id=2,
        provider="anthropic",
        model_name="claude-3",
        tool="writing",
        request_type="chat",
    )
    handler.on_llm_start(
        {}, ["你好"],
        invocation_params={"messages": [{"role": "user", "content": "你好"}]},
    )
    handler.on_llm_error(RuntimeError("模拟模型错误"))


@pytest.mark.integration
class TestModelUsageLink:
    """AI 调用 → 监控日志 全链路"""

    def test_llm_call_writes_log_and_shows_in_api(
        self, client, mysql_session, admin_headers, it_user
    ):
        _run_success_callback(it_user.id)

        # 落库
        log = mysql_session.query(AIModelUsageLog).filter(
            AIModelUsageLog.user_id == it_user.id
        ).first()
        assert log is not None
        assert log.provider == "openai"
        assert log.status == "success"
        assert log.total_tokens == 15
        assert log.prompt_tokens == 10
        assert log.completion_tokens == 5
        assert "这是回复" in log.output_content

        # 监控 API 可见
        logs = client.get("/api/v1/admin/model-usage/logs", headers=admin_headers)
        assert logs.status_code == 200
        items = logs.json()["data"]["items"]
        assert len(items) == 1
        # FastAPI 序列化会把 Decimal 转成字符串，按数值断言
        assert float(items[0]["total_tokens"]) == 15.0

        stats = client.get("/api/v1/admin/model-usage/stats", headers=admin_headers)
        overview = stats.json()["data"]["overview"]
        assert overview["total_calls"] == 1
        assert float(overview["total_tokens"]) == 15.0
        assert overview["failed_calls"] == 0

    def test_failed_call_recorded_in_stats(
        self, client, mysql_session, admin_headers, it_user
    ):
        _run_failed_callback(it_user.id)

        log = mysql_session.query(AIModelUsageLog).filter(
            AIModelUsageLog.user_id == it_user.id
        ).first()
        assert log.status == "failed"
        assert "模拟模型错误" in log.error_message

        stats = client.get("/api/v1/admin/model-usage/stats", headers=admin_headers)
        overview = stats.json()["data"]["overview"]
        assert overview["total_calls"] == 1
        assert overview["failed_calls"] == 1
        assert overview["success_rate"] == 0
