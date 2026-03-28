import re

import httpx

from .base import Provider, IntrospectionResult


class StripeProvider(Provider):
    name = "Stripe"

    patterns = [
        re.compile(r"^sk_live_[A-Za-z0-9]{24,}$"),  # Live secret key
        re.compile(r"^sk_test_[A-Za-z0-9]{24,}$"),  # Test secret key
        re.compile(r"^rk_live_[A-Za-z0-9]{24,}$"),  # Restricted key (live)
        re.compile(r"^rk_test_[A-Za-z0-9]{24,}$"),  # Restricted key (test)
        re.compile(r"^pk_live_[A-Za-z0-9]{24,}$"),  # Publishable key (live)
        re.compile(r"^pk_test_[A-Za-z0-9]{24,}$"),  # Publishable key (test)
    ]

    async def introspect(self, key: str) -> IntrospectionResult:
        # Stripe keys don't expire, but we can validate them and get account info
        is_publishable = key.startswith("pk_")
        if is_publishable:
            return IntrospectionResult(
                provider=self.name,
                metadata={"note": "Publishable keys cannot be introspected server-side"},
                rotation_url="https://dashboard.stripe.com/apikeys",
                rotation_steps=self._rotation_steps(),
            )

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.stripe.com/v1/account",
                    auth=(key, ""),
                )
        except httpx.HTTPError:
            return IntrospectionResult(
                provider=self.name,
                metadata={"error": "Could not reach Stripe API"},
                rotation_url="https://dashboard.stripe.com/apikeys",
                rotation_steps=self._rotation_steps(),
            )

        if resp.status_code == 401:
            return IntrospectionResult(
                provider=self.name,
                metadata={"status": "invalid_or_revoked"},
                rotation_url="https://dashboard.stripe.com/apikeys",
                rotation_steps=self._rotation_steps(),
            )

        data = resp.json()
        is_test = key.startswith(("sk_test_", "rk_test_"))
        return IntrospectionResult(
            provider=self.name,
            expires_at=None,  # Stripe keys do not expire
            metadata={
                "account_id": data.get("id"),
                "business_name": data.get("business_profile", {}).get("name"),
                "mode": "test" if is_test else "live",
                "note": "Stripe keys do not expire -- rotate on a schedule",
            },
            rotation_url="https://dashboard.stripe.com/apikeys",
            rotation_steps=self._rotation_steps(),
        )

    @staticmethod
    def _rotation_steps() -> list[str]:
        return [
            "Go to https://dashboard.stripe.com/apikeys",
            "Click 'Roll key...' next to the secret key",
            "Set an expiration window for the old key (e.g. 24 hours)",
            "Copy the new key and update it in your secret manager",
            "Verify your integration works with the new key before the old one expires",
        ]
