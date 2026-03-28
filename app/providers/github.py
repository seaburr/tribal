import re

import httpx

from .base import Provider, IntrospectionResult


class GitHubProvider(Provider):
    name = "GitHub"

    patterns = [
        re.compile(r"^ghp_[A-Za-z0-9]{36,255}$"),    # Classic PAT
        re.compile(r"^github_pat_[A-Za-z0-9_]+$"),  # Fine-grained PAT
        re.compile(r"^gho_[A-Za-z0-9]{36}$"),       # OAuth access token
        re.compile(r"^ghs_[A-Za-z0-9]{36}$"),       # App installation token
        re.compile(r"^ghr_[A-Za-z0-9]{36}$"),       # App refresh token
    ]

    async def introspect(self, key: str) -> IntrospectionResult:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.github.com/user",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Accept": "application/vnd.github+json",
                    },
                )
        except httpx.HTTPError:
            return IntrospectionResult(
                provider=self.name,
                metadata={"error": "Could not reach GitHub API"},
                rotation_url="https://github.com/settings/tokens",
                rotation_steps=self._rotation_steps(),
            )

        if resp.status_code == 401:
            return IntrospectionResult(
                provider=self.name,
                metadata={"status": "invalid_or_expired"},
                rotation_url="https://github.com/settings/tokens",
                rotation_steps=self._rotation_steps(),
            )

        # GitHub returns token expiration in the response header for
        # fine-grained PATs: github-authentication-token-expiration
        expiry = None
        exp_header = resp.headers.get("github-authentication-token-expiration")
        if exp_header:
            try:
                from datetime import datetime
                expiry = datetime.strptime(
                    exp_header.split(" ")[0], "%Y-%m-%d"
                ).date()
            except (ValueError, IndexError):
                pass

        data = resp.json()
        return IntrospectionResult(
            provider=self.name,
            expires_at=expiry,
            metadata={
                "login": data.get("login"),
                "scopes": resp.headers.get("x-oauth-scopes", ""),
            },
            rotation_url="https://github.com/settings/tokens",
            rotation_steps=self._rotation_steps(),
        )

    @staticmethod
    def _rotation_steps() -> list[str]:
        return [
            "Go to https://github.com/settings/tokens",
            "Click 'Generate new token' (or find the existing token to regenerate)",
            "Select the required scopes and set an expiration",
            "Copy the new token and update it in your secret manager",
            "Revoke the old token",
        ]
