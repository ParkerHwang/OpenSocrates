"""Pinned, content-only desktop host preparation; never changes account settings."""

from __future__ import annotations

import hashlib
import io
import json
import os
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

CONTENT_VERSION = "1.5.3"
PAYLOADS = {
    "claude_cowork": (
        "opensocrates-1.5.3-claude-chat-skills.zip",
        "ee0163505a39251acb15b6db4eaddbc98845ad28b7354de220466110e84a7fd5",
    ),
    "antigravity": (
        "opensocrates-1.5.3-antigravity-plugin.zip",
        "4f8252b186044741134d722f5e15f3dd338ad0b22945dd13b2e91d12a3fc96ce",
    ),
}
MAX_ARCHIVE_BYTES = 8 * 1024 * 1024
MAX_EXPANDED_BYTES = 32 * 1024 * 1024
MAX_MEMBERS = 2000


def _regular_file(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISREG(info.st_mode) and not bool(getattr(info, "st_file_attributes", 0) & 0x400)


def payload_bytes(payloads: Path, host: str) -> bytes:
    """Verify a pinned archive independently of a mutable payload manifest."""
    name, expected = PAYLOADS[host]
    path = payloads / name
    for ancestor in (payloads, *payloads.parents):
        info = ancestor.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("payload_unavailable")
    if not _regular_file(path) or path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("payload_unavailable")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("payload_identity_mismatch")
    return raw


def _unsafe_part(part: str) -> bool:
    reserved = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
    return (
        part in ("", ".", "..")
        or any(character in part for character in ':<>"|?*\x00')
        or part.endswith((" ", "."))
        or part.split(".")[0].upper() in reserved
        or len(part.encode("utf-8")) > 240
    )


def _release_metadata(raw: bytes) -> None:
    value = json.loads(raw.decode("utf-8"))
    expected = {
        "schema": "opensocrates.content-host-manifest/1.0.0",
        "host": "antigravity",
        "product_version": CONTENT_VERSION,
        "source_tree_hash": "sha256:a4d9f4b70f653dee12a3ea758ef10dc391443a19536c7e7f22082962fd252e0f",
    }
    if not isinstance(value, dict) or any(value.get(key) != item for key, item in expected.items()):
        raise ValueError("payload_release_metadata")


def _member_target(member: zipfile.ZipInfo, host: str) -> PurePosixPath:
    path = PurePosixPath(member.filename)
    mode = member.external_attr >> 16
    if (
        member.orig_filename != member.filename
        or not path.parts
        or path.is_absolute()
        or any(_unsafe_part(part) for part in path.parts)
        or "\\" in member.filename
        or member.filename != path.as_posix()
        or stat.S_IFMT(mode) not in (0, stat.S_IFREG)
        or member.is_dir()
        or member.flag_bits & 1
    ):
        raise ValueError("payload_member_type")
    if host == "antigravity":
        if path != PurePosixPath("release-manifest.json") and path.parts[:2] not in (
            (".agents", "skills"),
            (".agents", "rules"),
        ):
            raise ValueError("payload_layout")
        return path
    if path.parts[0] != "opensocrates":
        raise ValueError("payload_layout")
    return PurePosixPath("plugins/opensocrates-lab/skills") / path


def _entries(archive: zipfile.ZipFile, host: str) -> list[tuple[PurePosixPath, bytes]]:
    result: list[tuple[PurePosixPath, bytes]] = []
    seen: set[str] = set()
    total = 0
    members = archive.infolist()
    if len(members) > MAX_MEMBERS:
        raise ValueError("payload_members")
    for member in members:
        target = _member_target(member, host)
        folded = target.as_posix().casefold()
        total += member.file_size
        if folded in seen or total > MAX_EXPANDED_BYTES:
            raise ValueError("payload_limits")
        seen.add(folded)
        raw = archive.read(member)
        if len(raw) != member.file_size:
            raise ValueError("payload_size")
        if host == "antigravity" and target == PurePosixPath("release-manifest.json"):
            _release_metadata(raw)
        else:
            result.append((target, raw))
    return result


def _write_new(root: Path, entries: list[tuple[PurePosixPath, bytes]]) -> None:
    """Stage a complete tree and commit new roots; no partial archive extraction."""
    roots = {path.parts[0] for path, _ in entries}
    if any(os.path.lexists(root / name) for name in roots):
        raise ValueError("payload_collision")
    with tempfile.TemporaryDirectory(prefix=".content-stage-", dir=root) as folder:
        stage = Path(folder)
        for relative, raw in entries:
            destination = stage.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as stream:
                stream.write(raw)
            destination.chmod(0o644)
        committed: list[tuple[str, int]] = []
        try:
            for name in sorted(roots):
                if os.path.lexists(root / name):
                    raise ValueError("payload_collision")
                identity = (stage / name).stat().st_ino
                (stage / name).rename(root / name)
                committed.append((name, identity))
        except OSError:
            _rollback_roots(root, stage, committed)
            raise
        except ValueError:
            _rollback_roots(root, stage, committed)
            raise


def _rollback_roots(root: Path, stage: Path, committed: list[tuple[str, int]]) -> None:
    for name, identity in reversed(committed):
        target = root / name
        if target.lstat().st_ino == identity and not target.is_symlink():
            target.rename(stage / name)


def _plugin_manifests() -> list[tuple[PurePosixPath, bytes]]:
    marketplace = {
        "name": "opensocrates-office-lab",
        "interface": {"displayName": "OpenSocrates Office Lab"},
        "plugins": [
            {
                "name": "opensocrates-lab",
                "source": {"source": "local", "path": "./plugins/opensocrates-lab"},
                "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                "category": "Productivity",
            }
        ],
    }
    plugin = {
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        "name": "opensocrates-lab",
        "version": "0.1.0",
        "description": "Experimental Work content adapter for OpenSocrates 1.5.3.",
    }
    return [
        (PurePosixPath(".agents/plugins/marketplace.json"), json.dumps(marketplace).encode()),
        (PurePosixPath("plugins/opensocrates-lab/plugin.json"), json.dumps(plugin).encode()),
    ]


def _base_guide(host: str, arm: str) -> dict[str, Any]:
    if host not in ("desktop_work", "claude_cowork", "antigravity"):
        raise ValueError("unsupported_host")
    links = {
        "desktop_work": [
            {"title": "Work plugins", "url": "https://learn.chatgpt.com/docs/plugins"}
        ],
        "claude_cowork": [
            {
                "title": "Claude plugins",
                "url": "https://support.claude.com/en/articles/13837440-use-plugins-in-claude",
            }
        ],
        "antigravity": [
            {"title": "Antigravity rules", "url": "https://www.antigravity.google/docs/rules/"}
        ],
    }
    return {
        "profile": f"{host}-{'content-only' if arm == 'C' else 'baseline'}",
        "status": "manual_required",
        "steps": [
            "새 대화에서 표시된 actor 폴더만 열고, 동일한 공개 자료와 프롬프트를 사용하세요. / Open only the displayed actor folder in a fresh conversation.",
            "계정·전역·상위 폴더 지침, 메모리, 플러그인, 커넥터를 직접 확인하세요. 새 OS나 폴더만으로 격리되지 않습니다. / Review inherited account/global instructions, memory, plugins and connectors.",
            "실제 모델·effort·앱 버전을 화면에서 확인하세요. 다른 모델이나 CLI로 대체하지 마세요. / Confirm actual model, effort and app version; do not substitute another model or CLI.",
            "앱의 정상 권한 승인 절차를 따르세요. final.md만 out 폴더에 저장하거나 승인할 최종 답변만 수동 입력하세요. / Follow normal trust prompts; save only the final deliverable to out/final.md or use approved manual intake.",
        ],
        "links": links[host],
    }


def setup_guide(host: str, arm: str, actor: Path, payloads: Path | None) -> dict[str, Any]:
    """Return explicit manual instructions without inferring that a host loaded content."""
    guide = _base_guide(host, arm)
    if arm != "C":
        guide["steps"].append(
            "OpenSocrates가 계정·전역·프로젝트에 없는지 확인하세요. / Confirm OpenSocrates is absent from every inherited scope."
        )
        return guide
    payload_host = "claude_cowork" if host == "desktop_work" else host
    try:
        if payloads is None:
            raise ValueError("payload_unavailable")
        payload_bytes(payloads, payload_host)
    except (OSError, ValueError):
        guide["status"] = "unavailable"
        guide["steps"].append(
            "고정된 공개 콘텐츠 파일을 사용할 수 없습니다. C 실행을 시작하지 마세요. / Pinned content is unavailable; do not start C."
        )
        return guide
    steps = {
        "desktop_work": "실험용 content-only 플러그인입니다. Work의 지원되는 로컬 marketplace UI에서 actor 폴더(.agents/plugins/marketplace.json 포함)를 추가하고 opensocrates-lab을 설치·활성화하세요. 암묵적 스킬 선택은 보장되지 않습니다. @ 명시 호출은 별도 조건이므로 이 실험에서 대체하지 마세요. 지원되는 가져오기나 탐색이 없으면 unavailable로 남기세요. 제품의 Codex native 동작 검증이 아닙니다. / Use Work's supported local marketplace UI to add the actor folder containing .agents/plugins/marketplace.json and enable opensocrates-lab; implicit skill selection is not guaranteed and explicit @ invocation is a separate condition. Unsupported discovery remains unavailable. This experimental adapter does not qualify native Codex behavior.",
        "claude_cowork": "검증된 claude-chat-skills ZIP을 Claude 계정의 Skills UI에서 수동 업로드·활성화하세요. 계정 동기화는 다른 조건에도 영향을 줍니다. A/B 전에는 별도 깨끗한 프로필·스냅샷 또는 명시적인 제거 확인이 필요합니다. / Manually upload and enable the verified account skill ZIP in Claude's Skills UI. Account sync affects other conditions; check clean profiles/snapshots or explicit removal before A/B.",
        "antigravity": "actor 안의 .agents/rules와 .agents/skills만 사용하는 새 Antigravity 작업을 여세요. 전역 지침·스킬의 상속을 확인하세요. Gemini 3.8 Flash Medium UI 선택과 요청 문자열 매핑을 직접 확인하세요. / Open a new Antigravity task using this actor's workspace rules/skills; check global inheritance and explicitly confirm the Gemini 3.8 Flash Medium mapping.",
    }
    guide["steps"].append(steps[host])
    if host == "claude_cowork":
        guide["content_file"] = str(payloads / PAYLOADS["claude_cowork"][0])
    return guide


def prepare_content(actor: Path, host: str, payloads: Path | None) -> dict[str, Any]:
    """Prepare only verified content inside a fresh, owned actor workspace."""
    guide = setup_guide(host, "C", actor, payloads)
    if guide["status"] == "unavailable" or host == "claude_cowork":
        return guide
    info = actor.lstat()
    if not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError("actor_unsafe")
    if payloads is None:
        return guide
    raw = payload_bytes(payloads, "antigravity" if host == "antigravity" else "claude_cowork")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = _entries(archive, host)
    if host == "desktop_work":
        entries.extend(_plugin_manifests())
    _write_new(actor, entries)
    return guide
