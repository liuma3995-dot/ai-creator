# -*- coding: utf-8 -*-
"""测试模型输出清理：移除推理模型混入正文的 <think> 块"""
from app.services.langchain.service import clean_model_content


def test_removes_think_block_from_head():
    raw = "<think>The user wants me to write a note.</think>\n\n正文内容：AI 突破改变了生活。"
    cleaned = clean_model_content(raw)
    assert "<think>" not in cleaned
    assert "正文内容" in cleaned
    assert cleaned.startswith("正文内容")


def test_removes_multiple_think_blocks():
    raw = "开头。<think>思考一</think>中间内容。<think>思考二</think>结尾。"
    cleaned = clean_model_content(raw)
    assert "<think>" not in cleaned
    assert cleaned == "开头。中间内容。结尾。"


def test_normal_content_unchanged():
    raw = "今天天气很好，适合出去玩。"
    assert clean_model_content(raw) == raw


def test_empty_and_whitespace():
    assert clean_model_content("") == ""
    assert clean_model_content("   ") == ""
