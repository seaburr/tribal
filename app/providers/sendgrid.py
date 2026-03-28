import re

from .base import Provider, IntrospectionResult


class SendGridProvider(Provider):
    name = "SendGrid"

    patterns = [
        re.compile(r"^SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}$"),
    ]

    async def introspect(self, key: str) -> IntrospectionResult:
        # SendGrid keys cannot be introspected -- the API to list keys
        # requires a key with admin scope and returns IDs, not the keys
        # themselves.  Best we can do is confirm the format.
        return IntrospectionResult(
            provider=self.name,
            expires_at=None,
            metadata={
                "note": "SendGrid keys do not expire and cannot be introspected via API",
            },
            rotation_url="https://app.sendgrid.com/settings/api_keys",
            rotation_steps=self._rotation_steps(),
        )

    @staticmethod
    def _rotation_steps() -> list[str]:
        return [
            "Go to https://app.sendgrid.com/settings/api_keys",
            "Click 'Create API Key'",
            "Select the appropriate permissions (match the old key's scopes)",
            "Copy the new key and update it in your secret manager",
            "Delete the old key from the SendGrid dashboard",
        ]
