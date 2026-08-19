# -*- coding: utf-8 -*-
"""URL 抓取子功能：SSRF 防护与正文提取测试"""
import socket

import pytest

from app.api.v1.writing import _extract_page_content, validate_fetch_url


class TestValidateFetchUrl:
    """SSRF 防护校验"""

    def test_rejects_non_http_schemes(self):
        for bad in ["file:///etc/passwd", "ftp://example.com/x", "javascript:alert(1)"]:
            with pytest.raises(ValueError, match="仅支持 http/https"):
                validate_fetch_url(bad)

    def test_rejects_private_and_reserved_ip_literals(self):
        for bad in [
            "http://127.0.0.1/",
            "http://127.0.0.1:8000/health",
            "http://10.0.0.1/",
            "http://172.16.0.1/",
            "http://192.168.1.1/",
            "http://169.254.169.254/latest/meta-data",
            "http://0.0.0.0/",
            "http://[::1]/",
        ]:
            with pytest.raises(ValueError, match="禁止"):
                validate_fetch_url(bad)

    def test_rejects_localhost_hostname(self):
        with pytest.raises(ValueError, match="本机"):
            validate_fetch_url("http://localhost:8000/health")

    def test_accepts_public_url(self, monkeypatch):
        monkeypatch.setattr(
            socket,
            "getaddrinfo",
            lambda host, port: [(2, 1, 6, "", ("93.184.216.34", 0))],
        )
        assert validate_fetch_url("https://example.com/article") == "https://example.com/article"

    def test_rejects_domain_resolving_to_private_ip(self, monkeypatch):
        monkeypatch.setattr(
            socket,
            "getaddrinfo",
            lambda host, port: [(2, 1, 6, "", ("10.0.0.5", 0))],
        )
        with pytest.raises(ValueError, match="内网"):
            validate_fetch_url("https://internal.example.com/")

    def test_strips_fragment_and_adds_default_scheme(self, monkeypatch):
        monkeypatch.setattr(
            socket,
            "getaddrinfo",
            lambda host, port: [(2, 1, 6, "", ("93.184.216.34", 0))],
        )
        assert validate_fetch_url("example.com/path#frag") == "https://example.com/path"


class TestExtractPageContent:
    def test_extracts_title_and_paragraphs(self):
        html = """
        <html><head><title>测试文章标题</title></head>
        <body>
          <nav><a>导航链接</a></nav>
          <script>var x = 1;</script>
          <article>
            <h1>文章大标题</h1>
            <p>这是第一段正文内容，长度足够长以便提取。</p>
            <p>这是第二段正文内容，同样足够长。</p>
          </article>
          <footer>版权信息</footer>
        </body></html>
        """
        title, content = _extract_page_content(html)
        assert title == "测试文章标题"
        assert "这是第一段正文内容" in content
        assert "这是第二段正文内容" in content
        assert "导航链接" not in content
        assert "版权信息" not in content
        assert "var x" not in content

    def test_returns_empty_when_no_meaningful_text(self):
        html = "<html><head><title>t</title></head><body><p>短</p></body></html>"
        title, content = _extract_page_content(html)
        assert title == "t"
        assert content == ""

    def test_falls_back_to_dense_text_for_div_layout(self):
        """SPA/div 布局页面：语义标签提取不到时按文本密度兜底"""
        html = """
        <html><head><title>SPA页面</title></head>
        <body>
          <div id="app">
            <div class="feed-item"><a href="/x">这是第一条资讯标题，内容足够长可以提取</a></div>
            <div class="feed-item"><a href="/y">这是第二条资讯摘要文字，也足够长能被提取</a></div>
          </div>
        </body></html>
        """
        title, content = _extract_page_content(html)
        assert title == "SPA页面"
        assert "这是第一条资讯标题" in content
        assert "这是第二条资讯摘要文字" in content


class TestFetchUrlEndpointSecurity:
    def test_blocks_internal_url_before_network(self, client, auth_headers):
        r = client.post(
            "/api/v1/writing/fetch-url",
            json={"url": "http://127.0.0.1:8000/health"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is False
        assert "禁止" in data["error"]

    def test_blocks_non_http_scheme(self, client, auth_headers):
        r = client.post(
            "/api/v1/writing/fetch-url",
            json={"url": "file:///etc/passwd"},
            headers=auth_headers,
        )
        data = r.json()
        assert data["success"] is False
        assert "仅支持 http/https" in data["error"]
