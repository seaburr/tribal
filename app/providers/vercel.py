import re

import httpx

from .base import Provider, IntrospectionResult


class VercelProvider(Provider):
    name = "Vercel"

    patterns: list[re.Pattern] = []  # No distinctive prefix — select provider manually

    async def introspect(self, key: str) -> IntrospectionResult:
        rotation_url = "https://vercel.com/account/tokens"

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.vercel.com/v2/user",
                    headers={"Authorization": f"Bearer {key}"},
                )
        except httpx.HTTPError:
            return IntrospectionResult(
                provider=self.name,
                metadata={"error": "Could not reach Vercel API"},
                rotation_url=rotation_url,
                rotation_steps=self._rotation_steps(),
            )

        if resp.status_code in (401, 403):
            return IntrospectionResult(
                provider=self.name,
                metadata={"status": "invalid_or_expired"},
                rotation_url=rotation_url,
                rotation_steps=self._rotation_steps(),
            )

        user = resp.json().get("user", {})
        return IntrospectionResult(
            provider=self.name,
            expires_at=None,
            metadata={
                "username": user.get("username"),
                "email": user.get("email"),
                "note": (
                    "Token expiry is not available via the Vercel API — "
                    "set the expiration date manually when creating this resource."
                ),
            },
            rotation_url=rotation_url,
            rotation_steps=self._rotation_steps(),
        )

    @staticmethod
    def _rotation_steps() -> list[str]:
        return [
            "Go to https://vercel.com/account/tokens",
            "Click 'Create' and set an expiration if desired",
            "Copy the new token and update it in your secret manager",
            "Delete the old token from the tokens list",
        ]
