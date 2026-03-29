import re

import httpx

from .base import Provider, IntrospectionResult


class GCPProvider(Provider):
    name = "GCP"

    patterns = [
        re.compile(r"^AIzaSy[A-Za-z0-9_-]{33}$"),  # Google API key
    ]

    async def introspect(self, key: str) -> IntrospectionResult:
        rotation_url = "https://console.cloud.google.com/apis/credentials"

        # GCP API keys don't expose expiry via an unauthenticated endpoint.
        # We validate by calling the Cloud Resource Manager API, which accepts
        # API keys and returns 400 with "keyInvalid" for bad keys.
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://cloudresourcemanager.googleapis.com/v1/projects",
                    params={"key": key, "pageSize": "1"},
                )
        except httpx.HTTPError:
            return IntrospectionResult(
                provider=self.name,
                metadata={"error": "Could not reach Google API"},
                rotation_url=rotation_url,
                rotation_steps=self._rotation_steps(),
            )

        if resp.status_code == 400:
            error_reason = (
                resp.json()
                .get("error", {})
                .get("errors", [{}])[0]
                .get("reason", "")
            )
            if error_reason == "keyInvalid":
                return IntrospectionResult(
                    provider=self.name,
                    metadata={"status": "invalid"},
                    rotation_url=rotation_url,
                    rotation_steps=self._rotation_steps(),
                )

        return IntrospectionResult(
            provider=self.name,
            expires_at=None,
            metadata={
                "note": (
                    "GCP API keys do not expire. "
                    "For service account keys with expiry, track the key ID and "
                    "check validity in the Cloud Console under IAM → Service Accounts."
                ),
            },
            rotation_url=rotation_url,
            rotation_steps=self._rotation_steps(),
        )

    @staticmethod
    def _rotation_steps() -> list[str]:
        return [
            "Go to https://console.cloud.google.com/apis/credentials",
            "Locate the API key — note any restrictions before proceeding",
            "Click the key name, then 'Regenerate key' (or create a new key with the same restrictions)",
            "Copy the new key and update it in your secret manager",
            "Delete or restrict the old key",
        ]
