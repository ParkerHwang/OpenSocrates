"""In-memory host capability contract for the v2 desktop connection matrix.

The matrix addresses ChatGPT desktop Chat, Work, and Codex and Claude desktop
Chat, Cowork, and Code on macOS and Windows, including an unknown, local, or
cloud execution location. Claude account experience is a separate axis. Cells
do not inherit one another's verdicts.

Every capability starts ``unknown``. ``unsupported`` is a separate status and
is used only for a cited route constraint or a caller-supplied evidence record.
Nothing in this module observes a live app, selects a model, or marks a real
host supported. Declared cells are addresses, not installation evidence.

The module does not control an app, call a model-provider API, read or write
credentials, change process environment, store prompts, transcripts, workspace
contents, or hidden reasoning, or open ``claude://`` links.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

_SOURCE_REF = re.compile(r"[a-z0-9][a-z0-9._:-]{0,127}")
_VERSION_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,63}")
_EXCLUDED_SOURCE_MARKERS = ("claude://", "canonical_search_probe")


class DesktopApp(StrEnum):
    """Desktop applications in the initial v2 connection scope."""

    CHATGPT = "chatgpt_desktop"
    CLAUDE = "claude_desktop"


class HostOperatingSystem(StrEnum):
    """Operating systems in the initial v2 connection scope."""

    MACOS = "macos"
    WINDOWS = "windows"


class ChatGptMode(StrEnum):
    """ChatGPT desktop product surfaces. Same-app modes are not one capability."""

    CHAT = "chatgpt.chat"
    WORK = "chatgpt.work"
    CODEX = "chatgpt.codex"


class ClaudeMode(StrEnum):
    """Claude desktop product surfaces. Same-app modes are not one capability."""

    CHAT = "claude.chat"
    COWORK = "claude.cowork"
    CODE = "claude.code"


class ExecutionLocation(StrEnum):
    """Where host work executes. Unknown is not a third confirmed location."""

    UNKNOWN = "unknown"
    LOCAL = "local"
    CLOUD = "cloud"


class AccountExperience(StrEnum):
    """Claude account experience. Unified does not equate surface capabilities."""

    UNSPECIFIED = "unspecified"
    UNIFIED = "unified"


class AppOsCell(StrEnum):
    """The four app/OS cells. A result on one does not pass another."""

    CHATGPT_MACOS = "chatgpt_macos"
    CHATGPT_WINDOWS = "chatgpt_windows"
    CLAUDE_MACOS = "claude_macos"
    CLAUDE_WINDOWS = "claude_windows"


class HostCapability(StrEnum):
    """Connection operations tracked separately for one exact endpoint cell."""

    SESSION_CREATION = "session_creation"
    MESSAGE_DELIVERY = "message_delivery"
    AUTOMATIC_SEND = "automatic_send"
    IN_FLIGHT_UPDATE = "in_flight_update"
    READ_CONFIRMATION = "read_confirmation"
    RESPONSE_CONFIRMATION = "response_confirmation"
    TURN_RESUME = "turn_resume"
    USER_INTERRUPT = "user_interrupt"
    MODEL_SELECTION = "model_selection"
    MODEL_VISIBILITY = "model_visibility"
    INPUT_LIMIT = "input_limit"
    DESTINATION_BINDING = "destination_binding"
    RETURN_PATH = "return_path"
    LOCAL_SERVICE_CONNECTION = "local_service_connection"
    DELIVERY_CANCEL = "delivery_cancel"


class ConnectionRoute(StrEnum):
    """How a capability would be exercised. Routes do not share a verdict."""

    UNSPECIFIED = "unspecified"
    DESKTOP_COMMAND_PREFILL = "desktop_command_prefill"
    CLAUDE_DESKTOP_DEEPLINK = "claude_desktop_deeplink"
    CHATGPT_COMPUTER_USE_SELF = "chatgpt_computer_use_self"
    COMPUTER_USE = "computer_use"
    HOST_CONNECTOR = "host_connector"
    SCREEN_CONTROL = "screen_control"
    STRUCTURED_CHANNEL = "structured_channel"
    CURRENT_SESSION_TOOL = "current_session_tool"
    HOST_SCHEDULER = "host_scheduler"
    PROVIDER_API_AGENT = "provider_api_agent"


class SupportStatus(StrEnum):
    """Capability support. Missing evidence stays unknown, not unsupported."""

    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"
    SUPPORTED = "supported"


class EvidenceKind(StrEnum):
    """Why a verdict exists. A design citation is not a live host probe."""

    DESIGN_DOCUMENT = "design_document"
    LIVE_STRUCTURED = "live_structured"
    LIVE_SCREEN = "live_screen"


class UnsupportedBasis(StrEnum):
    """Why a verdict is unsupported. Unknown verdicts use ``none``."""

    NONE = "none"
    NOT_ACCEPTED_ROUTE = "not_accepted_route"
    DOCUMENTED_NON_BEHAVIOR = "documented_non_behavior"
    RECORDED_EVIDENCE = "recorded_evidence"


class DeliveryStage(StrEnum):
    """Named deeplink progress labels. A label alone confirms no capability."""

    LINK_REQUESTED = "link_requested"
    SCREEN_OPENED = "screen_opened"
    COMPOSER_PREFILLED = "composer_prefilled"
    SEND_ATTEMPTED = "send_attempted"
    SESSION_OBSERVED = "session_observed"
    RESULT_RETURNED = "result_returned"
    READ_CONFIRMED = "read_confirmed"


class ExternalEffect(StrEnum):
    """What is known about an effect outside this process."""

    NOT_ATTEMPTED = "not_attempted"
    EFFECT_UNKNOWN = "effect_unknown"
    CONFIRMED_FAILURE = "confirmed_failure"
    OBSERVED = "observed"


class HostCapabilityContractError(ValueError):
    """Raised when a value would collapse unknown, unsupported, or cell scope."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CapabilityEvidence:
    """Bounded citation. It has no prompt, transcript, path, or credential."""

    kind: EvidenceKind
    source_ref: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, EvidenceKind):
            raise HostCapabilityContractError("evidence_kind_invalid")
        if not isinstance(self.source_ref, str) or _SOURCE_REF.fullmatch(self.source_ref) is None:
            raise HostCapabilityContractError("source_ref_rejected")
        lowered = self.source_ref.lower()
        if any(marker in lowered for marker in _EXCLUDED_SOURCE_MARKERS):
            raise HostCapabilityContractError("excluded_probe_source")


@dataclass(frozen=True, slots=True)
class HostEndpoint:
    """One app, OS, mode, location, account experience, and optional version.

    Constructing an endpoint does not assert that the app is installed, that
    the location was observed, or that any capability is supported. An omitted
    version matches only other omitted versions.
    """

    app: DesktopApp
    operating_system: HostOperatingSystem
    execution_location: ExecutionLocation = ExecutionLocation.UNKNOWN
    chatgpt_mode: ChatGptMode | None = None
    claude_mode: ClaudeMode | None = None
    account_experience: AccountExperience = AccountExperience.UNSPECIFIED
    app_version: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.app, DesktopApp):
            raise HostCapabilityContractError("endpoint_field_invalid")
        if not isinstance(self.operating_system, HostOperatingSystem):
            raise HostCapabilityContractError("endpoint_field_invalid")
        if not isinstance(self.execution_location, ExecutionLocation):
            raise HostCapabilityContractError("endpoint_field_invalid")
        if not isinstance(self.account_experience, AccountExperience):
            raise HostCapabilityContractError("endpoint_field_invalid")
        if self.app is DesktopApp.CHATGPT:
            if not isinstance(self.chatgpt_mode, ChatGptMode) or self.claude_mode is not None:
                raise HostCapabilityContractError("endpoint_mode_mismatch")
            if self.account_experience is not AccountExperience.UNSPECIFIED:
                raise HostCapabilityContractError("account_experience_not_on_claude")
        elif self.app is DesktopApp.CLAUDE:
            if not isinstance(self.claude_mode, ClaudeMode) or self.chatgpt_mode is not None:
                raise HostCapabilityContractError("endpoint_mode_mismatch")
        if self.app_version is not None and _VERSION_TOKEN.fullmatch(self.app_version) is None:
            raise HostCapabilityContractError("version_token_invalid")

    @property
    def app_os_cell(self) -> AppOsCell:
        cells = {
            (DesktopApp.CHATGPT, HostOperatingSystem.MACOS): AppOsCell.CHATGPT_MACOS,
            (DesktopApp.CHATGPT, HostOperatingSystem.WINDOWS): AppOsCell.CHATGPT_WINDOWS,
            (DesktopApp.CLAUDE, HostOperatingSystem.MACOS): AppOsCell.CLAUDE_MACOS,
            (DesktopApp.CLAUDE, HostOperatingSystem.WINDOWS): AppOsCell.CLAUDE_WINDOWS,
        }
        return cells[self.app, self.operating_system]


@dataclass(frozen=True, slots=True)
class CapabilityVerdict:
    """Support for one capability on one endpoint, optionally via one route."""

    endpoint: HostEndpoint
    capability: HostCapability
    status: SupportStatus
    route: ConnectionRoute = ConnectionRoute.UNSPECIFIED
    evidence: CapabilityEvidence | None = None
    unsupported_basis: UnsupportedBasis = UnsupportedBasis.NONE
    from_route_constraint: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.endpoint, HostEndpoint):
            raise HostCapabilityContractError("endpoint_required")
        if not isinstance(self.capability, HostCapability):
            raise HostCapabilityContractError("capability_invalid")
        if not isinstance(self.status, SupportStatus):
            raise HostCapabilityContractError("status_invalid")
        if not isinstance(self.route, ConnectionRoute):
            raise HostCapabilityContractError("route_invalid")
        if not isinstance(self.unsupported_basis, UnsupportedBasis):
            raise HostCapabilityContractError("basis_invalid")
        if self.evidence is not None and not isinstance(self.evidence, CapabilityEvidence):
            raise HostCapabilityContractError("evidence_kind_invalid")
        if self.status is SupportStatus.UNKNOWN:
            if self.unsupported_basis is not UnsupportedBasis.NONE or self.from_route_constraint:
                raise HostCapabilityContractError("unknown_has_no_negative_basis")
            if self.evidence is not None and self.evidence.kind is EvidenceKind.DESIGN_DOCUMENT:
                raise HostCapabilityContractError("design_document_cannot_fill_unknown")
        elif self.status is SupportStatus.UNSUPPORTED:
            if self.evidence is None:
                raise HostCapabilityContractError("evidence_required")
            if self.unsupported_basis is UnsupportedBasis.NONE:
                raise HostCapabilityContractError("unsupported_basis_required")
            if self.evidence.kind is EvidenceKind.LIVE_SCREEN:
                raise HostCapabilityContractError("screen_evidence_cannot_change_support")
        elif self.status is SupportStatus.SUPPORTED:
            if (
                self.evidence is None
                or self.evidence.kind is not EvidenceKind.LIVE_STRUCTURED
                or self.from_route_constraint
                or self.unsupported_basis is not UnsupportedBasis.NONE
            ):
                raise HostCapabilityContractError("live_evidence_required_for_support")


@dataclass(frozen=True, slots=True)
class RouteConstraint:
    """A design-document limit that applies only when that route is asked.

    ``capability is None`` means every capability on that route. The endpoint's
    own capability status, read without a route, stays unknown.
    """

    constraint_id: str
    apps: frozenset[DesktopApp]
    operating_systems: frozenset[HostOperatingSystem]
    route: ConnectionRoute
    route_status: SupportStatus
    basis: UnsupportedBasis
    evidence: CapabilityEvidence
    capability: HostCapability | None = None
    chatgpt_modes: frozenset[ChatGptMode] | None = None
    claude_modes: frozenset[ClaudeMode] | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.constraint_id, str)
            or _SOURCE_REF.fullmatch(self.constraint_id) is None
        ):
            raise HostCapabilityContractError("constraint_id_invalid")
        if self.route is ConnectionRoute.UNSPECIFIED:
            raise HostCapabilityContractError("route_constraint_not_capability_status")
        if self.route_status is not SupportStatus.UNSUPPORTED:
            raise HostCapabilityContractError("route_constraint_not_capability_status")
        if self.basis not in {
            UnsupportedBasis.NOT_ACCEPTED_ROUTE,
            UnsupportedBasis.DOCUMENTED_NON_BEHAVIOR,
        }:
            raise HostCapabilityContractError("basis_invalid")
        if self.evidence.kind is not EvidenceKind.DESIGN_DOCUMENT:
            raise HostCapabilityContractError("route_constraint_not_capability_status")
        if not self.apps or not self.operating_systems:
            raise HostCapabilityContractError("constraint_scope_empty")


@dataclass(frozen=True, slots=True)
class DocumentedNonGuarantee:
    """A cited statement that must not be read as support or global absence."""

    note_id: str
    route: ConnectionRoute | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.note_id, str) or _SOURCE_REF.fullmatch(self.note_id) is None:
            raise HostCapabilityContractError("constraint_id_invalid")
        if self.route is not None and not isinstance(self.route, ConnectionRoute):
            raise HostCapabilityContractError("route_invalid")

    @property
    def changes_support_status(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class CitedPrefillCeiling:
    """A documented composer-prefill figure. It is not an effective input limit."""

    route: ConnectionRoute
    app: DesktopApp
    cited_characters: int
    binds_effective_input_limit: bool = False

    def __post_init__(self) -> None:
        if self.binds_effective_input_limit or self.cited_characters != 14000:
            raise HostCapabilityContractError("prefill_ceiling_is_not_input_limit")
        if (
            self.app is not DesktopApp.CLAUDE
            or self.route is not ConnectionRoute.CLAUDE_DESKTOP_DEEPLINK
        ):
            raise HostCapabilityContractError("prefill_ceiling_is_not_input_limit")


def _constraint(
    constraint_id: str,
    *,
    apps: frozenset[DesktopApp],
    route: ConnectionRoute,
    basis: UnsupportedBasis,
    source_ref: str,
    capability: HostCapability | None = None,
    chatgpt_modes: frozenset[ChatGptMode] | None = None,
    claude_modes: frozenset[ClaudeMode] | None = None,
) -> RouteConstraint:
    return RouteConstraint(
        constraint_id=constraint_id,
        apps=apps,
        operating_systems=frozenset(HostOperatingSystem),
        route=route,
        route_status=SupportStatus.UNSUPPORTED,
        basis=basis,
        evidence=CapabilityEvidence(EvidenceKind.DESIGN_DOCUMENT, source_ref),
        capability=capability,
        chatgpt_modes=chatgpt_modes,
        claude_modes=claude_modes,
    )


def _build_route_constraints() -> tuple[RouteConstraint, ...]:
    """Route limits cited from the v2 system design. They are not live probes."""

    chatgpt = frozenset({DesktopApp.CHATGPT})
    claude = frozenset({DesktopApp.CLAUDE})
    both = frozenset(DesktopApp)
    chatgpt_modes = frozenset(ChatGptMode)
    claude_modes = frozenset(ClaudeMode)
    command = _constraint(
        "chatgpt-command-no-autosend",
        apps=chatgpt,
        route=ConnectionRoute.DESKTOP_COMMAND_PREFILL,
        capability=HostCapability.AUTOMATIC_SEND,
        basis=UnsupportedBasis.DOCUMENTED_NON_BEHAVIOR,
        source_ref="design:system-2.0:chatgpt-command-no-autosend",
        chatgpt_modes=chatgpt_modes,
    )
    deeplink = _constraint(
        "claude-deeplink-prefill-not-autosend",
        apps=claude,
        route=ConnectionRoute.CLAUDE_DESKTOP_DEEPLINK,
        capability=HostCapability.AUTOMATIC_SEND,
        basis=UnsupportedBasis.DOCUMENTED_NON_BEHAVIOR,
        source_ref="design:system-2.0:claude-deeplink-prefill-not-autosend",
        claude_modes=claude_modes,
    )
    self_drive = tuple(
        _constraint(
            f"chatgpt-computer-use-self-not-accepted:{capability.value}",
            apps=chatgpt,
            route=ConnectionRoute.CHATGPT_COMPUTER_USE_SELF,
            capability=capability,
            basis=UnsupportedBasis.NOT_ACCEPTED_ROUTE,
            source_ref="design:system-2.0:chatgpt-computer-use-cannot-drive-self",
            chatgpt_modes=chatgpt_modes,
        )
        for capability in (
            HostCapability.SESSION_CREATION,
            HostCapability.MESSAGE_DELIVERY,
            HostCapability.AUTOMATIC_SEND,
        )
    )
    provider = _constraint(
        "provider-api-agent-not-accepted",
        apps=both,
        route=ConnectionRoute.PROVIDER_API_AGENT,
        basis=UnsupportedBasis.NOT_ACCEPTED_ROUTE,
        source_ref="design:system-2.0:provider-api-agent-excluded",
        chatgpt_modes=chatgpt_modes,
        claude_modes=claude_modes,
    )
    return (command, deeplink, *self_drive, provider)


def _build_non_guarantees() -> tuple[DocumentedNonGuarantee, ...]:
    note_ids = (
        "claude-computer-use-does-not-establish-session-control",
        "connector-registration-does-not-establish-delivery",
        "screen-action-does-not-establish-receipt",
        "macos-computer-use-background-not-guaranteed",
        "windows-computer-use-foreground-not-guaranteed",
        "cowork-cloud-continuation-does-not-connect-local-db",
        "remote-connector-does-not-connect-local-service",
        "blocked-claude-url-attempt-does-not-establish-unsupported",
        "cited-deeplink-ceiling-is-not-effective-input-limit",
        "one-app-os-cell-does-not-pass-another",
        "mcp-specification-does-not-prove-in-flight-update",
    )
    return tuple(DocumentedNonGuarantee(note_id) for note_id in note_ids)


_ROUTE_CONSTRAINTS = _build_route_constraints()
_NON_GUARANTEES = _build_non_guarantees()
_CLAUDE_PREFILL_CEILING = CitedPrefillCeiling(
    route=ConnectionRoute.CLAUDE_DESKTOP_DEEPLINK,
    app=DesktopApp.CLAUDE,
    cited_characters=14000,
)


def declared_endpoints() -> tuple[HostEndpoint, ...]:
    """Return every addressed cell. Each capability on each cell starts unknown."""

    endpoints: list[HostEndpoint] = []
    for operating_system in HostOperatingSystem:
        for mode in ChatGptMode:
            for location in ExecutionLocation:
                endpoints.append(
                    HostEndpoint(
                        app=DesktopApp.CHATGPT,
                        operating_system=operating_system,
                        execution_location=location,
                        chatgpt_mode=mode,
                    )
                )
        for mode in ClaudeMode:
            for location in ExecutionLocation:
                for experience in AccountExperience:
                    endpoints.append(
                        HostEndpoint(
                            app=DesktopApp.CLAUDE,
                            operating_system=operating_system,
                            execution_location=location,
                            claude_mode=mode,
                            account_experience=experience,
                        )
                    )
    return tuple(endpoints)


def documented_route_constraints() -> tuple[RouteConstraint, ...]:
    """Return route-scoped design limits. None of them marks a cell supported."""

    return _ROUTE_CONSTRAINTS


def documented_non_guarantees() -> tuple[DocumentedNonGuarantee, ...]:
    """Return citations that leave the related capability unknown."""

    return _NON_GUARANTEES


def cited_composer_prefill_ceiling(route: ConnectionRoute) -> CitedPrefillCeiling | None:
    """Return the cited Claude deeplink prefill figure without binding a limit."""

    if route is ConnectionRoute.CLAUDE_DESKTOP_DEEPLINK:
        return _CLAUDE_PREFILL_CEILING
    return None


def effective_input_limit(endpoint: HostEndpoint) -> None:
    """No declared or caller-described endpoint has a confirmed numeric limit."""

    if not isinstance(endpoint, HostEndpoint):
        raise HostCapabilityContractError("endpoint_required")
    return None


def passes_other_app_os_cells(cell: AppOsCell) -> tuple[AppOsCell, ...]:
    """An app/OS cell does not pass any other app/OS cell."""

    if not isinstance(cell, AppOsCell):
        raise HostCapabilityContractError("endpoint_field_invalid")
    return ()


def support_transfers(source: HostEndpoint, target: HostEndpoint) -> bool:
    """Capability support never moves from one endpoint value to another."""

    if not isinstance(source, HostEndpoint) or not isinstance(target, HostEndpoint):
        raise HostCapabilityContractError("endpoint_required")
    return False


def status_established_by_stage(stage: DeliveryStage) -> SupportStatus:
    """A delivery-stage name does not establish support, failure, or absence."""

    if not isinstance(stage, DeliveryStage):
        raise HostCapabilityContractError("stage_invalid")
    return SupportStatus.UNKNOWN


def classify_send_attempt(*, attempted: bool, effect_observed: bool) -> ExternalEffect:
    """Separate an unobserved send effect from both success and confirmed failure."""

    if not isinstance(attempted, bool) or not isinstance(effect_observed, bool):
        raise HostCapabilityContractError("effect_flag_invalid")
    if not attempted:
        return ExternalEffect.NOT_ATTEMPTED
    if effect_observed:
        return ExternalEffect.OBSERVED
    return ExternalEffect.EFFECT_UNKNOWN


def _constraint_matches(
    constraint: RouteConstraint,
    endpoint: HostEndpoint,
    capability: HostCapability,
    route: ConnectionRoute,
) -> bool:
    if constraint.route is not route or endpoint.app not in constraint.apps:
        return False
    if endpoint.operating_system not in constraint.operating_systems:
        return False
    if constraint.capability is not None and constraint.capability is not capability:
        return False
    if endpoint.app is DesktopApp.CHATGPT:
        modes = constraint.chatgpt_modes
        return modes is None or endpoint.chatgpt_mode in modes
    modes = constraint.claude_modes
    return modes is None or endpoint.claude_mode in modes


def matching_route_constraint(
    endpoint: HostEndpoint,
    capability: HostCapability,
    route: ConnectionRoute,
) -> RouteConstraint | None:
    """Return the design constraint for this route, if the route is in scope."""

    if route is ConnectionRoute.UNSPECIFIED:
        return None
    for constraint in _ROUTE_CONSTRAINTS:
        if _constraint_matches(constraint, endpoint, capability, route):
            return constraint
    return None


def baseline_verdict(
    endpoint: HostEndpoint,
    capability: HostCapability,
    route: ConnectionRoute = ConnectionRoute.UNSPECIFIED,
) -> CapabilityVerdict:
    """Resolve a cell before any caller record. The no-evidence result is unknown."""

    if not isinstance(endpoint, HostEndpoint):
        raise HostCapabilityContractError("endpoint_required")
    if not isinstance(capability, HostCapability):
        raise HostCapabilityContractError("capability_invalid")
    if not isinstance(route, ConnectionRoute):
        raise HostCapabilityContractError("route_invalid")
    constraint = matching_route_constraint(endpoint, capability, route)
    if constraint is None:
        return CapabilityVerdict(endpoint=endpoint, capability=capability, route=route)
    return CapabilityVerdict(
        endpoint=endpoint,
        capability=capability,
        route=route,
        status=SupportStatus.UNSUPPORTED,
        evidence=constraint.evidence,
        unsupported_basis=constraint.basis,
        from_route_constraint=True,
    )


class HostCapabilityView(Protocol):
    """Read surface for a later adapter. Implementations must not perform I/O."""

    def capability_status(
        self, endpoint: HostEndpoint, capability: HostCapability
    ) -> SupportStatus: ...

    def route_status(
        self,
        endpoint: HostEndpoint,
        capability: HostCapability,
        route: ConnectionRoute,
    ) -> SupportStatus: ...


class HostCapabilityLedger:
    """Process-local records. Writing a verdict does not contact a host."""

    def __init__(self) -> None:
        self._records: dict[
            tuple[HostEndpoint, HostCapability, ConnectionRoute], CapabilityVerdict
        ] = {}

    def record(
        self,
        endpoint: HostEndpoint,
        capability: HostCapability,
        status: SupportStatus,
        *,
        route: ConnectionRoute = ConnectionRoute.UNSPECIFIED,
        evidence: CapabilityEvidence | None = None,
    ) -> CapabilityVerdict:
        """Store one exact-cell verdict.

        Supported requires caller-supplied live structured evidence. This
        ledger does not create that evidence or check that a host produced it.
        Design citations stay in the route catalog and cannot be recorded as a
        new supported or unsupported verdict. Screen evidence cannot move a
        status to supported or unsupported. Model non-exposure stays unknown.
        A catalog route cannot be overwritten as supported.
        """

        if not isinstance(evidence, CapabilityEvidence) and evidence is not None:
            raise HostCapabilityContractError("evidence_kind_invalid")
        if status is SupportStatus.UNKNOWN:
            basis = UnsupportedBasis.NONE
            if evidence is not None and evidence.kind not in {
                EvidenceKind.LIVE_STRUCTURED,
                EvidenceKind.LIVE_SCREEN,
            }:
                raise HostCapabilityContractError("design_document_cannot_fill_unknown")
        elif status is SupportStatus.UNSUPPORTED:
            if capability is HostCapability.MODEL_VISIBILITY:
                raise HostCapabilityContractError("non_exposure_is_unknown")
            if evidence is None:
                raise HostCapabilityContractError("evidence_required")
            if evidence.kind is EvidenceKind.LIVE_SCREEN:
                raise HostCapabilityContractError("screen_evidence_cannot_change_support")
            if evidence.kind is not EvidenceKind.LIVE_STRUCTURED:
                raise HostCapabilityContractError("design_document_cannot_mark_capability")
            basis = UnsupportedBasis.RECORDED_EVIDENCE
        elif status is SupportStatus.SUPPORTED:
            if evidence is None or evidence.kind is not EvidenceKind.LIVE_STRUCTURED:
                raise HostCapabilityContractError("live_evidence_required_for_support")
            if matching_route_constraint(endpoint, capability, route) is not None:
                raise HostCapabilityContractError("route_not_accepted")
            basis = UnsupportedBasis.NONE
        else:
            raise HostCapabilityContractError("status_invalid")
        verdict = CapabilityVerdict(
            endpoint=endpoint,
            capability=capability,
            route=route,
            status=status,
            evidence=evidence,
            unsupported_basis=basis,
        )
        self._records[(endpoint, capability, route)] = verdict
        return verdict

    def recorded_verdict(
        self,
        endpoint: HostEndpoint,
        capability: HostCapability,
        route: ConnectionRoute = ConnectionRoute.UNSPECIFIED,
    ) -> CapabilityVerdict | None:
        """Return only a verdict stored by ``record``, without catalog synthesis."""

        return self._records.get((endpoint, capability, route))

    def promote(
        self,
        source: HostEndpoint,
        target: HostEndpoint,
        capability: HostCapability,
    ) -> CapabilityVerdict:
        """Reject copying a verdict across cells, including a cell onto itself."""

        if not isinstance(source, HostEndpoint) or not isinstance(target, HostEndpoint):
            raise HostCapabilityContractError("endpoint_required")
        if not isinstance(capability, HostCapability):
            raise HostCapabilityContractError("capability_invalid")
        raise HostCapabilityContractError("cross_cell_promotion_rejected")

    def verdict(
        self,
        endpoint: HostEndpoint,
        capability: HostCapability,
        route: ConnectionRoute = ConnectionRoute.UNSPECIFIED,
    ) -> CapabilityVerdict:
        """Resolve catalog route limits first, then an exact record, else unknown."""

        catalog = baseline_verdict(endpoint, capability, route)
        if catalog.from_route_constraint:
            return catalog
        recorded = self.recorded_verdict(endpoint, capability, route)
        if recorded is not None:
            return recorded
        return catalog

    def capability_status(
        self, endpoint: HostEndpoint, capability: HostCapability
    ) -> SupportStatus:
        """Status of the capability itself. A route limit does not change it."""

        return self.verdict(endpoint, capability, ConnectionRoute.UNSPECIFIED).status

    def route_status(
        self,
        endpoint: HostEndpoint,
        capability: HostCapability,
        route: ConnectionRoute,
    ) -> SupportStatus:
        """Status of one route. ``unspecified`` asks for the capability status."""

        if route is ConnectionRoute.UNSPECIFIED:
            return self.capability_status(endpoint, capability)
        return self.verdict(endpoint, capability, route).status

    def statuses(
        self, endpoint: HostEndpoint
    ) -> Mapping[HostCapability, SupportStatus]:
        """Routeless status of every capability. Missing records stay unknown."""

        return {
            capability: self.capability_status(endpoint, capability)
            for capability in HostCapability
        }

    def iter_baseline(self) -> Iterator[CapabilityVerdict]:
        """Yield the routeless unknown verdict for every declared cell and capability."""

        for endpoint in declared_endpoints():
            for capability in HostCapability:
                yield baseline_verdict(endpoint, capability)


__all__ = [
    "AccountExperience",
    "AppOsCell",
    "CapabilityEvidence",
    "CapabilityVerdict",
    "ChatGptMode",
    "CitedPrefillCeiling",
    "ClaudeMode",
    "ConnectionRoute",
    "DeliveryStage",
    "DesktopApp",
    "DocumentedNonGuarantee",
    "EvidenceKind",
    "ExecutionLocation",
    "ExternalEffect",
    "HostCapability",
    "HostCapabilityContractError",
    "HostCapabilityLedger",
    "HostCapabilityView",
    "HostEndpoint",
    "HostOperatingSystem",
    "RouteConstraint",
    "SupportStatus",
    "UnsupportedBasis",
    "baseline_verdict",
    "cited_composer_prefill_ceiling",
    "classify_send_attempt",
    "declared_endpoints",
    "documented_non_guarantees",
    "documented_route_constraints",
    "effective_input_limit",
    "matching_route_constraint",
    "passes_other_app_os_cells",
    "status_established_by_stage",
    "support_transfers",
]
