"""Azure / Entra ID credential provider.

Covers service principal client secrets, storage account keys, SAS
tokens, Cosmos DB keys, and other common Azure credential formats.
"""

import re
from datetime import datetime

from .base import Provider, IntrospectionResult


class AzureClientSecretProvider(Provider):
    """Azure AD / Entra ID app registration client secrets.

    Client secrets are opaque base64 strings (typically 34-44 chars)
    with a tilde prefix in newer formats.  There is no public API to
    introspect a client secret without the corresponding tenant/client
    IDs, so this provider focuses on identification and guidance.
    """

    name = "Azure Entra ID (Client Secret)"

    patterns = [
        # Newer Entra ID client secrets (v2): ~-prefixed, 34 chars
        re.compile(r"^~[A-Za-z0-9_.~-]{33}$"),
    ]

    async def introspect(self, key: str) -> IntrospectionResult:
        return IntrospectionResult(
            provider=self.name,
            expires_at=None,
            metadata={
                "note": (
                    "Azure client secrets cannot be introspected without the "
                    "tenant ID and client ID.  Check the app registration in "
                    "Entra ID to see the secret's configured expiration."
                ),
                "tip": (
                    "Use 'az ad app credential list --id <app-id>' to check "
                    "expiration dates for all credentials on this registration."
                ),
            },
            rotation_url="https://portal.azure.com/#view/Microsoft_AAD_IAM/ActiveDirectoryMenuBlade/~/RegisteredApps",
            rotation_steps=self._rotation_steps(),
        )

    @staticmethod
    def _rotation_steps() -> list[str]:
        return [
            "Go to Azure Portal > Entra ID > App registrations",
            "Find the app and go to Certificates & secrets",
            "Click 'New client secret', set a description and expiry",
            "Copy the secret value immediately (it won't be shown again)",
            "Update the secret in your secret manager / Key Vault",
            "Delete the old secret after confirming the new one works",
        ]


class AzureStorageKeyProvider(Provider):
    """Azure Storage account access keys.

    Storage keys are 88-character base64 strings ending with '=='.
    """

    name = "Azure Storage Account Key"

    patterns = [
        re.compile(r"^[A-Za-z0-9+/]{86}==$"),
    ]

    async def introspect(self, key: str) -> IntrospectionResult:
        return IntrospectionResult(
            provider=self.name,
            expires_at=None,
            metadata={
                "note": (
                    "Storage account keys do not expire but should be "
                    "rotated regularly.  Azure provides two keys (key1/key2) "
                    "to enable zero-downtime rotation."
                ),
                "tip": (
                    "Use 'az storage account keys renew' to rotate, or "
                    "configure an automated rotation policy in Key Vault."
                ),
            },
            rotation_url="https://portal.azure.com/#view/HubsExtension/BrowseResource/resourceType/Microsoft.Storage%2FStorageAccounts",
            rotation_steps=self._rotation_steps(),
        )

    @staticmethod
    def _rotation_steps() -> list[str]:
        return [
            "Go to Azure Portal > Storage accounts > [account] > Access keys",
            "Click 'Rotate key' on key1 or key2 (use the one NOT currently in production)",
            "Update your application config / Key Vault with the new key",
            "Verify your application works with the new key",
            "Rotate the other key once the first rotation is confirmed",
        ]


class AzureSASTokenProvider(Provider):
    """Azure Shared Access Signature (SAS) tokens.

    SAS tokens are URL query-string parameters that include 'sig=' and
    other SAS-specific parameters.  They often embed their own expiry.
    """

    name = "Azure SAS Token"

    patterns = [
        # SAS query string starting with ?sv=
        re.compile(r"^\?sv=\d{4}-\d{2}-\d{2}&.*sig=[A-Za-z0-9%+/=]+.*$"),
        # Full URL with SAS params
        re.compile(r"^https?://[^?]+\?.*sig=[A-Za-z0-9%+/=]+.*se=.+$"),
        # SAS params with se before sig
        re.compile(r"^https?://[^?]+\?.*se=.+&.*sig=[A-Za-z0-9%+/=]+.*$"),
    ]

    async def introspect(self, key: str) -> IntrospectionResult:
        # Try to extract the expiry (se= parameter) from the SAS token itself
        expiry = None
        import urllib.parse
        # Handle both full URLs and bare query strings
        query = key.split("?", 1)[-1] if "?" in key else key.lstrip("?")
        params = urllib.parse.parse_qs(query)
        se_values = params.get("se", [])
        if se_values:
            try:
                # se is typically ISO 8601: 2025-12-31T23:59:59Z
                expiry_str = se_values[0].replace("Z", "+00:00")
                expiry = datetime.fromisoformat(expiry_str).date()
            except (ValueError, IndexError):
                pass

        return IntrospectionResult(
            provider=self.name,
            expires_at=expiry,
            metadata={
                "note": (
                    "SAS token expiry was extracted from the 'se' parameter.  "
                    "SAS tokens cannot be revoked individually -- rotate the "
                    "underlying storage account key to invalidate all SAS "
                    "tokens signed with it."
                ) if expiry else (
                    "Could not extract expiry from SAS token.  Check the 'se' "
                    "parameter or the policy that generated it."
                ),
            },
            rotation_url="https://portal.azure.com/#view/HubsExtension/BrowseResource/resourceType/Microsoft.Storage%2FStorageAccounts",
            rotation_steps=self._rotation_steps(),
        )

    @staticmethod
    def _rotation_steps() -> list[str]:
        return [
            "Generate a new SAS token with an updated expiry from the Azure Portal or CLI",
            "Update the SAS token in your application config / secret manager",
            "If using a stored access policy, update the policy's expiry instead",
            "To revoke all existing SAS tokens, rotate the storage account key they were signed with",
        ]


class AzureCosmosDBKeyProvider(Provider):
    """Azure Cosmos DB primary/secondary keys.

    Cosmos DB keys are 88-character base64 strings (same format as
    storage keys but used in a different context).  Since we can't
    distinguish them from storage keys by format alone, this provider
    has lower priority (registered after AzureStorageKeyProvider).
    """

    name = "Azure Cosmos DB Key"

    # Same format as storage keys -- the registry will match storage
    # first due to discovery order, which is fine.  This provider is
    # here for explicit use when the caller knows the context.
    patterns: list[re.Pattern] = []

    async def introspect(self, key: str) -> IntrospectionResult:
        return IntrospectionResult(
            provider=self.name,
            expires_at=None,
            metadata={
                "note": (
                    "Cosmos DB keys do not expire.  Azure provides "
                    "primary and secondary keys for zero-downtime rotation."
                ),
            },
            rotation_url="https://portal.azure.com/#view/HubsExtension/BrowseResource/resourceType/Microsoft.DocumentDB%2FdatabaseAccounts",
            rotation_steps=[
                "Go to Azure Portal > Cosmos DB > [account] > Keys",
                "Click 'Regenerate' on the secondary key",
                "Update your application to use the new secondary key",
                "Once confirmed, regenerate the primary key",
                "Update your application to use the new primary key",
            ],
        )
