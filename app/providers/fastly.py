import re
from datetime import datetime

import httpx

from .base import Provider, IntrospectionResult

# Fastly tokens have no stable prefix — select provider manually.
# Introspection via GET /tokens/self returns the token's expiry date if one was set.

_NO_EXPIRY_SENTINEL = "0001-01-01T00:00:00Z"


class FastlyProvider(Provider):
    name = "Fastly"

    patterns: list[re.Pattern] = []

    async def introspect(self, key: str) -> IntrospectionResult:
        rotation_url = "https://manage.fastly.com/account/personal/tokens"

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.fastly.com/tokens/self",
                    headers={"Fastly-Key": key},
                )
        except httpx.HTTPError:
            return IntrospectionResult(
                provider=self.name,
                metadata={"error": "Could not reach Fastly API"},
                rotation_url=rotation_url,
                rotation_steps=self._rotation_steps(),
            )

        if resp.status_code == 401:
            return IntrospectionResult(
                provider=self.name,
                metadata={"status": "invalid_or_expired"},
                rotation_url=rotation_url,
                rotation_steps=self._rotation_steps(),
            )

        data = resp.json()
        expires_at = None
        expires_raw = data.get("expires_at")
        if expires_raw and expires_raw != _NO_EXPIRY_SENTINEL:
            try:
                expires_at = datetime.fromisoformat(
                    expires_raw.replace("Z", "+00:00")
                ).date()
            except ValueError:
                pass

        return IntrospectionResult(
            provider=self.name,
            expires_at=expires_at,
            metadata={
                "name": data.get("name"),
                "user_id": data.get("user_id"),
                "scope": data.get("scope", ""),
                **({"note": "Token has no expiration set"} if expires_at is None else {}),
            },
            rotation_url=rotation_url,
            rotation_steps=self._rotation_steps(),
        )

    @staticmethod
    def _rotation_steps() -> list[str]:
        return [
            "Go to https://manage.fastly.com/account/personal/tokens",
            "Click 'Create Token' and assign the same scope as the existing token",
            "Copy the new token and update it in your secret manager",
            "Delete the old token",
        ]
