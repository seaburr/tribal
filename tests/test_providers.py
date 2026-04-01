"""Tests for the provider plugin system.

These tests verify pattern matching and the registry mechanics.
Introspection tests mock HTTP calls to avoid hitting real APIs.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.providers import identify, introspect, list_providers
from app.providers.base import IntrospectionResult


# ── Registry ─────────────────────────────────────────────────────────────────

class TestRegistry:
    def test_providers_discovered(self):
        names = list_providers()
        assert len(names) >= 7  # GitHub, Stripe, OpenAI, Anthropic, AWS, Slack, SendGrid + Azure
        assert "GitHub" in names
        assert "Stripe" in names
        assert "AWS" in names

    def test_list_providers_returns_strings(self):
        for name in list_providers():
            assert isinstance(name, str)


# ── Pattern matching (identify only, no API calls) ───────────────────────────

class TestGitHub:
    def test_classic_pat(self):
        p = identify("ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij")
        assert p is not None
        assert p.name == "GitHub"

    def test_fine_grained_pat(self):
        p = identify("github_pat_" + "A" * 82)
        assert p is not None
        assert p.name == "GitHub"

    def test_no_match_short(self):
        assert identify("ghp_short") is None


class TestStripe:
    def test_live_secret(self):
        p = identify("sk_live_" + "A" * 24)
        assert p is not None
        assert p.name == "Stripe"

    def test_test_secret(self):
        p = identify("sk_test_" + "B" * 30)
        assert p is not None
        assert p.name == "Stripe"

    def test_restricted_key(self):
        p = identify("rk_live_" + "C" * 24)
        assert p is not None
        assert p.name == "Stripe"

    def test_publishable_key(self):
        p = identify("pk_test_" + "D" * 24)
        assert p is not None
        assert p.name == "Stripe"


class TestOpenAI:
    def test_legacy_key(self):
        p = identify("sk-" + "A" * 48)
        assert p is not None
        assert p.name == "OpenAI"

    def test_project_key(self):
        p = identify("sk-proj-" + "A" * 50)
        assert p is not None
        assert p.name == "OpenAI"

    def test_service_account_key(self):
        p = identify("sk-svcacct-" + "A" * 50)
        assert p is not None
        assert p.name == "OpenAI"


class TestAnthropic:
    def test_api_key(self):
        p = identify("sk-ant-" + "A" * 50)
        assert p is not None
        assert p.name == "Anthropic"

    def test_too_short(self):
        assert identify("sk-ant-short") is None


class TestAWS:
    def test_iam_key(self):
        p = identify("AKIA" + "A" * 16)
        assert p is not None
        assert p.name == "AWS"

    def test_sts_key(self):
        p = identify("ASIA" + "B" * 16)
        assert p is not None
        assert p.name == "AWS"


class TestSlack:
    def test_bot_token(self):
        p = identify("xoxb-123456-abcdef-ghijklmnop")
        assert p is not None
        assert p.name == "Slack"

    def test_user_token(self):
        p = identify("xoxp-123-456-789-abcdef1234567890")
        assert p is not None
        assert p.name == "Slack"


class TestSendGrid:
    def test_api_key(self):
        key = "SG." + "A" * 22 + "." + "B" * 43
        p = identify(key)
        assert p is not None
        assert p.name == "SendGrid"


class TestAzure:
    def test_client_secret_v2(self):
        key = "~" + "A" * 33
        p = identify(key)
        assert p is not None
        assert "Azure" in p.name or "Entra" in p.name

    def test_storage_key(self):
        key = "A" * 86 + "=="
        p = identify(key)
        assert p is not None
        assert "Azure" in p.name or "Storage" in p.name

    def test_sas_token_with_expiry(self):
        token = "?sv=2021-06-08&ss=b&srt=sco&se=2025-12-31T23%3A59%3A59Z&sig=abc123%2Bdef%3D"
        p = identify(token)
        assert p is not None
        assert "SAS" in p.name

    def test_sas_full_url(self):
        url = "https://myaccount.blob.core.windows.net/container?sv=2021-06-08&se=2025-06-01&sig=abc%2B123%3D"
        p = identify(url)
        assert p is not None
        assert "SAS" in p.name


class TestTerraformCloud:
    def test_user_token(self):
        key = "abcdef" + ".atlasv1." + "a" * 64
        p = identify(key)
        assert p is not None
        assert p.name == "Terraform Cloud"

    def test_no_match_without_atlasv1(self):
        assert identify("somerandomprefixtoken123") is None


class TestDigitalOcean:
    def test_pat(self):
        key = "dop_v1_" + "a" * 64
        p = identify(key)
        assert p is not None
        assert p.name == "DigitalOcean"

    def test_too_short(self):
        assert identify("dop_v1_abc") is None


class TestNoMatch:
    def test_random_string(self):
        assert identify("not-a-real-key") is None

    def test_empty(self):
        assert identify("") is None


# ── Introspection (mocked HTTP) ─────────────────────────────────────────────

class TestIntrospection:
    def test_github_introspect_valid(self):
        import asyncio

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {
            # GitHub returns the first moment the token is *invalid* (midnight),
            # so the last valid day should be the day before.
            "github-authentication-token-expiration": "2026-01-01 00:00:00 UTC",
            "x-oauth-scopes": "repo, read:org",
        }
        mock_resp.json.return_value = {"login": "testuser"}

        with patch("app.providers.github.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
                get=AsyncMock(return_value=mock_resp)
            ))
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            result = asyncio.run(introspect("ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"))

        from datetime import date
        assert result is not None
        assert result.provider == "GitHub"
        assert result.expires_at == date(2025, 12, 31)  # midnight Jan 1 → last valid day Dec 31
        assert result.metadata["login"] == "testuser"
        assert len(result.rotation_steps) > 0

    def test_github_introspect_invalid(self):
        import asyncio

        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with patch("app.providers.github.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
                get=AsyncMock(return_value=mock_resp)
            ))
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            result = asyncio.run(introspect("ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"))

        assert result is not None
        assert result.metadata["status"] == "invalid_or_expired"

    def test_introspect_no_match(self):
        import asyncio
        result = asyncio.run(introspect("not-a-real-key"))
        assert result is None

    def test_aws_introspect_no_http(self):
        """AWS provider returns guidance without making HTTP calls."""
        import asyncio
        result = asyncio.run(introspect("AKIA" + "A" * 16))
        assert result is not None
        assert result.provider == "AWS"
        assert result.metadata["key_type"] == "long-lived (IAM)"
        assert len(result.rotation_steps) > 0

    def test_azure_sas_extracts_expiry(self):
        import asyncio
        from app.providers.azure import AzureSASTokenProvider
        provider = AzureSASTokenProvider()
        token = "?sv=2021-06-08&ss=b&se=2025-12-31T23:59:59Z&sig=abc123"
        result = asyncio.run(provider.introspect(token))
        assert result.expires_at is not None
        assert result.expires_at.year == 2025
        assert result.expires_at.month == 12
        assert result.expires_at.day == 31
