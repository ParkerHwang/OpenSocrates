#!/usr/bin/env python3
"""Build deterministic bilingual prompt outputs from a compiled JSON bundle.

This focused build tool deliberately imports no YAML parser and never reads the
authoring tree.  It loads one validated ``compiled-content.bundle.json`` and
compiles representative English/Korean start, tool-observation, and Stop-repair
contexts into a caller-supplied directory.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opensocrates.content.loader import load_compiled_bundle
from opensocrates.domain.enums import (
    AnswerShape,
    Participation,
    ParticipationReasonCode,
    Rigor,
    RiskFloorReason,
    RouterReasonCode,
    TaskState,
)
from opensocrates.domain.models import RouterDecision
from opensocrates.domain.participation import build_participation_decision
from opensocrates.domain.rigor import build_rigor_decision
from opensocrates.prompting.compiler import (
    PromptCompiler,
    PromptCompileRequest,
    PromptEvent,
)


def _canonical_json(value: Any) -> bytes:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return (encoded + "\n").encode("utf-8")


def _method_route(bundle: Any, primary_id: str, secondary_id: str | None) -> RouterDecision:
    methods = {method.id: method for method in bundle.methods}
    primary = methods.get(primary_id)
    if primary is None:
        raise ValueError(f"primary method is not in the bundle: {primary_id}")
    if secondary_id is not None and secondary_id not in methods:
        raise ValueError(f"secondary method is not in the bundle: {secondary_id}")
    if secondary_id == primary_id:
        raise ValueError("primary and secondary methods must differ")
    shapes = primary.participation.get("allowed_answer_shapes", ())
    if not isinstance(shapes, (list, tuple)) or not shapes:
        raise ValueError(f"primary method has no answer shape: {primary_id}")
    answer_shape = AnswerShape(shapes[0])
    secondary = methods.get(secondary_id) if secondary_id is not None else None
    return RouterDecision(
        answer_shape=answer_shape,
        primary_family=primary.family,
        secondary_family=secondary.family if secondary else None,
        primary_method=primary.id,
        secondary_method=secondary.id if secondary else None,
        explicit_invocation=False,
        reason_code=(
            RouterReasonCode.WEIGHTED_PRIMARY_WITH_COMPLEMENT
            if secondary
            else RouterReasonCode.WEIGHTED_PRIMARY
        ),
        prompt_bundle_hash=bundle.normalized_semantic_hash,
    )


def _representative_request(
    bundle: Any,
    locale: str,
    event: PromptEvent,
    route: RouterDecision,
) -> PromptCompileRequest:
    participation = build_participation_decision(
        Participation.JUDGMENT,
        ParticipationReasonCode.JUDGMENT_CHOICE,
        judgment_targets=("representative judgment",),
    )
    rigor = build_rigor_decision(
        Rigor.TOGETHER,
        None,
        Rigor.TOGETHER,
        RiskFloorReason.ORDINARY_JUDGMENT,
    )
    return PromptCompileRequest(
        bundle=bundle,
        locale=locale,
        event=event,
        participation=participation,
        rigor=rigor,
        route=route,
        phase=TaskState.FRAMING,
        expected_content_revision=bundle.content_revision,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bundle",
        type=Path,
        required=True,
        help="validated compiled JSON content bundle",
    )
    parser.add_argument(
        "--output-dir",
        "--output",
        dest="output_dir",
        type=Path,
        required=True,
        help="caller-supplied generated-output directory",
    )
    parser.add_argument("--primary-method", default="critical-thinking")
    parser.add_argument("--secondary-method", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        bundle = load_compiled_bundle(args.bundle.resolve())
        methods = {method.id: method for method in bundle.methods}
        secondary_id = args.secondary_method
        if secondary_id is None:
            primary = methods.get(args.primary_method)
            if primary is None:
                raise ValueError(f"primary method is not in the bundle: {args.primary_method}")
            preferred = primary.complements.get("preferred", ())
            if isinstance(preferred, str):
                secondary_id = preferred
            elif isinstance(preferred, (list, tuple)) and preferred:
                secondary_id = preferred[0]
        route = _method_route(bundle, args.primary_method, secondary_id)
        compiler = PromptCompiler(bundle)
        output_dir = args.output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        manifest_outputs: list[dict[str, Any]] = []
        event_files = (
            (PromptEvent.START, "start.md"),
            (PromptEvent.TOOL_OBSERVATION, "tool-observation.md"),
            (PromptEvent.STOP_REPAIR, "stop-repair.md"),
        )
        for locale in ("en", "ko"):
            locale_dir = output_dir / locale
            locale_dir.mkdir(parents=True, exist_ok=True)
            for event, filename in event_files:
                result = compiler.compile(_representative_request(bundle, locale, event, route))
                path = locale_dir / filename
                path.write_bytes(result.text.encode("utf-8"))
                manifest_outputs.append(
                    {
                        "path": path.relative_to(output_dir).as_posix(),
                        "locale": locale,
                        "event": event.value,
                        "compiled_prompt_bundle_hash": result.compiled_prompt_bundle_hash,
                        "estimated_tokens": result.estimated_tokens,
                        "context_bytes": result.context_bytes,
                        "fragments": [
                            {
                                "id": fragment.id,
                                "locale": fragment.locale,
                                "version": fragment.version,
                            }
                            for fragment in result.fragments
                        ],
                    }
                )

        manifest = {
            "schema": "opensocrates.compiled-prompt-manifest/1.0.0",
            "content_revision": bundle.content_revision,
            "normalized_semantic_hash": bundle.normalized_semantic_hash,
            "outputs": manifest_outputs,
        }
        (output_dir / "manifest.json").write_bytes(_canonical_json(manifest))
        print(
            f"PROMPTS_OK locales=2 events=3 output={output_dir} "
            f"content_revision={bundle.content_revision}"
        )
        return 0
    except Exception as exc:  # focused CLI boundary: concise nonzero failure
        print(f"PROMPTS_INVALID {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
