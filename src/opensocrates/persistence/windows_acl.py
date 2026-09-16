"""Compatibility exports for native Windows security primitives."""

from opensocrates.windows_security import current_sid, inspect_acl, secure_acl

__all__ = ["current_sid", "inspect_acl", "secure_acl"]
