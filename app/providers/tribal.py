import os
import re

import httpx

from .base import Provider, IntrospectionResult

_BASE_URL = os.environ.get("TRIBAL_BASE_URL", "http://localhost:8000").rstrip("/")


class TribalProvider(Provider):
    name = "Tribal"

    patterns = [
        re.compile(r"^tribal_sk_[0-9a-f]{64}$"),
    ]

    def introspect_local(self, db, key: str) -> IntrospectionResult:
        """Direct DB lookup — used when introspecting keys on this instance."""
        from ..auth import hash_api_key
        from .. import models

        key_hash = hash_api_key(key)
        api_key = (
            db.query(models.ApiKey)
            .filter(
                models.ApiKey.key_hash == key_hash,
                models.ApiKey.revoked_at.is_(None),
            )
            .first()
        )

        if not api_key:
            return IntrospectionResult(
                provider=self.name,
                metadata={"status": "invalid_or_revoked"},
                rotation_url=f"{_BASE_URL}/settings/api-keys",
                rotation_steps=self._rotation_steps(),
            )

        user = db.get(models.User, api_key.user_id)
        return IntrospectionResult(
            provider=self.name,
            expires_at=None,
            metadata={
                "status": "valid",
                "name": api_key.name,
                "key_prefix": api_key.key_prefix,
                "owner": user.email if user else None,
                "last_used_at": api_key.last_used_at.isoformat() if api_key.last_used_at else None,
                "note": "Tribal API keys do not currently expire",
            },
            rotation_url=f"{_BASE_URL}/settings/api-keys",
            rotation_steps=self._rotation_steps(),
        )

    async def introspect(self, key: str) -> IntrospectionResult:
        """HTTP introspection — fallback for cross-instance key verification."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{_BASE_URL}/api/keys/verify",
                    headers={"Authorization": f"Bearer {key}"},
                )
        except httpx.HTTPError:
            return IntrospectionResult(
                provider=self.name,
                metadata={"error": "Could not reach Tribal instance"},
                rotation_url=f"{_BASE_URL}/settings/api-keys",
                rotation_steps=self._rotation_steps(),
            )

        if resp.status_code == 401:
            return IntrospectionResult(
                provider=self.name,
                metadata={"status": "invalid_or_revoked"},
                rotation_url=f"{_BASE_URL}/settings/api-keys",
                rotation_steps=self._rotation_steps(),
            )

        data = resp.json()
        return IntrospectionResult(
            provider=self.name,
            expires_at=None,
            metadata={
                "status": "valid",
                "name": data.get("name"),
                "key_prefix": data.get("key_prefix"),
                "owner": data.get("owner"),
                "last_used_at": data.get("last_used_at"),
                "note": "Tribal API keys do not currently expire",
            },
            rotation_url=f"{_BASE_URL}/settings/api-keys",
            rotation_steps=self._rotation_steps(),
        )

    @staticmethod
    def _rotation_steps() -> list[str]:
        return [
            f"Go to {_BASE_URL}/settings/api-keys",
            "Click 'New API Key', give it a name, and copy the full key",
            "Update the key in your secret manager or application config",
            "Revoke the old key from the API Keys settings page",
        ]
