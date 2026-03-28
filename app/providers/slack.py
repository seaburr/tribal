import re

import httpx

from .base import Provider, IntrospectionResult


class SlackProvider(Provider):
    name = "Slack"

    patterns = [
        re.compile(r"^xoxb-[0-9]+-[A-Za-z0-9]+-[A-Za-z0-9]+$"),  # Bot token
        re.compile(r"^xoxp-[0-9]+-[0-9]+-[0-9]+-[a-f0-9]+$"),    # User token
        re.compile(r"^xoxe\.xoxp-[0-9]+-[A-Za-z0-9-]+$"),         # Config token
        re.compile(r"^xoxe-[0-9]+-[A-Za-z0-9-]+$"),               # Refresh token
    ]

    async def introspect(self, key: str) -> IntrospectionResult:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    "https://slack.com/api/auth.test",
                    headers={"Authorization": f"Bearer {key}"},
                )
        except httpx.HTTPError:
            return IntrospectionResult(
                provider=self.name,
                metadata={"error": "Could not reach Slack API"},
                rotation_url="https://api.slack.com/apps",
                rotation_steps=self._rotation_steps(),
            )

        data = resp.json()
        if not data.get("ok"):
            return IntrospectionResult(
                provider=self.name,
                metadata={"status": "invalid", "error": data.get("error", "unknown")},
                rotation_url="https://api.slack.com/apps",
                rotation_steps=self._rotation_steps(),
            )

        return IntrospectionResult(
            provider=self.name,
            expires_at=None,  # Slack bot/user tokens don't expire
            metadata={
                "team": data.get("team"),
                "user": data.get("user"),
                "team_id": data.get("team_id"),
            },
            rotation_url="https://api.slack.com/apps",
            rotation_steps=self._rotation_steps(),
        )

    @staticmethod
    def _rotation_steps() -> list[str]:
        return [
            "Go to https://api.slack.com/apps and select your app",
            "Navigate to OAuth & Permissions",
            "Click 'Reinstall to Workspace' to generate a new token",
            "Copy the new token and update it in your secret manager",
            "The old token is automatically revoked on reinstall",
        ]
