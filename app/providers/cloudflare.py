import re
from datetime import datetime

import httpx

from .base import Provider, IntrospectionResult


class CloudflareProvider(Provider):
    name = "Cloudflare"

    patterns: list[re.Pattern] = []  # No stable prefix — select provider manually

    async def introspect(self, key: str) -> IntrospectionResult:
        headers = {"Authorization": f"Bearer {key}"}
        rotation_url = "https://dash.cloudflare.com/profile/api-tokens"

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                verify_resp = await client.get(
                    "https://api.cloudflare.com/client/v4/user/tokens/verify",
                    headers=headers,
                )
        except httpx.HTTPError:
            return IntrospectionResult(
                provider=self.name,
                metadata={"error": "Could not reach Cloudflare API"},
                rotation_url=rotation_url,
                rotation_steps=self._rotation_steps(),
            )

        verify_data = verify_resp.json()
        if not verify_data.get("success"):
            return IntrospectionResult(
                provider=self.name,
                metadata={"status": "invalid", "errors": verify_data.get("errors", [])},
                rotation_url=rotation_url,
                rotation_steps=self._rotation_steps(),
            )

        result = verify_data.get("result", {})
        token_id = result.get("id")
        metadata: dict = {"status": result.get("status")}
        expires_at = None

        if token_id:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    detail_resp = await client.get(
                        f"https://api.cloudflare.com/client/v4/user/tokens/{token_id}",
                        headers=headers,
                    )
                detail_data = detail_resp.json()
                if detail_data.get("success"):
                    token = detail_data.get("result", {})
                    metadata["name"] = token.get("name")
                    expires_on = token.get("expires_on")
                    if expires_on:
                        expires_at = datetime.fromisoformat(
                            expires_on.replace("Z", "+00:00")
                        ).date()
                    else:
                        metadata["note"] = "Token has no expiration set"
            except (httpx.HTTPError, ValueError):
                pass

        return IntrospectionResult(
            provider=self.name,
            expires_at=expires_at,
            metadata=metadata,
            rotation_url=rotation_url,
            rotation_steps=self._rotation_steps(),
        )

    @staticmethod
    def _rotation_steps() -> list[str]:
        return [
            "Go to https://dash.cloudflare.com/profile/api-tokens",
            "Click 'Create Token' to generate a replacement with the same permissions",
            "Copy the new token and update it in your secret manager",
            "Delete the old token from the API Tokens list",
        ]
