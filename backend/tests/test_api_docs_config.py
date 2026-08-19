# -*- coding: utf-8 -*-
"""T4 API 文档开关回归测试"""
from app.core.config import resolve_docs_enabled


class TestResolveDocsEnabled:
    def test_none_follows_debug_true(self):
        assert resolve_docs_enabled(None, True) is True

    def test_none_follows_debug_false(self):
        assert resolve_docs_enabled(None, False) is False

    def test_explicit_true_wins_in_production(self):
        assert resolve_docs_enabled(True, False) is True

    def test_explicit_false_wins_in_development(self):
        assert resolve_docs_enabled(False, True) is False


class TestDocsEndpoints:
    def test_dev_docs_available(self, client):
        # 本地开发环境（DEBUG=True）文档应可访问
        r = client.get("/docs")
        assert r.status_code == 200
        r2 = client.get("/openapi.json")
        assert r2.status_code == 200
