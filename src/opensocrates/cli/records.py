"""CLI handlers for explicit deletion and retention commands."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from ..application.delete_records import (
    AmbiguousPublicShortId,
    DeleteConfirmationRequired,
    DeleteReceipt,
    DeleteRequest,
    DeleteScope,
    RecordNotFound,
    SecureDeleteStore,
    delete_records,
)
from ..application.prune_records import (
    PruneJournal,
    PrunePlan,
    PruneReceipt,
    SecurePruneStore,
    apply_prune,
)
from ..rendering.messages import LocaleCatalog, MessageCatalogError, placeholder_names


class RecordsCommandError(ValueError):
    """Raised when a records CLI handler cannot form a catalog-backed result."""


_RECORDS_KEYS = frozenset(
    {
        "records.delete.scope",
        "records.delete.confirmation_required",
        "records.delete.not_found",
        "records.delete.ambiguous",
        "records.delete.receipt",
        "records.prune.plan",
        "records.prune.receipt",
    }
)


def _messages(catalog: LocaleCatalog | Mapping[str, object], locale: str) -> Mapping[str, str]:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    if isinstance(catalog, LocaleCatalog):
        try:
            return catalog.locale_messages[locale]
        except KeyError as error:
            raise RecordsCommandError("records locale is unavailable") from error
    if not isinstance(catalog, Mapping):
        raise RecordsCommandError("records command requires a locale catalog")
    if "locale_messages" in catalog:
        candidate = catalog.get("locale_messages")
        if isinstance(candidate, Mapping):
            candidate = candidate.get(locale)
    elif "messages" in catalog:
        declared = catalog.get("locale")
        if declared is not None and declared != locale:
            raise RecordsCommandError("records locale catalog does not match the requested locale")
        candidate = catalog.get("messages")
    elif locale in catalog and isinstance(catalog[locale], Mapping):
        candidate = catalog[locale]
    else:
        candidate = catalog
    if not isinstance(candidate, Mapping):
        raise RecordsCommandError("records locale messages must be a mapping")
    selected: dict[str, str] = {}
    for key in _RECORDS_KEYS:
        value = candidate.get(key)
        if not isinstance(value, str):
            raise RecordsCommandError(f"missing locale key {locale}.{key}")
        selected[key] = value
    return selected


def _lookup(
    catalog: LocaleCatalog | Mapping[str, object],
    locale: str,
    key: str,
    **values: object,
) -> str:
    if isinstance(catalog, LocaleCatalog):
        try:
            return catalog.lookup(locale, key, **values)
        except MessageCatalogError as error:
            raise RecordsCommandError("records locale lookup failed") from error
    messages = _messages(catalog, locale)
    template = messages.get(key)
    if not isinstance(template, str):
        raise RecordsCommandError(f"missing locale key {locale}.{key}")
    if placeholder_names(template) != frozenset(values):
        raise RecordsCommandError(f"placeholder mismatch for {locale}.{key}")
    if any(not isinstance(value, (str, int, bool)) for value in values.values()):
        raise RecordsCommandError("records message substitutions must be scalar")
    try:
        result = template.format_map({name: str(value) for name, value in values.items()})
    except (KeyError, ValueError) as error:
        raise RecordsCommandError("records locale formatting failed") from error
    if not result.strip():
        raise RecordsCommandError("records locale message is empty")
    return result


def format_delete_scope(
    scope: DeleteScope,
    catalog: LocaleCatalog | Mapping[str, object],
    locale: str,
) -> str:
    if not isinstance(scope, DeleteScope):
        raise RecordsCommandError("delete scope is invalid")
    return _lookup(catalog, locale, "records.delete.scope", count=scope.count)


def format_delete_receipt(
    receipt: DeleteReceipt,
    catalog: LocaleCatalog | Mapping[str, object],
    locale: str,
) -> str:
    if not isinstance(receipt, DeleteReceipt):
        raise RecordsCommandError("delete receipt is invalid")
    return _lookup(
        catalog,
        locale,
        "records.delete.receipt",
        count=receipt.count,
        timestamp=receipt.timestamp,
        outcome=receipt.outcome.value,
    )


def format_prune_plan(
    plan: PrunePlan,
    catalog: LocaleCatalog | Mapping[str, object],
    locale: str,
) -> str:
    if not isinstance(plan, PrunePlan):
        raise RecordsCommandError("prune plan is invalid")
    return _lookup(
        catalog,
        locale,
        "records.prune.plan",
        count=len(plan.selected),
        bytes=plan.bytes_to_free,
    )


def format_prune_receipt(
    receipt: PruneReceipt,
    catalog: LocaleCatalog | Mapping[str, object],
    locale: str,
) -> str:
    if not isinstance(receipt, PruneReceipt):
        raise RecordsCommandError("prune receipt is invalid")
    return _lookup(
        catalog,
        locale,
        "records.prune.receipt",
        count=receipt.count,
        outcome=receipt.outcome.value,
    )


def handle_delete(
    request: DeleteRequest,
    *,
    store: SecureDeleteStore,
    catalog: LocaleCatalog | Mapping[str, object],
    locale: str,
    now: datetime | None = None,
) -> str:
    """Handle one delete command and return only catalog-backed public text."""

    try:
        result = delete_records(request, store=store, now=now)
    except DeleteConfirmationRequired as error:
        return "\n".join(
            (
                format_delete_scope(error.scope, catalog, locale),
                _lookup(catalog, locale, "records.delete.confirmation_required"),
            )
        )
    except RecordNotFound:
        return _lookup(catalog, locale, "records.delete.not_found")
    except AmbiguousPublicShortId:
        return _lookup(catalog, locale, "records.delete.ambiguous")
    return format_delete_receipt(result.receipt, catalog, locale)


def handle_prune_plan(
    plan: PrunePlan,
    *,
    catalog: LocaleCatalog | Mapping[str, object],
    locale: str,
) -> str:
    """Format a read-only plan; this function performs no store operation."""

    return format_prune_plan(plan, catalog, locale)


def handle_prune_apply(
    plan: PrunePlan,
    *,
    store: SecurePruneStore,
    journal: PruneJournal,
    catalog: LocaleCatalog | Mapping[str, object],
    locale: str,
    now: datetime | None = None,
) -> str:
    receipt = apply_prune(plan, store=store, journal=journal, now=now)
    return format_prune_receipt(receipt, catalog, locale)


handle_records_delete = handle_delete
handle_records_prune_plan = handle_prune_plan
handle_records_prune_apply = handle_prune_apply


__all__ = [
    "RecordsCommandError",
    "format_delete_receipt",
    "format_delete_scope",
    "format_prune_plan",
    "format_prune_receipt",
    "handle_delete",
    "handle_prune_apply",
    "handle_prune_plan",
    "handle_records_delete",
    "handle_records_prune_apply",
    "handle_records_prune_plan",
]
