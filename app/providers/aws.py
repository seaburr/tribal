import re

from .base import Provider, IntrospectionResult


class AWSProvider(Provider):
    """Identifies AWS access keys.

    Full introspection requires the AWS secret key *and* STS, which is
    out of scope for transient single-key inspection.  This provider
    identifies the key format and returns rotation guidance.
    """

    name = "AWS"

    patterns = [
        re.compile(r"^AKIA[A-Z0-9]{16}$"),  # IAM user access key
        re.compile(r"^ASIA[A-Z0-9]{16}$"),  # STS temporary credentials
    ]

    async def introspect(self, key: str) -> IntrospectionResult:
        is_temporary = key.startswith("ASIA")
        return IntrospectionResult(
            provider=self.name,
            expires_at=None,
            metadata={
                "key_type": "temporary (STS)" if is_temporary else "long-lived (IAM)",
                "note": (
                    "AWS access key IDs cannot be introspected without the "
                    "corresponding secret key and STS credentials. Use the "
                    "AWS CLI: aws iam list-access-keys / "
                    "aws iam get-access-key-last-used --access-key-id <key>"
                ),
            },
            rotation_url="https://console.aws.amazon.com/iam/home#/security_credentials",
            rotation_steps=self._rotation_steps(is_temporary),
        )

    @staticmethod
    def _rotation_steps(is_temporary: bool) -> list[str]:
        if is_temporary:
            return [
                "STS temporary credentials rotate automatically",
                "If you need to revoke them, invalidate the session via the IAM console",
            ]
        return [
            "Go to IAM > Users > [user] > Security credentials",
            "Click 'Create access key' to generate a new key pair",
            "Update the access key ID and secret in your secret manager",
            "Verify your applications work with the new key",
            "Deactivate the old key, then delete it after confirming no usage",
        ]
