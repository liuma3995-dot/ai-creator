# -*- coding: utf-8 -*-
"""T3 默认凭据清理与种子管理员加固回归测试"""
import pytest

from app.core.config import settings, validate_production_settings


class TestProductionSettingsValidation:
    def test_default_secrets_rejected_in_production(self, monkeypatch):
        monkeypatch.setattr(settings, "DEBUG", False)
        monkeypatch.setattr(settings, "SECRET_KEY", "your-secret-key-change-in-production")
        monkeypatch.setattr(settings, "PAYMENT_CALLBACK_SECRET", "change-me-payment-callback-secret")
        monkeypatch.setattr(settings, "OAUTH_ENCRYPTION_KEY", "your-oauth-encryption-key-change-in-production")
        with pytest.raises(ValueError):
            validate_production_settings()

    def test_empty_secrets_rejected_in_production(self, monkeypatch):
        monkeypatch.setattr(settings, "DEBUG", False)
        monkeypatch.setattr(settings, "SECRET_KEY", "")
        monkeypatch.setattr(settings, "PAYMENT_CALLBACK_SECRET", "real-secret")
        monkeypatch.setattr(settings, "OAUTH_ENCRYPTION_KEY", "real-secret")
        with pytest.raises(ValueError):
            validate_production_settings()

    def test_production_with_real_secrets_passes(self, monkeypatch):
        monkeypatch.setattr(settings, "DEBUG", False)
        monkeypatch.setattr(settings, "SECRET_KEY", "real-strong-secret")
        monkeypatch.setattr(settings, "PAYMENT_CALLBACK_SECRET", "real-strong-secret")
        monkeypatch.setattr(settings, "OAUTH_ENCRYPTION_KEY", "real-strong-secret")
        validate_production_settings()

    def test_debug_mode_skips_validation(self, monkeypatch):
        monkeypatch.setattr(settings, "DEBUG", True)
        monkeypatch.setattr(settings, "SECRET_KEY", "your-secret-key-change-in-production")
        validate_production_settings()


class TestAdminInitPassword:
    def test_uses_env_password_when_set(self, monkeypatch):
        from scripts.initdb import _resolve_admin_password

        monkeypatch.setenv("ADMIN_INIT_PASSWORD", "EnvPass@123456")
        password, generated = _resolve_admin_password()
        assert password == "EnvPass@123456"
        assert generated is False

    def test_generates_random_password_when_unset(self, monkeypatch):
        from scripts.initdb import _resolve_admin_password

        monkeypatch.delenv("ADMIN_INIT_PASSWORD", raising=False)
        password, generated = _resolve_admin_password()
        assert generated is True
        assert len(password) >= 12
