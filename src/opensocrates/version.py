"""Single source for release, schema, content, routing, and verifier identities."""

from __future__ import annotations

from typing import Final

PRODUCT_NAME: Final[str] = "opensocrates"
PRODUCT_VERSION: Final[str] = "1.1.3"
SCHEMA_VERSION: Final[str] = "1.0.0"
SCHEMA_MAJOR: Final[int] = 1
CONTENT_REVISION: Final[int] = 1
ROUTER_VERSION: Final[str] = "1.0.0"
VERIFIER_VERSION: Final[str] = "1.0.0"
RULESET_VERSION: Final[str] = "1.0.0"


def version_info() -> dict[str, str | int]:
    """Return the canonical identity payload used by the version command."""

    return {
        "product": PRODUCT_NAME,
        "product_version": PRODUCT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "schema_major": SCHEMA_MAJOR,
        "content_revision": CONTENT_REVISION,
        "router_version": ROUTER_VERSION,
        "verifier_version": VERIFIER_VERSION,
        "ruleset_version": RULESET_VERSION,
    }
