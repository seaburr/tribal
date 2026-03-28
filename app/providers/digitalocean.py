import re

import httpx

from .base import Provider, IntrospectionResult


class DigitalOceanProvider(Provider):
    name = "DigitalOcean"

    patterns = [
        re.compile(r"^dop_v1_[a-f0-9]{64}$"),
    ]

    async def introspect(self, key: str) -> IntrospectionResult:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.digitalocean.com/v2/account",
                    headers={"Authorization": f"Bearer {key}"},
                )
        except httpx.HTTPError:
            return IntrospectionResult(
                provider=self.name,
                metadata={"error": "Could not reach DigitalOcean API"},
                rotation_url="https://cloud.digitalocean.com/account/api/tokens",
                rotation_steps=self._rotation_steps(),
            )

        if resp.status_code == 401:
            return IntrospectionResult(
                provider=self.name,
                metadata={"status": "invalid_or_expired"},
                rotation_url="https://cloud.digitalocean.com/account/api/tokens",
                rotation_steps=self._rotation_steps(),
            )

        data = resp.json().get("account", {})
        return IntrospectionResult(
            provider=self.name,
            expires_at=None,  # DO tokens do not expire
            metadata={
                "email": data.get("email"),
                "status": data.get("status"),
                "note": "DigitalOcean personal access tokens do not expire -- rotate on a schedule",
            },
            rotation_url="https://cloud.digitalocean.com/account/api/tokens",
            rotation_steps=self._rotation_steps(),
        )

    @staticmethod
    def _rotation_steps() -> list[str]:
        return [
            "Go to https://cloud.digitalocean.com/account/api/tokens",
            "Click 'Generate New Token'",
            "Name the token and select the required scopes (read/write)",
            "Copy the new token and update it in your secret manager",
            "Delete the old token from the tokens list",
        ]
