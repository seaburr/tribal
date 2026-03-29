import re

import httpx

from .base import Provider, IntrospectionResult


class PagerDutyProvider(Provider):
    name = "PagerDuty"

    patterns: list[re.Pattern] = []  # No distinctive prefix — select provider manually

    async def introspect(self, key: str) -> IntrospectionResult:
        rotation_url = "https://app.pagerduty.com/api_keys"

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.pagerduty.com/users/me",
                    headers={
                        "Authorization": f"Token token={key}",
                        "Accept": "application/vnd.pagerduty+json;version=2",
                    },
                )
        except httpx.HTTPError:
            return IntrospectionResult(
                provider=self.name,
                metadata={"error": "Could not reach PagerDuty API"},
                rotation_url=rotation_url,
                rotation_steps=self._rotation_steps(),
            )

        if resp.status_code == 401:
            return IntrospectionResult(
                provider=self.name,
                metadata={"status": "invalid_or_revoked"},
                rotation_url=rotation_url,
                rotation_steps=self._rotation_steps(),
            )

        user = resp.json().get("user", {})
        return IntrospectionResult(
            provider=self.name,
            expires_at=None,
            metadata={
                "name": user.get("name"),
                "email": user.get("email"),
                "role": user.get("role"),
                "note": "PagerDuty API keys do not expire — rotate on a schedule",
            },
            rotation_url=rotation_url,
            rotation_steps=self._rotation_steps(),
        )

    @staticmethod
    def _rotation_steps() -> list[str]:
        return [
            "Go to https://app.pagerduty.com/api_keys (or User menu → API Access Keys)",
            "Click 'Create New API Key'",
            "Copy the new key and update it in your secret manager",
            "Delete the old key once the new one is confirmed working",
        ]
