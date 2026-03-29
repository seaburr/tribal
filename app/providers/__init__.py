"""Provider registry with auto-discovery.

Every concrete ``Provider`` subclass defined in a module under this
package is automatically registered at import time.  Call ``identify()``
to match a key to a provider, or ``introspect()`` to identify *and*
fetch metadata in one step.
"""

import importlib
import pkgutil
from .base import Provider, IntrospectionResult

_registry: list[Provider] = []


def _discover() -> None:
    """Import all sibling modules and register Provider subclasses."""
    package = importlib.import_module(__name__)
    for _, module_name, _ in pkgutil.iter_modules(package.__path__):
        if module_name == "base":
            continue
        mod = importlib.import_module(f"{__name__}.{module_name}")
        for attr in vars(mod).values():
            if (
                isinstance(attr, type)
                and issubclass(attr, Provider)
                and attr is not Provider
            ):
                _registry.append(attr())


_discover()


def list_providers() -> list[str]:
    """Return the names of all registered providers."""
    return [p.name for p in _registry]


def identify(key: str) -> Provider | None:
    """Return the first provider whose pattern matches *key*."""
    for provider in _registry:
        if provider.matches(key):
            return provider
    return None


def find_by_name(name: str) -> Provider | None:
    """Return the provider with the given name, or None.

    Case-insensitive to be forgiving of UI inconsistencies.
    Used when the caller knows which provider to use and wants to skip
    pattern matching (e.g. for providers with no distinctive key prefix).
    """
    name_lower = name.lower()
    for provider in _registry:
        if provider.name.lower() == name_lower:
            return provider
    return None


async def introspect(key: str) -> IntrospectionResult | None:
    """Identify a key and fetch its metadata in one call.

    Returns ``None`` if no provider recognises the key pattern.
    """
    provider = identify(key)
    if provider:
        return await provider.introspect(key)
    return None


__all__ = [
    "Provider",
    "IntrospectionResult",
    "list_providers",
    "identify",
    "find_by_name",
    "introspect",
]
