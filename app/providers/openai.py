import re

import httpx

from .base import Provider, IntrospectionResult


class OpenAIProvider(Provider):
    name = "OpenAI"

    patterns = [
        re.compile(r"^sk-[A-Za-z0-9]{20,}$"),             # Legacy key format
        re.compile(r"^sk-proj-[A-Za-z0-9_-]{40,}$"),      # Project-scoped key
        re.compile(r"^sk-svcacct-[A-Za-z0-9_-]{40,}$"),   # Service account key
    ]

    async def introspect(self, key: str) -> IntrospectionResult:
        # OpenAI has no key introspection API, but we can validate by
        # hitting a lightweight endpoint
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                )
        except httpx.HTTPError:
            return IntrospectionResult(
                provider=self.name,
                metadata={"error": "Could not reach OpenAI API"},
                rotation_url="https://platform.openai.com/api-keys",
                rotation_steps=self._rotation_steps(),
            )

        if resp.status_code == 401:
            return IntrospectionResult(
                provider=self.name,
                metadata={"status": "invalid_or_expired"},
                rotation_url="https://platform.openai.com/api-keys",
                rotation_steps=self._rotation_steps(),
            )

        return IntrospectionResult(
            provider=self.name,
            expires_at=None,  # OpenAI does not expose expiration via API
            metadata={
                "status": "valid",
                "note": "OpenAI does not expose key expiration via API",
            },
            rotation_url="https://platform.openai.com/api-keys",
            rotation_steps=self._rotation_steps(),
        )

    @staticmethod
    def _rotation_steps() -> list[str]:
        return [
            "Go to https://platform.openai.com/api-keys",
            "Click 'Create new secret key'",
            "Name the key and assign it to the appropriate project",
            "Copy the new key and update it in your secret manager",
            "Delete the old key from the OpenAI dashboard",
        ]
