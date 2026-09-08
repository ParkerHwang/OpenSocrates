"""Content-only in-turn CLI: no authentication, network, hooks, or disk state."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TextIO

from ..content.injection import ProjectionInstructionAssembler
from ..content.loader import load_compiled_bundle, load_reasoning_content_projections
from ..rendering.response_policy import load_compiled_response_policy
from ..selector.decision import DecisionSession

# Closed feature envelopes are small; this is an input memory bound, not a reasoning budget.
MAX_REQUEST_CHARS = 16384


def run_decision(stdin: TextIO, stdout: TextIO, *, stream: bool = False) -> int:
    try:
        # A missing installed pair must not fall back to workspace-controlled content.
        frozen = getattr(sys, "_MEIPASS", None)
        root = Path(frozen) if isinstance(frozen, str) else Path(__file__).resolve().parents[3]
        bundle = load_compiled_bundle(root / "content/compiled-content.bundle.json")
        projections = load_reasoning_content_projections(
            root / "content/compiled-reasoning-content.bundle.json"
        )
        if bundle.content_revision != projections.content_revision:
            raise ValueError
        session = DecisionSession(
            bundle,
            ProjectionInstructionAssembler(projections),
            response_policy=load_compiled_response_policy(
                root / "content/compiled-response-policy.json"
            ),
        )
    except Exception:
        stdout.write(json.dumps(DecisionSession._failure("canonical_content_unavailable")) + "\n")
        return 0
    while True:
        payload = (
            stdin.readline(MAX_REQUEST_CHARS + 1) if stream else stdin.read(MAX_REQUEST_CHARS + 1)
        )
        if not payload:
            return 0
        if len(payload) > MAX_REQUEST_CHARS:
            stdout.write(json.dumps(session._failure("request_too_large")) + "\n")
            stdout.flush()
            return 0
        try:
            request = json.loads(payload)
            response = session.handle(request)
        except Exception:
            response = session._failure("decision_unavailable")
        stdout.write(json.dumps(response, ensure_ascii=False, sort_keys=True) + "\n")
        stdout.flush()
        if not stream:
            return 0
