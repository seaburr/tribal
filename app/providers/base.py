"""Base class for credential providers.

Each provider knows how to identify API keys by pattern and optionally
introspect them via the issuing service's API.  Providers must NEVER
persist, log, or store the key material -- it exists only for the
duration of the ``introspect()`` call and is discarded immediately.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
import re


@dataclass
class IntrospectionResult:
    """Metadata returned after inspecting a key -- never contains the key itself."""

    provider: str
    expires_at: date | None = None
    metadata: dict = field(default_factory=dict)
    rotation_url: str | None = None
    rotation_steps: list[str] = field(default_factory=list)


class Provider(ABC):
    """Abstract base for a credential provider plugin.

    To add a new provider, create a module in ``app/providers/`` that
    defines a subclass of ``Provider``.  It will be auto-discovered at
    import time -- no registration boilerplate required.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name (e.g. 'GitHub')."""

    @property
    @abstractmethod
    def patterns(self) -> list[re.Pattern]:
        """Compiled regexes that match this provider's key formats."""

    @abstractmethod
    async def introspect(self, key: str) -> IntrospectionResult:
        """Call the provider's API to retrieve key metadata.

        Implementations must:
        - NEVER store, log, or persist ``key``
        - Return an ``IntrospectionResult`` even on failure (use metadata
          to indicate errors)
        - Handle network errors gracefully
        """

    def introspect_local(self, db, key: str) -> "IntrospectionResult | None":
        """Optional in-process introspection using a live database session.

        Override this for providers that run on the same host and can query
        the local database directly, avoiding an outbound HTTP round-trip.
        Return ``None`` to signal that the caller should fall back to
        ``introspect()``.
        """
        return None

    def matches(self, key: str) -> bool:
        """Return True if ``key`` matches any of this provider's patterns."""
        return any(p.match(key) for p in self.patterns)
