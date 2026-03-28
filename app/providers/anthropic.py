import re

import httpx

from .base import Provider, IntrospectionResult


class AnthropicProvider(Provider):
    name = "Anthropic"

    patterns = [
        re.compile(r"^sk-ant-[A-Za-z0-9_-]{40,}$"),
    ]

    async def introspect(self, key: str) -> IntrospectionResult:
        # Anthropic has no key introspection API; validate with a
        # lightweight request that won't consume tokens
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={
                        "x-api-key": key,
                        "anthropic-version": "2023-06-01",
                    },
                )
        except httpx.HTTPError:
            return IntrospectionResult(
                provider=self.name,
                metadata={"error": "Could not reach Anthropic API"},
                rotation_url="https://console.anthropic.com/settings/keys",
                rotation_steps=self._rotation_steps(),
            )

        if resp.status_code == 401:
            return IntrospectionResult(
                provider=self.name,
                metadata={"status": "invalid_or_expired"},
                rotation_url="https://console.anthropic.com/settings/keys",
                rotation_steps=self._rotation_steps(),
            )

        return IntrospectionResult(
            provider=self.name,
            expires_at=None,
            metadata={
                "status": "valid",
                "note": "Anthropic does not expose key expiration via API",
            },
            rotation_url="https://console.anthropic.com/settings/keys",
            rotation_steps=self._rotation_steps(),
        )

    @staticmethod
    def _rotation_steps() -> list[str]:
        return [
            "Go to https://console.anthropic.com/settings/keys",
            "Click 'Create Key'",
            "Name the key and copy it immediately (it won't be shown again)",
            "Update the key in your secret manager",
            "Disable or delete the old key from the console",
        ]
