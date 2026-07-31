"""OpenSocrates v1 runtime package.

The package intentionally has no production dependency outside Python's
standard library.  Host adapters and persistence layers are added in later
work packages; the foundational contracts are importable on their own.
"""

from .version import (
    CONTENT_REVISION,
    PRODUCT_VERSION,
    ROUTER_VERSION,
    RULESET_VERSION,
    SCHEMA_VERSION,
    VERIFIER_VERSION,
    version_info,
)

__all__ = [
    "CONTENT_REVISION",
    "PRODUCT_VERSION",
    "ROUTER_VERSION",
    "RULESET_VERSION",
    "SCHEMA_VERSION",
    "VERIFIER_VERSION",
    "version_info",
]
