import re

import httpx

from .base import Provider, IntrospectionResult


class TerraformCloudProvider(Provider):
    name = "Terraform Cloud"

    patterns = [
        re.compile(r"^[A-Za-z0-9]+\.atlasv1\.[A-Za-z0-9]{64,}$"),
    ]

    async def introspect(self, key: str) -> IntrospectionResult:
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/vnd.api+json",
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://app.terraform.io/api/v2/account/details",
                    headers=headers,
                )

                if resp.status_code == 401:
                    return IntrospectionResult(
                        provider=self.name,
                        metadata={"status": "invalid_or_expired"},
                        rotation_url="https://app.terraform.io/app/settings/tokens",
                        rotation_steps=self._rotation_steps(),
                    )

                data = resp.json().get("data", {})
                attrs = data.get("attributes", {})

                # Fetch the token's own metadata to get expiry
                expiry = None
                try:
                    tokens_resp = await client.get(
                        "https://app.terraform.io/api/v2/users/user/authentication-tokens",
                        headers=headers,
                    )
                    if tokens_resp.status_code == 200:
                        for token_data in tokens_resp.json().get("data", []):
                            expired_at = token_data.get("attributes", {}).get("expired-at")
                            if expired_at:
                                from datetime import datetime
                                expiry = datetime.fromisoformat(
                                    expired_at.replace("Z", "+00:00")
                                ).date()
                                break
                except (httpx.HTTPError, ValueError, TypeError):
                    pass

        except httpx.HTTPError:
            return IntrospectionResult(
                provider=self.name,
                metadata={"error": "Could not reach Terraform Cloud API"},
                rotation_url="https://app.terraform.io/app/settings/tokens",
                rotation_steps=self._rotation_steps(),
            )

        return IntrospectionResult(
            provider=self.name,
            expires_at=expiry,
            metadata={
                "username": attrs.get("username"),
                "email": attrs.get("email"),
                **({"note": "Token has no configured expiration"} if not expiry else {}),
            },
            rotation_url="https://app.terraform.io/app/settings/tokens",
            rotation_steps=self._rotation_steps(),
        )

    @staticmethod
    def _rotation_steps() -> list[str]:
        return [
            "Go to https://app.terraform.io/app/settings/tokens (user) or Organization > Settings > API Tokens (org/team)",
            "Click 'Create an API token' or 'Regenerate' on the existing token",
            "Copy the new token and update it in your secret manager or CI/CD variables",
            "Verify your Terraform runs succeed with the new token",
            "Delete or let the old token expire",
        ]
