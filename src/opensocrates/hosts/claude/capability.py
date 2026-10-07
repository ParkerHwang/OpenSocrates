"""Dated documentation capability metadata, never synthetic live receipts."""

from __future__ import annotations


def capability_contract() -> dict[str, str]:
    return {
        "host": "claude",
        "target": "darwin-arm64",
        "status": "unknown",
        "evidence": "documented_contract_only",
        "source": "https://code.claude.com/docs/en/hooks",
        "source_checked_at": "2026-10-07",
        "application": "unverified",
        "windows_native": "unavailable",
        "chat_cowork": "separate_account_content_transport",
    }
