#!/usr/bin/env python3
"""Run the bounded release security gate.

The v1 runtime is standard-library-only except for the deliberately isolated,
Codex-only selector SDK boundary.  This checker verifies the locally provable
parts of that exception: production import boundaries, direct-network and
execution prohibitions, selector artifact/isolation contracts, dependency and
SBOM consistency, and fixed generated launcher commands.  It records only
counts and stable reason codes, never source paths or source contents.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = "opensocrates.security-scan-evidence/1.0.0"
_STDLIB = set(getattr(sys, "stdlib_module_names", ())) | {
    "_ast",
    "typing_extensions",
}
_NETWORK_MODULES = {
    "aiohttp",
    "boto3",
    "ftplib",
    "httpx",
    "paramiko",
    "requests",
    "socket",
    "telnetlib",
    "urllib3",
    "websocket",
}
_DYNAMIC_NAMES = {"__import__", "compile", "eval", "exec", "execfile"}
_SENSITIVE_NAMES = {
    "api_key",
    "cwd",
    "credential",
    "credentials",
    "oauth",
    "password",
    "private_key",
    "prompt",
    "raw_output",
    "reasoning",
    "secret",
    "secrets",
    "selector_reasoning",
    "tool_data",
    "tool_input",
    "tool_output",
    "transcript",
    "transcript_path",
    "user_prompt",
    "workspace",
    "workspace_path",
}
_SAFE_LAUNCH_EVENTS = {
    "completion_candidate",
    "post_compaction",
    "pre_compaction",
    "session_ended",
    "session_started",
    "skill_invoked",
    "tool_batch_completed",
    "tool_failed",
    "tool_succeeded",
    "user_prompt_submitted",
}
_SAFE_HOSTS = {"codex"}
_SELECTOR_DIRECTORY = Path("src/opensocrates/selector")
_SELECTOR_REQUIRED_MODULES = frozenset(
    {
        "application.py",
        "artifacts.py",
        "context.py",
        "models.py",
        "sdk.py",
        "sdk_worker.py",
    }
)
_SELECTOR_SDK_MODULE = "sdk_worker.py"
_ALLOWED_SDK_IMPORTS = frozenset({"openai_codex", "openai_codex.client", "openai_codex.types"})
_SELECTOR_DISABLED_FEATURES = frozenset(
    {
        "apps",
        "enable_fanout",
        "goals",
        "hooks",
        "multi_agent",
        "multi_agent_v2",
        "plugins",
        "request_permissions_tool",
        "shell_tool",
        "unified_exec",
        "web_search_request",
    }
)
_SELECTOR_RECURSION_ENV = "OPENSOCRATES_SELECTOR_ACTIVE"
_RUNTIME_REQUIREMENTS = {
    "openai-codex": "==0.144.4",
    "openai-codex-cli-bin": "==0.144.4",
    "pydantic": ">=2.12,<3",
}
_REQUIREMENT_NAME = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(.*)$")


class SecurityScanError(RuntimeError):
    """Raised for an invalid checker configuration."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical_json(value), encoding="utf-8")


def _iso_now() -> str:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch and epoch.isdigit():
        return (
            datetime.fromtimestamp(int(epoch), UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve(root: Path, value: str | Path) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


def _root_name(module: str) -> str:
    return module.split(".", 1)[0]


def _call_name(node: ast.Call) -> tuple[str, str] | None:
    function = node.func
    if isinstance(function, ast.Name):
        return ("", function.id)
    if isinstance(function, ast.Attribute) and isinstance(function.value, ast.Name):
        return (function.value.id, function.attr)
    return None


def _sensitive_name(name: str) -> bool:
    normalized = name.casefold()
    if normalized in _SENSITIVE_NAMES:
        return True
    return normalized.endswith("_prompt") or normalized.startswith("raw_")


def _sensitive_expression(node: ast.AST | None) -> bool:  # noqa: C901  # Closed AST data shapes.
    if isinstance(node, ast.Name):
        return _sensitive_name(node.id)
    if isinstance(node, ast.Attribute):
        return _sensitive_name(node.attr)
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return any(_sensitive_expression(item) for item in node.elts)
    if isinstance(node, ast.JoinedStr):
        return any(
            _sensitive_expression(value.value)
            for value in node.values
            if isinstance(value, ast.FormattedValue)
        )
    if isinstance(node, ast.FormattedValue):
        return _sensitive_expression(node.value)
    if isinstance(node, ast.Starred):
        return _sensitive_expression(node.value)
    if isinstance(node, ast.Dict):
        for key, value in zip(node.keys, node.values, strict=True):
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                if _sensitive_name(key.value):
                    return True
            if _sensitive_expression(value):
                return True
    return False


def _constant_string(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _import_findings(tree: ast.AST) -> tuple[int, int, int]:
    external = 0
    network = 0
    dynamic_import = 0
    for node in ast.walk(tree):
        module: str | None = None
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = _root_name(alias.name)
                if root not in _STDLIB and not alias.name.startswith("opensocrates"):
                    external += 1
                if root in _NETWORK_MODULES:
                    network += 1
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            module = node.module or ""
            root = _root_name(module)
            if root not in _STDLIB and not module.startswith("opensocrates"):
                external += 1
            if root in _NETWORK_MODULES or module in {"urllib.request", "urllib.error"}:
                network += 1
        if module and module in {"importlib", "importlib.util"}:
            dynamic_import += 1
    return external, network, dynamic_import


def _call_findings(tree: ast.AST) -> dict[str, int]:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    findings = {
        "dynamic_execution": 0,
        "shell_execution": 0,
        "network_calls": 0,
        "sensitive_writes": 0,
        "unsafe_deserialization": 0,
    }
    function_stack: list[str] = []

    class Visitor(ast.NodeVisitor):
        def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            function_stack.append(node.name)
            self.generic_visit(node)
            function_stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._visit_function(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._visit_function(node)

        def visit_Call(self, node: ast.Call) -> None:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
            named = _call_name(node)
            if named is None:
                self.generic_visit(node)
                return
            owner, name = named
            if owner == "" and name in _DYNAMIC_NAMES:
                # Literal optional-module imports are bounded; imports whose
                # module name comes from runtime data are the forbidden case.
                literal_import = (
                    name in {"__import__", "import_module"}
                    and node.args
                    and _constant_string(node.args[0])
                )
                sanctioned_optional_loader = (
                    name == "import_module"
                    and owner == "importlib"
                    and function_stack[-1:] == ["_load_optional"]
                )
                if not literal_import and not sanctioned_optional_loader:
                    findings["dynamic_execution"] += 1
            if owner == "importlib" and name == "import_module":
                if (not node.args or not _constant_string(node.args[0])) and function_stack[
                    -1:
                ] != ["_load_optional"]:
                    findings["dynamic_execution"] += 1
            elif owner == "" and name == "import_module":
                if not node.args or not _constant_string(node.args[0]):
                    findings["dynamic_execution"] += 1
            if owner in {"pickle", "marshal"} or (
                owner == "yaml" and name in {"load", "full_load", "unsafe_load"}
            ):
                findings["unsafe_deserialization"] += 1
            if owner in {"os", "commands"} and (
                name == "system" or name.startswith("exec") or name == "popen"
            ):
                findings["shell_execution"] += 1
            if owner == "subprocess":
                shell = next(
                    (keyword.value for keyword in node.keywords if keyword.arg == "shell"),
                    None,
                )
                if isinstance(shell, ast.Constant) and shell.value is True:
                    findings["shell_execution"] += 1
                else:
                    findings["shell_execution"] += 1
            if name in {"connect", "create_connection", "urlopen"} or (
                owner in {"requests", "httpx", "socket", "urllib", "urllib_request"}
                and name in {"get", "post", "put", "request", "open"}
            ):
                findings["network_calls"] += 1
            payload: ast.AST | None = None
            if name in {"write", "write_text", "write_bytes", "writelines"} and node.args:
                payload = node.args[0]
            elif owner == "os" and name == "write" and len(node.args) >= 2:
                payload = node.args[1]
            # ``json.dumps`` is transient serialization, not a write sink.  The
            # selector uses it to create an in-memory SDK request, so treating
            # every serialization call as persistence would be a false positive.
            if payload is not None and _sensitive_expression(payload):
                findings["sensitive_writes"] += 1
            self.generic_visit(node)

    Visitor().visit(tree)
    return findings


def _attribute_chain(node: ast.AST) -> tuple[str, ...] | None:
    if isinstance(node, ast.Name):
        return (node.id,)
    if isinstance(node, ast.Attribute):
        parent = _attribute_chain(node.value)
        return (*parent, node.attr) if parent is not None else None
    return None


def _call_chain(node: ast.Call) -> tuple[str, ...] | None:
    return _attribute_chain(node.func)


def _literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _literal_int(node: ast.AST | None) -> int | None:
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value
    return None


def _literal_int_expression(node: ast.AST | None) -> int | None:
    literal = _literal_int(node)
    if literal is not None:
        return literal
    if not isinstance(node, ast.BinOp):
        return None
    left = _literal_int_expression(node.left)
    right = _literal_int_expression(node.right)
    if left is None or right is None:
        return None
    if isinstance(node.op, ast.Add):
        return left + right
    if isinstance(node.op, ast.Sub):
        return left - right
    if isinstance(node.op, ast.Mult):
        return left * right
    return None


def _top_level_function(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    if not isinstance(tree, ast.Module):
        return None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _class_method(tree: ast.AST, class_name: str, method_name: str) -> ast.FunctionDef | None:
    if not isinstance(tree, ast.Module):
        return None
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for member in node.body:
            if isinstance(member, ast.FunctionDef) and member.name == method_name:
                return member
    return None


def _function_calls(node: ast.FunctionDef | None) -> tuple[ast.Call, ...]:
    if node is None:
        return ()
    return tuple(child for child in ast.walk(node) if isinstance(child, ast.Call))


def _function_has_call(node: ast.FunctionDef | None, expected: tuple[str, ...]) -> bool:
    return any(_call_chain(call) == expected for call in _function_calls(node))


def _keyword_value(call: ast.Call, name: str) -> ast.AST | None:
    return next((keyword.value for keyword in call.keywords if keyword.arg == name), None)


def _node_has_name(node: ast.AST, name: str) -> bool:
    return any(isinstance(child, ast.Name) and child.id == name for child in ast.walk(node))


def _node_has_attribute(node: ast.AST, name: str) -> bool:
    return any(isinstance(child, ast.Attribute) and child.attr == name for child in ast.walk(node))


def _node_has_string(node: ast.AST, value: str) -> bool:
    return any(_literal_string(child) == value for child in ast.walk(node))


def _node_has_string_fragment(node: ast.AST, value: str) -> bool:
    return any(
        isinstance(child, ast.Constant) and isinstance(child.value, str) and value in child.value
        for child in ast.walk(node)
    )


def _module_literal_int(tree: ast.Module, name: str) -> int | None:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            return _literal_int_expression(node.value)
    return None


def _module_literal_string(tree: ast.Module, name: str) -> str | None:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            return _literal_string(node.value)
    return None


def _module_literal_strings(tree: ast.Module, name: str) -> frozenset[str]:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            continue
        if isinstance(node.value, (ast.Tuple, ast.List, ast.Set)):
            values = {_literal_string(item) for item in node.value.elts}
            if None not in values:
                return frozenset(value for value in values if value is not None)
    return frozenset()


def _return_dict(function: ast.FunctionDef | None) -> ast.Dict | None:
    if function is None:
        return None
    for node in ast.walk(function):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            return node.value
    return None


def _dict_value(node: ast.Dict | None, key: str) -> ast.AST | None:
    if node is None:
        return None
    for candidate, value in zip(node.keys, node.values, strict=True):
        if _literal_string(candidate) == key:
            return value
    return None


def _assigned_value(function: ast.FunctionDef | None, name: str) -> ast.AST | None:
    if function is None:
        return None
    for node in ast.walk(function):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return node.value
    return None


def _function_names_with_call(tree: ast.Module, expected: tuple[str, ...]) -> frozenset[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and _function_has_call(node, expected):
            names.add(node.name)
    return frozenset(names)


def _comparison_has_upper_bound(node: ast.AST, value_name: str, limit_name: str) -> bool:
    def is_value(candidate: ast.AST) -> bool:
        return (isinstance(candidate, ast.Name) and candidate.id == value_name) or (
            isinstance(candidate, ast.Attribute) and candidate.attr == value_name
        )

    for child in ast.walk(node):
        if not isinstance(child, ast.Compare):
            continue
        operands = (child.left, *child.comparators)
        for index, operand in enumerate(operands[:-1]):
            successor = operands[index + 1]
            if (
                is_value(operand)
                and isinstance(successor, ast.Name)
                and successor.id == limit_name
                and isinstance(child.ops[index], ast.LtE)
            ):
                return True
    return False


def _call_has_keyword_chain(call: ast.Call, name: str, expected: tuple[str, ...]) -> bool:
    value = _keyword_value(call, name)
    return value is not None and _attribute_chain(value) == expected


def _call_has_keyword_bool(call: ast.Call, name: str, expected: bool) -> bool:
    value = _keyword_value(call, name)
    return isinstance(value, ast.Constant) and value.value is expected


def _is_empty_list(node: ast.AST | None) -> bool:
    return isinstance(node, ast.List) and not node.elts


def _is_literal_bool(node: ast.AST | None, expected: bool) -> bool:
    return isinstance(node, ast.Constant) and node.value is expected


def _literal_string_list(node: ast.AST | None) -> tuple[str, ...] | None:
    if not isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return None
    values: list[str] = []
    for element in node.elts:
        value = _literal_string(element)
        if value is None:
            return None
        values.append(value)
    return tuple(values)


def _parse_selector_modules(root: Path) -> tuple[dict[str, ast.Module], set[str]]:
    directory = root / _SELECTOR_DIRECTORY
    if not directory.is_dir():
        return {}, {"selector_source_missing"}
    modules: dict[str, ast.Module] = {}
    errors: set[str] = set()
    for relative in sorted(_SELECTOR_REQUIRED_MODULES):
        path = directory / relative
        if not path.is_file():
            errors.add("selector_required_module_missing")
            continue
        try:
            modules[relative] = ast.parse(path.read_text(encoding="utf-8"), filename="<selector>")
        except (OSError, UnicodeError, SyntaxError):
            errors.add("selector_source_parse_error")
    return modules, errors


def _scan_production(root: Path) -> dict[str, Any]:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    source = root / "src" / "opensocrates"
    if not source.is_dir():
        return {
            "status": "unavailable",
            "production_files": 0,
            "external_imports": 0,
            "network_imports": 0,
            "dynamic_imports": 0,
            "dynamic_execution": 0,
            "shell_execution": 0,
            "network_calls": 0,
            "sensitive_writes": 0,
            "unsafe_deserialization": 0,
            "error_codes": ["production_source_missing"],
        }
    totals: dict[str, Any] = {
        "production_files": 0,
        "external_imports": 0,
        "network_imports": 0,
        "dynamic_imports": 0,
        "dynamic_execution": 0,
        "shell_execution": 0,
        "network_calls": 0,
        "sensitive_writes": 0,
        "unsafe_deserialization": 0,
    }
    errors: set[str] = set()
    for path in sorted(source.rglob("*.py"), key=lambda item: item.as_posix().encode("utf-8")):
        totals["production_files"] += 1
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename="<production>")
        except (OSError, UnicodeError, SyntaxError):
            errors.add("production_parse_error")
            continue
        external, network, dynamic_import = _import_findings(tree)
        totals["external_imports"] += external
        totals["network_imports"] += network
        totals["dynamic_imports"] += dynamic_import
        findings = _call_findings(tree)
        for key, value in findings.items():
            totals[key] += value
    violations = sum(value for key, value in totals.items() if key not in {"production_files"})
    if errors:
        status = "unavailable"
    else:
        status = "fail" if violations else "pass"
    totals["status"] = status
    totals["error_codes"] = sorted(errors)
    if totals["external_imports"]:
        totals["error_codes"].append("external_production_import")
    if totals["network_imports"] or totals["network_calls"]:
        totals["error_codes"].append("runtime_network_pattern")
    if totals["dynamic_execution"] or totals["dynamic_imports"]:
        totals["error_codes"].append("dynamic_execution_pattern")
    if totals["shell_execution"]:
        totals["error_codes"].append("shell_execution_pattern")
    if totals["sensitive_writes"]:
        totals["error_codes"].append("sensitive_persistence_pattern")
    if totals["unsafe_deserialization"]:
        totals["error_codes"].append("unsafe_deserialization_pattern")
    totals["error_codes"] = sorted(set(totals["error_codes"]))
    return totals


def _selector_sdk_import_check(  # noqa: C901  # Closed SDK-import boundary.
    modules: Mapping[str, ast.Module],
) -> tuple[int, set[str]]:
    imports: list[tuple[str, str, tuple[str, ...]]] = []
    static_sdk_imports = 0

    class Visitor(ast.NodeVisitor):
        def __init__(self, relative: str) -> None:
            self.relative = relative
            self.functions: list[str] = []

        def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            self.functions.append(node.name)
            self.generic_visit(node)
            self.functions.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._visit_function(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._visit_function(node)

        def visit_Import(self, node: ast.Import) -> None:
            nonlocal static_sdk_imports
            static_sdk_imports += sum(
                _root_name(alias.name) in {"openai_codex", "openai"} for alias in node.names
            )

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            nonlocal static_sdk_imports
            module = node.module or ""
            if _root_name(module) in {"openai_codex", "openai"}:
                static_sdk_imports += 1

        def visit_Call(self, node: ast.Call) -> None:  # noqa: C901  # Closed import boundary.
            if _call_chain(node) == ("importlib", "import_module"):
                target = _literal_string(node.args[0] if node.args else None)
                if target is not None and target.startswith("openai_codex"):
                    imports.append((self.relative, target, tuple(self.functions)))
            self.generic_visit(node)

    for relative, tree in modules.items():
        Visitor(relative).visit(tree)
    errors: set[str] = set()
    if static_sdk_imports:
        errors.add("selector_sdk_static_import")
    imported_targets = {target for _, target, _ in imports}
    if imported_targets != _ALLOWED_SDK_IMPORTS:
        errors.add("selector_sdk_import_set_invalid")
    if any(
        relative != _SELECTOR_SDK_MODULE or functions != ("_load_sdk",)
        for relative, _target, functions in imports
    ):
        errors.add("selector_sdk_import_outside_worker")
    return len(imports), errors


def _runtime_sdk_import_boundary_check(  # noqa: C901  # Closed runtime SDK boundary.
    root: Path,
) -> set[str]:
    """Reject SDK imports anywhere except the worker's narrow lazy loader."""

    source = root / "src" / "opensocrates"
    if not source.is_dir():
        return {"production_source_missing"}
    errors: set[str] = set()
    for path in source.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename="<production>")
        except (OSError, UnicodeError, SyntaxError):
            errors.add("production_parse_error")
            continue
        relative = path.relative_to(source).as_posix()

        class Visitor(ast.NodeVisitor):
            def __init__(self, module_relative: str) -> None:
                self.functions: list[str] = []
                self.relative = module_relative

            def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
                self.functions.append(node.name)
                self.generic_visit(node)
                self.functions.pop()

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self._visit_function(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                self._visit_function(node)

            def visit_Import(self, node: ast.Import) -> None:
                if any(
                    _root_name(alias.name) in {"openai", "openai_codex"} for alias in node.names
                ):
                    errors.add("selector_sdk_static_import")

            def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
                if _root_name(node.module or "") in {"openai", "openai_codex"}:
                    errors.add("selector_sdk_static_import")

            def visit_Call(self, node: ast.Call) -> None:
                if _call_chain(node) == ("importlib", "import_module"):
                    target = _literal_string(node.args[0] if node.args else None)
                    if target is not None and _root_name(target) in {"openai", "openai_codex"}:
                        if not (
                            self.relative == "selector/sdk_worker.py"
                            and tuple(self.functions) == ("_load_sdk",)
                            and target in _ALLOWED_SDK_IMPORTS
                        ):
                            errors.add("selector_sdk_import_outside_worker")
                self.generic_visit(node)

        Visitor(relative).visit(tree)
    return errors


def _selector_process_check(modules: Mapping[str, ast.Module]) -> set[str]:
    sdk = modules.get("sdk.py")
    worker = modules.get(_SELECTOR_SDK_MODULE)
    if sdk is None or worker is None:
        return {"selector_process_boundary_missing"}
    start = _class_method(sdk, "CodexReasoningSelector", "_start_worker")
    if start is None:
        start = _top_level_function(sdk, "_start_worker")
    worker_entry = _top_level_function(worker, "run_selector_worker")
    errors: set[str] = set()
    if not any(
        _call_chain(call) == ("multiprocessing", "get_context")
        and _literal_string(call.args[0] if call.args else None) == "spawn"
        for call in _function_calls(start)
    ):
        errors.add("selector_spawn_context_missing")
    process_calls = [
        call for call in _function_calls(start) if (_call_chain(call) or ())[-1:] == ("Process",)
    ]
    if not any(
        _node_has_name(_keyword_value(call, "target") or ast.Constant(None), "run_selector_worker")
        and _call_has_keyword_bool(call, "daemon", False)
        for call in process_calls
    ):
        errors.add("selector_fresh_worker_contract_missing")
    if not _function_has_call(worker_entry, ("os", "setsid")):
        errors.add("selector_process_isolation_missing")
    if not any(
        _call_chain(call) == ("os", "killpg")
        for call in ast.walk(sdk)
        if isinstance(call, ast.Call)
    ):
        errors.add("selector_process_cleanup_missing")
    return errors


def _selector_recursion_check(modules: Mapping[str, ast.Module]) -> set[str]:
    worker = modules.get(_SELECTOR_SDK_MODULE)
    runner = _top_level_function(worker, "run_selector_worker") if worker is not None else None
    if runner is None:
        return {"selector_sdk_recursion_guard_missing"}
    for node in ast.walk(runner):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Subscript)
                and _attribute_chain(target.value) == ("os", "environ")
                and _node_has_name(target.slice, "SELECTOR_RECURSION_ENV")
                and _literal_string(node.value) == "1"
            ):
                return set()
    return {"selector_sdk_recursion_guard_missing"}


def _selector_oauth_boundary_check(modules: Mapping[str, ast.Module]) -> set[str]:
    """Permit only an owner-checked OAuth-file hand-off to the app-server."""

    worker = modules.get(_SELECTOR_SDK_MODULE)
    if worker is None:
        return {"selector_oauth_boundary_missing"}
    oauth_file = _top_level_function(worker, "_safe_existing_oauth_file")
    environment = _top_level_function(worker, "_isolated_environment")
    sdk_call = _top_level_function(worker, "_run_sdk_call")
    if oauth_file is None or environment is None or sdk_call is None:
        return {"selector_oauth_boundary_missing"}
    errors: set[str] = set()
    oauth_calls = _function_calls(oauth_file)
    if not _function_has_call(oauth_file, ("auth_file", "lstat")):
        errors.add("selector_oauth_file_check_missing")
    if not any(_call_chain(call) == ("os", "geteuid") for call in oauth_calls):
        errors.add("selector_oauth_owner_check_missing")
    if not _node_has_name(oauth_file, "stat") or not _node_has_attribute(oauth_file, "st_mode"):
        errors.add("selector_oauth_permission_check_missing")
    if not _node_has_string(environment, "CODEX_HOME"):
        errors.add("selector_oauth_environment_boundary_missing")
    symlink_calls = [
        call for call in _function_calls(sdk_call) if _call_chain(call) == ("os", "symlink")
    ]
    if not any(
        _node_has_name(call.args[0] if call.args else ast.Constant(None), "auth_file")
        and _node_has_string(
            call.args[1] if len(call.args) > 1 else ast.Constant(None), "auth.json"
        )
        for call in symlink_calls
    ):
        errors.add("selector_oauth_handoff_missing")
    credential_read_names = {"open", "read", "read_bytes", "read_text", "load", "loads"}
    for call in (node for node in ast.walk(worker) if isinstance(node, ast.Call)):
        chain = _call_chain(call)
        if chain and chain[-1] in credential_read_names and _node_has_name(call, "auth_file"):
            errors.add("selector_oauth_credential_read")
    return errors


def _selector_silent_worker_check(worker: ast.Module) -> set[str]:
    silence = _top_level_function(worker, "_silence_standard_streams")
    errors: set[str] = set()
    duplicated_descriptors = {
        _literal_int(call.args[1])
        for call in _function_calls(silence)
        if _call_chain(call) == ("os", "dup2") and len(call.args) >= 2
    }
    if duplicated_descriptors != {1, 2}:
        errors.add("selector_standard_stream_silencing_missing")
    if not any(
        _call_chain(call) == ("os", "open")
        and _attribute_chain(call.args[0] if call.args else ast.Constant(None)) == ("os", "devnull")
        for call in _function_calls(silence)
    ):
        errors.add("selector_standard_stream_sink_missing")
    for call in (node for node in ast.walk(worker) if isinstance(node, ast.Call)):
        chain = _call_chain(call)
        if chain == ("print",):
            errors.add("selector_stdout_stderr_write")
        if chain in {("sys", "stdout", "write"), ("sys", "stderr", "write")}:
            errors.add("selector_stdout_stderr_write")
        if chain == ("os", "write") and len(call.args) >= 2:
            if _literal_int(call.args[0]) in {1, 2}:
                errors.add("selector_stdout_stderr_write")
    return errors


def _selector_isolation_check(  # noqa: C901  # Explicit selector-isolation contract.
    modules: Mapping[str, ast.Module],
) -> set[str]:
    worker = modules.get(_SELECTOR_SDK_MODULE)
    if worker is None:
        return {"selector_sdk_worker_missing"}
    errors: set[str] = set()
    disabled = _module_literal_strings(worker, "_DISABLED_FEATURES")
    if not _SELECTOR_DISABLED_FEATURES.issubset(disabled):
        errors.add("selector_command_web_features_not_disabled")
    config = _top_level_function(worker, "_thread_config")
    overrides = _top_level_function(worker, "_config_overrides")
    start_params = _top_level_function(worker, "_thread_start_params")
    sdk_call = _top_level_function(worker, "_run_sdk_call")
    if config is None or overrides is None or start_params is None or sdk_call is None:
        errors.add("selector_sdk_config_missing")
        return errors | _selector_silent_worker_check(worker)
    if not _node_has_name(config, "_DISABLED_FEATURES"):
        errors.add("selector_feature_config_missing")
    if not any(
        isinstance(node, ast.Dict)
        and any(_literal_string(key) == "web_search" for key in node.keys)
        and any(_literal_string(value) == "disabled" for value in node.values)
        for node in ast.walk(config)
    ):
        errors.add("selector_web_disabled_missing")
    if not _node_has_string(overrides, 'web_search="disabled"'):
        errors.add("selector_web_override_missing")
    if not _node_has_string_fragment(
        overrides, "request_max_retries=0"
    ) or not _node_has_string_fragment(overrides, "stream_max_retries=0"):
        errors.add("selector_retry_policy_missing")
    parameters = _return_dict(start_params)
    dynamic_tools = _dict_value(parameters, "dynamicTools")
    if (
        _literal_string(_dict_value(parameters, "approvalPolicy")) != "never"
        or not isinstance(dynamic_tools, ast.Call)
        or _call_chain(dynamic_tools) != ("_dynamic_tools",)
        or not _is_empty_list(_dict_value(parameters, "environments"))
        or not _is_literal_bool(_dict_value(parameters, "ephemeral"), True)
        or _literal_string(_dict_value(parameters, "sandbox")) != "read-only"
        or _dict_value(parameters, "model") is not None
    ):
        errors.add("selector_low_level_thread_policy_invalid")
    start_calls = [
        call
        for call in _function_calls(sdk_call)
        if _call_chain(call) == ("client", "thread_start")
    ]
    if not any(
        len(call.args) == 1
        and isinstance(call.args[0], ast.Call)
        and _call_chain(call.args[0]) == ("_thread_start_params",)
        for call in start_calls
    ):
        errors.add("selector_low_level_thread_start_missing")
    if not any(
        _call_chain(call) == ("sdk_client", "CodexClient")
        and _node_has_name(
            _keyword_value(call, "approval_handler") or ast.Constant(None), "approval_handler"
        )
        for call in _function_calls(sdk_call)
    ):
        errors.add("selector_dynamic_tool_client_missing")
    turn_calls = [
        call for call in _function_calls(sdk_call) if _call_chain(call) == ("thread", "turn")
    ]
    if len(turn_calls) != 1:
        errors.add("selector_sdk_turn_contract_missing")
    else:
        turn = turn_calls[0]
        if not _call_has_keyword_chain(turn, "sandbox", ("sdk", "Sandbox", "read_only")):
            errors.add("selector_read_only_sandbox_missing")
        if not _call_has_keyword_chain(turn, "approval_mode", ("sdk", "ApprovalMode", "deny_all")):
            errors.add("selector_write_approval_missing")
        if _keyword_value(turn, "model") is not None:
            errors.add("selector_explicit_model_forbidden")
    if not _function_has_call(sdk_call, ("tempfile", "TemporaryDirectory")):
        errors.add("selector_isolated_working_directory_missing")
    if not _function_has_call(sdk_call, ("os", "chdir")):
        errors.add("selector_isolated_working_directory_missing")
    errors.update(_selector_silent_worker_check(worker))
    return errors


def _guarded_by_attribute(
    function: ast.FunctionDef | None, attribute: str, required_call: tuple[str, ...]
) -> bool:
    if function is None:
        return False
    for node in ast.walk(function):
        if not isinstance(node, ast.If) or not _node_has_attribute(node.test, attribute):
            continue
        if any(
            _call_chain(call) == required_call
            for call in ast.walk(node)
            if isinstance(call, ast.Call)
        ):
            return True
    return False


def _has_attribute_guard(function: ast.FunctionDef | None, attribute: str) -> bool:
    return bool(
        function is not None
        and any(
            isinstance(node, ast.If) and _node_has_attribute(node.test, attribute)
            for node in ast.walk(function)
        )
    )


def _selector_context_primitive_check(context: ast.Module) -> set[str]:
    """Bind the Context Accessor to its finite, descriptor-only read surface."""

    errors: set[str] = set()
    required_limits = {
        "MAX_CONTEXT_CALLS": 8,
        "MAX_CONTEXT_READ_BYTES": 32 * 1024,
        "MAX_CONTEXT_TOTAL_BYTES": 256 * 1024,
        "MAX_CONTEXT_DIRECTORY_ENTRIES": 128,
    }
    if any(_module_literal_int(context, name) != value for name, value in required_limits.items()):
        errors.add("selector_context_limits_invalid")
    flags = _top_level_function(context, "_open_flags")
    if flags is None or any(
        not _node_has_attribute(flags, name) for name in ("O_RDONLY", "O_CLOEXEC", "O_NOFOLLOW")
    ):
        errors.add("selector_context_read_flags_invalid")
    forbidden_open_flags = {"O_APPEND", "O_CREAT", "O_RDWR", "O_TRUNC", "O_WRONLY"}
    if any(
        isinstance(node, ast.Attribute) and node.attr in forbidden_open_flags
        for node in ast.walk(context)
    ):
        errors.add("selector_context_write_flag_present")
    if _function_names_with_call(context, ("os", "open")) != {"_open_beneath", "_open_exact"}:
        errors.add("selector_context_open_surface_invalid")
    pread_calls = [
        call
        for call in (node for node in ast.walk(context) if isinstance(node, ast.Call))
        if _call_chain(call) == ("os", "pread")
    ]
    if len(pread_calls) != 1 or not _function_has_call(
        _class_method(context, "SelectorContextAccessor", "_read_descriptor"),
        ("os", "pread"),
    ):
        errors.add("selector_context_pread_surface_invalid")
    if _function_names_with_call(context, ("os", "scandir")) != {"_scan_directory"}:
        errors.add("selector_context_scandir_surface_invalid")
    open_beneath = _top_level_function(context, "_open_beneath")
    if not any(
        _call_chain(call) == ("os", "open") and _keyword_value(call, "dir_fd") is not None
        for call in _function_calls(open_beneath)
    ):
        errors.add("selector_context_containment_missing")
    forbidden_reads_or_writes = {
        ("open",),
        ("os", "read"),
        ("os", "write"),
        ("builtins", "open"),
    }
    if any(
        (_call_chain(call) in forbidden_reads_or_writes)
        or (
            (_call_chain(call) or ())[-1:]
            in {("read_bytes",), ("read_text",), ("write",), ("write_bytes",), ("write_text",)}
        )
        for call in (node for node in ast.walk(context) if isinstance(node, ast.Call))
    ):
        errors.add("selector_context_unapproved_io")
    return errors


def _selector_dynamic_context_check(worker: ast.Module) -> set[str]:
    """Verify the pinned low-level SDK tool shape without inspecting content."""

    errors: set[str] = set()
    if _module_literal_string(worker, "_CONTEXT_TOOL_METHOD") != "item/tool/call":
        errors.add("selector_context_tool_method_invalid")
    if _module_literal_string(worker, "_CONTEXT_TOOL_NAME") != "read_context":
        errors.add("selector_context_tool_name_invalid")
    schema = _return_dict(_top_level_function(worker, "_context_tool_schema"))
    input_schema = _dict_value(schema, "inputSchema")
    if (
        _literal_string(_dict_value(schema, "type")) != "function"
        or not _node_has_name(
            _dict_value(schema, "name") or ast.Constant(None), "_CONTEXT_TOOL_NAME"
        )
        or not isinstance(input_schema, ast.Dict)
        or not _is_literal_bool(_dict_value(input_schema, "additionalProperties"), False)
        or _literal_string_list(_dict_value(input_schema, "required")) != ("operation",)
    ):
        errors.add("selector_context_tool_schema_invalid")
    dynamic_tools = _top_level_function(worker, "_dynamic_tools")
    if not _function_has_call(dynamic_tools, ("_context_tool_schema",)):
        errors.add("selector_dynamic_tool_registration_missing")
    handler_call = _class_method(worker, "_ContextToolHandler", "__call__")
    dispatch = _class_method(worker, "_ContextToolHandler", "_dispatch")
    if (
        handler_call is None
        or not _node_has_name(handler_call, "_CONTEXT_TOOL_METHOD")
        or dispatch is None
        or not _node_has_name(dispatch, "_CONTEXT_TOOL_NAME")
        or not _node_has_string(dispatch, "namespace")
    ):
        errors.add("selector_context_tool_dispatch_invalid")
    allowed_arguments = _literal_string_list(_assigned_value(dispatch, "allowed"))
    readers = _assigned_value(dispatch, "readers")
    reader_keys = (
        frozenset(key for key in (_literal_string(key) for key in readers.keys) if key is not None)
        if isinstance(readers, ast.Dict)
        else frozenset()
    )
    if (
        allowed_arguments is None
        or frozenset(allowed_arguments) != {"operation", "relative_path", "index", "offset"}
        or reader_keys
        != {
            "list_workspace",
            "read_referenced_file",
            "read_transcript",
            "read_workspace_file",
        }
    ):
        errors.add("selector_context_tool_allowlist_invalid")
    accessor_calls = {
        _call_chain(call)
        for method in (
            _class_method(worker, "_ContextToolHandler", "_read_transcript"),
            _class_method(worker, "_ContextToolHandler", "_list_workspace"),
            _class_method(worker, "_ContextToolHandler", "_read_workspace_file"),
            _class_method(worker, "_ContextToolHandler", "_read_referenced_file"),
        )
        for call in _function_calls(method)
    }
    expected_accessors = {
        ("self", "_accessor", "list_workspace"),
        ("self", "_accessor", "read_referenced_file"),
        ("self", "_accessor", "read_transcript"),
        ("self", "_accessor", "read_workspace_file"),
    }
    if not expected_accessors.issubset(accessor_calls):
        errors.add("selector_context_tool_read_surface_invalid")
    return errors


def _selector_raw_context_output_check(
    context: ast.Module,
    worker: ast.Module,
) -> set[str]:
    errors: set[str] = set()
    for module in (context, worker):
        for node in ast.walk(module):
            if isinstance(node, ast.Import) and any(
                alias.name == "logging" for alias in node.names
            ):
                errors.add("selector_raw_context_logging_present")
            if isinstance(node, ast.ImportFrom) and node.module == "logging":
                errors.add("selector_raw_context_logging_present")
            if not isinstance(node, ast.Call):
                continue
            chain = _call_chain(node)
            if chain == ("print",) or chain in {
                ("sys", "stderr", "write"),
                ("sys", "stdout", "write"),
            }:
                errors.add("selector_raw_context_output_present")
    return errors


def _selector_context_check(modules: Mapping[str, ast.Module]) -> set[str]:
    context = modules.get("context.py")
    sdk = modules.get("sdk.py")
    worker = modules.get(_SELECTOR_SDK_MODULE)
    if context is None or sdk is None or worker is None:
        return {"selector_context_contract_missing"}
    errors: set[str] = set()
    handles = _top_level_function(context, "handles_for_request")
    if not _guarded_by_attribute(
        handles, "transcript_access_enabled", ("request", "without_transcript_context")
    ):
        errors.add("selector_transcript_opt_out_missing")
    post_init = _class_method(context, "SelectorContextHandles", "__post_init__")
    required_handles = {
        "transcript_access_enabled",
        "transcript_path",
        "transcript_referenced_file_paths",
    }
    if post_init is None or any(
        not _node_has_attribute(post_init, name) for name in required_handles
    ):
        errors.add("selector_transcript_handle_guard_missing")
    if not _has_attribute_guard(
        _top_level_function(sdk, "_worker_request"), "transcript_access_enabled"
    ):
        errors.add("selector_worker_request_opt_out_missing")
    worker_accessor = _top_level_function(worker, "_context_accessor")
    if not _has_attribute_guard(worker_accessor, "transcript_access_enabled"):
        errors.add("selector_sdk_context_opt_out_missing")
    turn_input = _top_level_function(worker, "_selector_turn_input")
    host_path_attributes = {
        "transcript_path",
        "transcript_referenced_file_paths",
        "workspace_path",
    }
    if (
        turn_input is None
        or not _function_has_call(turn_input, ("_context_accessor",))
        or any(_node_has_attribute(turn_input, attribute) for attribute in host_path_attributes)
    ):
        errors.add("selector_host_path_model_input")
    errors.update(_selector_context_primitive_check(context))
    errors.update(_selector_dynamic_context_check(worker))
    errors.update(_selector_raw_context_output_check(context, worker))
    return errors


def _instruction_artifact_check(modules: Mapping[str, ast.Module]) -> set[str]:
    artifacts = modules.get("artifacts.py")
    if artifacts is None:
        return {"instruction_artifact_contract_missing"}
    errors: set[str] = set()
    if _module_literal_int(artifacts, "INSTRUCTION_FILE_TTL_SECONDS") != 86_400:
        errors.add("instruction_artifact_ttl_invalid")
    if _module_literal_int(artifacts, "MAX_INSTRUCTION_FILE_BYTES") != 1024 * 1024:
        errors.add("instruction_artifact_size_bound_invalid")
    calls = tuple(node for node in ast.walk(artifacts) if isinstance(node, ast.Call))
    directory_mode = any(
        (_call_chain(call) or ())[-1:] == ("mkdir",)
        and _literal_int(_keyword_value(call, "mode")) == 0o700
        for call in calls
    ) and any(
        _call_chain(call) == ("os", "chmod")
        and _literal_int(call.args[1] if len(call.args) > 1 else None) == 0o700
        for call in calls
    )
    file_mode = any(
        _call_chain(call) == ("os", "fchmod")
        and _literal_int(call.args[1] if len(call.args) > 1 else None) == 0o600
        for call in calls
    )
    if not directory_mode:
        errors.add("instruction_artifact_directory_mode_invalid")
    if not file_mode:
        errors.add("instruction_artifact_file_mode_invalid")
    for method_name in (
        "create",
        "latest_for_session",
        "delete_turn",
        "delete_session",
        "sweep_expired",
    ):
        if _class_method(artifacts, "InstructionFileStore", method_name) is None:
            errors.add("instruction_artifact_lifecycle_missing")
            break
    return errors


def _selector_persistence_check(  # noqa: C901  # Explicit permitted write boundary.
    modules: Mapping[str, ast.Module],
) -> tuple[int, set[str]]:
    errors: set[str] = set()
    unapproved_writes = 0
    forbidden_modules = ("persistence", "diagnose", "metrics", "trace")
    mutating_names = {
        "replace",
        "rename",
        "symlink",
        "touch",
        "unlink",
        "write",
        "write_bytes",
        "write_text",
        "writelines",
    }
    worker_allowed = {"symlink"}
    for relative, tree in modules.items():
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if any(part in node.module.split(".") for part in forbidden_modules):
                    errors.add("selector_persistence_import")
            if not isinstance(node, ast.Call):
                continue
            chain = _call_chain(node)
            if not chain or chain[-1] not in mutating_names:
                continue
            if chain == ("replace",):
                # ``dataclasses.replace`` creates a new in-memory request for
                # transcript opt-out; it is not a filesystem replacement.
                continue
            if relative == "artifacts.py":
                continue
            if relative == _SELECTOR_SDK_MODULE and chain[-1] in worker_allowed:
                continue
            unapproved_writes += 1
    if unapproved_writes:
        errors.add("selector_unapproved_persistence_write")
    models = modules.get("models.py")
    if models is not None:
        for class_name in ("SelectorRequest", "RawSelectorCandidate"):
            for serializer in ("to_dict", "to_json", "to_json_value", "model_dump"):
                if _class_method(models, class_name, serializer) is not None:
                    errors.add("selector_raw_model_serialization")
    return unapproved_writes, errors


def _parse_extra_module(root: Path, relative: str) -> ast.Module | None:
    try:
        return ast.parse((root / relative).read_text(encoding="utf-8"), filename="<production>")
    except (OSError, UnicodeError, SyntaxError):
        return None


def _if_fails_open_silently(node: ast.If) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Call) or (_call_chain(child) or ())[-1:] != ("write",):
            if isinstance(child, ast.Return):
                value = _literal_int(child.value)
                if child.value is None or value == 0:
                    return True
            continue
        if _literal_string(child.args[0] if child.args else None) == "":
            return True
    return False


def _external_recursion_guard(entrypoint: ast.Module) -> bool:
    has_marker = _node_has_string(entrypoint, _SELECTOR_RECURSION_ENV) or any(
        isinstance(node, ast.ImportFrom)
        and any(alias.name == "SELECTOR_RECURSION_ENV" for alias in node.names)
        for node in ast.walk(entrypoint)
    )
    if not has_marker:
        return False
    for node in ast.walk(entrypoint):
        if not isinstance(node, ast.If):
            continue
        reads_environment = any(
            _call_chain(call) == ("os", "environ", "get")
            and (
                _literal_string(call.args[0] if call.args else None) == _SELECTOR_RECURSION_ENV
                or _node_has_name(
                    call.args[0] if call.args else ast.Constant(None), "SELECTOR_RECURSION_ENV"
                )
            )
            for call in ast.walk(node.test)
            if isinstance(call, ast.Call)
        )
        if reads_environment and _if_fails_open_silently(node):
            return True
    return False


def _timeout_assignment_is_guarded(  # noqa: C901  # Explicit hook-template control flow.
    function: ast.FunctionDef,
) -> tuple[int, int]:
    guarded = 0
    unguarded = 0

    def branch_excludes_user_prompt(test: ast.AST) -> tuple[bool, bool]:
        """Return whether true/false branches exclude UserPromptSubmit."""

        if not isinstance(test, ast.Compare) or not _node_has_string(test, "UserPromptSubmit"):
            return False, False
        if any(isinstance(operator, ast.NotEq) for operator in test.ops):
            return True, False
        if any(isinstance(operator, ast.Eq) for operator in test.ops):
            return False, True
        return False, False

    def record_timeout(value: ast.AST | None, is_guarded: bool) -> None:
        nonlocal guarded, unguarded
        if value is None:
            return
        if is_guarded:
            guarded += 1
        else:
            unguarded += 1

    def visit(  # noqa: C901  # Explicit hook-template control flow.
        nodes: Sequence[ast.stmt], under_non_prompt_guard: bool
    ) -> None:
        for node in nodes:
            if isinstance(node, ast.If):
                true_excludes, false_excludes = branch_excludes_user_prompt(node.test)
                visit(node.body, under_non_prompt_guard or true_excludes)
                visit(node.orelse, under_non_prompt_guard or false_excludes)
                continue
            if isinstance(node, ast.Assign):
                if isinstance(node.value, ast.Dict) and any(
                    _literal_string(key) == "timeout" for key in node.value.keys
                ):
                    record_timeout(node.value, under_non_prompt_guard)
                for target in node.targets:
                    if (
                        isinstance(target, ast.Subscript)
                        and _literal_string(target.slice) == "timeout"
                    ):
                        record_timeout(node.value, under_non_prompt_guard)
            elif isinstance(node, ast.AnnAssign):
                if (
                    isinstance(node.target, ast.Subscript)
                    and _literal_string(node.target.slice) == "timeout"
                ):
                    record_timeout(node.value, under_non_prompt_guard)
            elif isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
                if any(_literal_string(key) == "timeout" for key in node.value.keys):
                    record_timeout(node.value, under_non_prompt_guard)
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.stmt):
                    visit((child,), under_non_prompt_guard)

    visit(function.body, False)
    return guarded, unguarded


def _selector_hook_boundary_check(root: Path) -> set[str]:
    entrypoint = _parse_extra_module(root, "src/opensocrates/hooks/entrypoint.py")
    commands = _parse_extra_module(root, "src/opensocrates/hosts/codex/commands.py")
    if entrypoint is None or commands is None:
        return {"selector_hook_boundary_source_missing"}
    errors: set[str] = set()
    if not _external_recursion_guard(entrypoint):
        errors.add("selector_external_recursion_guard_missing")
    hook_command = _top_level_function(commands, "hook_command")
    if hook_command is None:
        errors.add("selector_hook_timeout_contract_missing")
    else:
        guarded, unguarded = _timeout_assignment_is_guarded(hook_command)
        if unguarded or not guarded:
            errors.add("selector_user_prompt_timeout_not_omitted")
    return errors


def _selector_boundary_check(root: Path) -> dict[str, Any]:
    modules, errors = _parse_selector_modules(root)
    if errors:
        return {
            "status": "unavailable" if "selector_source_parse_error" in errors else "fail",
            "selector_modules_checked": len(modules),
            "sdk_imports_checked": 0,
            "unapproved_selector_writes": 0,
            "error_codes": sorted(errors),
        }
    sdk_imports, sdk_errors = _selector_sdk_import_check(modules)
    runtime_sdk_errors = _runtime_sdk_import_boundary_check(root)
    process_errors = _selector_process_check(modules)
    recursion_errors = _selector_recursion_check(modules)
    oauth_errors = _selector_oauth_boundary_check(modules)
    isolation_errors = _selector_isolation_check(modules)
    context_errors = _selector_context_check(modules)
    artifact_errors = _instruction_artifact_check(modules)
    unapproved_writes, persistence_errors = _selector_persistence_check(modules)
    hook_errors = _selector_hook_boundary_check(root)
    errors.update(sdk_errors)
    errors.update(runtime_sdk_errors)
    errors.update(process_errors)
    errors.update(recursion_errors)
    errors.update(oauth_errors)
    errors.update(isolation_errors)
    errors.update(context_errors)
    errors.update(artifact_errors)
    errors.update(persistence_errors)
    errors.update(hook_errors)
    return {
        "status": "fail" if errors else "pass",
        "selector_modules_checked": len(modules),
        "sdk_imports_checked": sdk_imports,
        "unapproved_selector_writes": unapproved_writes,
        "error_codes": sorted(errors),
    }


def _load_json(path: Path) -> Mapping[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, Mapping) else None


def _normalized_requirement(value: object) -> tuple[str, str] | None:
    if not isinstance(value, str):
        return None
    match = _REQUIREMENT_NAME.fullmatch(value.strip())
    if match is None:
        return None
    name = match.group(1).casefold().replace("_", "-").replace(".", "-")
    return name, match.group(2).replace(" ", "")


def _locked_dependency_names(package: Mapping[str, Any]) -> frozenset[str] | None:
    dependencies = package.get("dependencies", [])
    if not isinstance(dependencies, list):
        return None
    names: set[str] = set()
    for item in dependencies:
        if not isinstance(item, Mapping) or not isinstance(item.get("name"), str):
            return None
        names.add(str(item["name"]).casefold())
    return frozenset(names)


def _version_at_least(value: object, minimum: tuple[int, int]) -> bool:
    if not isinstance(value, str):
        return False
    parts = value.split(".")
    if len(parts) < 2 or not all(part.isdigit() for part in parts[:2]):
        return False
    return (int(parts[0]), int(parts[1])) >= minimum


def _version_in_range(value: object, minimum: tuple[int, int], exclusive_major: int) -> bool:
    if not _version_at_least(value, minimum) or not isinstance(value, str):
        return False
    major = value.split(".", 1)[0]
    return major.isdigit() and int(major) < exclusive_major


def _bounded_sbom_string(value: object) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= 128
        and "\x00" not in value
        and all(" " <= character <= "~" for character in value)
    )


def _dependency_check(root: Path) -> dict[str, Any]:  # noqa: C901  # Closed runtime allowlist.
    pyproject = root / "pyproject.toml"
    lockfile = root / "uv.lock"
    if not pyproject.is_file() or not lockfile.is_file():
        return {
            "status": "unavailable",
            "runtime_dependency_count": 0,
            "lockfile_present": lockfile.is_file(),
            "error_codes": ["dependency_metadata_missing"],
        }
    errors: set[str] = set()
    try:
        project = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        lock = tomllib.loads(lockfile.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError):
        return {
            "status": "unavailable",
            "runtime_dependency_count": 0,
            "lockfile_present": True,
            "error_codes": ["dependency_metadata_invalid"],
        }
    runtime = project.get("project", {}).get("dependencies", [])
    if not isinstance(runtime, list):
        errors.add("runtime_dependency_metadata_invalid")
        runtime = []
    parsed_runtime = [_normalized_requirement(value) for value in runtime]
    if any(item is None for item in parsed_runtime):
        errors.add("runtime_dependency_requirement_invalid")
    declared = {
        name: specifier
        for item in parsed_runtime
        if item is not None
        for name, specifier in (item,)
    }
    if len(declared) != len(parsed_runtime):
        errors.add("runtime_dependency_duplicate")
    if declared != _RUNTIME_REQUIREMENTS:
        errors.add("runtime_dependency_allowlist_invalid")
    packages = lock.get("package", [])
    if not isinstance(packages, list):
        errors.add("lock_package_table_invalid")
        packages = []
    root_packages = [
        item
        for item in packages
        if isinstance(item, Mapping) and item.get("name") == "opensocrates"
    ]
    if not root_packages:
        errors.add("root_package_missing_from_lock")
    else:
        for package in root_packages:
            if _locked_dependency_names(package) != frozenset(_RUNTIME_REQUIREMENTS):
                errors.add("locked_runtime_dependency_allowlist_invalid")
    locked_by_name = {
        str(item.get("name")).casefold(): item
        for item in packages
        if isinstance(item, Mapping) and isinstance(item.get("name"), str)
    }
    for name, expected in _RUNTIME_REQUIREMENTS.items():
        locked_package = locked_by_name.get(name)
        if locked_package is None:
            errors.add("selector_runtime_dependency_missing_from_lock")
            continue
        version = locked_package.get("version")
        if name in {"openai-codex", "openai-codex-cli-bin"} and version != expected[2:]:
            errors.add("selector_sdk_version_mismatch")
        if name == "pydantic" and not _version_at_least(version, (2, 12)):
            errors.add("selector_pydantic_version_invalid")
    return {
        "status": "fail" if errors else "pass",
        "runtime_dependency_count": len(runtime),
        "runtime_policy": "codex-selector-sdk-only",
        "lockfile_present": True,
        "locked_package_count": len(packages),
        "error_codes": sorted(errors),
    }


def _sbom_check(root: Path) -> dict[str, Any]:  # noqa: C901  # Closed SBOM closure contract.
    report = _load_json(root / "build" / "evidence" / "sbom.json")
    document = _load_json(root / "build" / "evidence" / "sbom.spdx.json")
    if report is None or document is None:
        return {
            "status": "unavailable",
            "spdx_valid": False,
            "error_codes": ["sbom_evidence_missing_or_invalid"],
        }
    errors: set[str] = set()
    if report.get("schema") != "opensocrates.sbom-evidence/1.0.0":
        errors.add("sbom_report_schema_invalid")
    if report.get("status") not in {"pass", "incomplete"}:
        errors.add("sbom_report_not_passing")
    runtime_entries = report.get("runtime_dependencies")
    if not isinstance(runtime_entries, list):
        errors.add("sbom_runtime_dependencies_invalid")
        runtime_entries = []
    reported_runtime_count = report.get("runtime_dependency_count")
    if type(reported_runtime_count) is not int or reported_runtime_count != len(runtime_entries):
        errors.add("sbom_runtime_dependency_count_invalid")
    runtime_versions: dict[str, str] = {}
    for entry in runtime_entries:
        if not isinstance(entry, Mapping):
            errors.add("sbom_runtime_dependencies_invalid")
            continue
        name = entry.get("name")
        version = entry.get("version")
        if (
            not isinstance(name, str)
            or not isinstance(version, str)
            or not _bounded_sbom_string(name)
            or not _bounded_sbom_string(version)
        ):
            errors.add("sbom_runtime_dependencies_invalid")
            continue
        normalized_name = name.casefold()
        if normalized_name in runtime_versions:
            errors.add("sbom_runtime_dependency_duplicate")
            continue
        runtime_versions[normalized_name] = version
    for name, expected in _RUNTIME_REQUIREMENTS.items():
        version = runtime_versions.get(name)
        if version is None:
            errors.add("sbom_selector_dependency_missing")
        elif name in {"openai-codex", "openai-codex-cli-bin"} and version != expected[2:]:
            errors.add("sbom_selector_dependency_version_invalid")
        elif name == "pydantic" and not _version_in_range(version, (2, 12), 3):
            errors.add("sbom_selector_dependency_version_invalid")
    if not report.get("lockfile_present"):
        errors.add("sbom_lockfile_missing")
    if document.get("spdxVersion") != "SPDX-2.3":
        errors.add("spdx_version_invalid")
    if not isinstance(document.get("packages"), list) or not isinstance(
        document.get("files"), list
    ):
        errors.add("spdx_shape_invalid")
    else:
        package_names = {
            value.get("name", "").casefold()
            for value in document["packages"]
            if isinstance(value, Mapping) and isinstance(value.get("name"), str)
        }
        if not set(runtime_versions).issubset(package_names):
            errors.add("spdx_runtime_dependency_missing")
    result = {
        "status": "fail" if errors else "pass",
        "spdx_valid": not errors,
        "runtime_dependency_count": len(runtime_entries),
        "package_count": len(document.get("packages", []))
        if isinstance(document.get("packages"), list)
        else 0,
        "artifact_count": len(document.get("files", []))
        if isinstance(document.get("files"), list)
        else 0,
        "error_codes": sorted(errors),
    }
    return result


def _launcher_command(value: object, host: str) -> bool:
    if not isinstance(value, str):
        return False
    prefix = "${PLUGIN_ROOT}"
    pieces = value.split()
    if len(pieces) == 4 and pieces[:3] == [f"{prefix}/bin/launch.sh", "hook", host]:
        return pieces[3] in _SAFE_LAUNCH_EVENTS
    return value == f"{prefix}/bin/launch.sh control {host}"


def _iter_command_values(value: object) -> Iterable[object]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key == "command":
                yield child
            yield from _iter_command_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_command_values(child)


def _codex_user_prompt_timeout_omitted(document: Mapping[str, Any]) -> bool:
    """Accept only a generated Codex UserPromptSubmit command without timeout."""

    hooks = document.get("hooks")
    if not isinstance(hooks, Mapping):
        return False
    handlers = hooks.get("UserPromptSubmit")
    if not isinstance(handlers, list) or not handlers:
        return False
    commands: list[Mapping[str, Any]] = []
    for handler in handlers:
        if not isinstance(handler, Mapping):
            return False
        nested = handler.get("hooks")
        if not isinstance(nested, list) or not nested:
            return False
        for command in nested:
            if not isinstance(command, Mapping) or not isinstance(command.get("command"), str):
                return False
            commands.append(command)
    return bool(commands) and all("timeout" not in command for command in commands)


def _launcher_check(root: Path) -> dict[str, Any]:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    base = root / "build" / "generated" / "plugins"
    if not base.is_dir():
        return {
            "status": "unavailable",
            "hosts_checked": 0,
            "commands_checked": 0,
            "invalid_commands": 0,
            "error_codes": ["generated_plugins_missing"],
        }
    hosts_checked = 0
    commands_checked = 0
    invalid = 0
    errors: set[str] = set()
    for host in sorted(_SAFE_HOSTS):
        hooks = base / host / "hooks" / "hooks.json"
        if not hooks.is_file():
            errors.add("generated_hooks_missing")
            continue
        document = _load_json(hooks)
        if document is None:
            errors.add("generated_hooks_invalid")
            continue
        hosts_checked += 1
        values = list(_iter_command_values(document))
        commands_checked += len(values)
        invalid += sum(not _launcher_command(value, host) for value in values)
        if host == "codex" and not _codex_user_prompt_timeout_omitted(document):
            errors.add("generated_codex_user_prompt_timeout_not_omitted")
        for path in (base / host / "commands", base / host / "skills"):
            if not path.is_dir():
                errors.add("generated_launcher_surface_missing")
                continue
            for candidate in path.rglob("*.md"):
                try:
                    text = candidate.read_text(encoding="utf-8")
                except (OSError, UnicodeError):
                    errors.add("generated_launcher_surface_unreadable")
                    continue
                prefix = "${PLUGIN_ROOT}"
                for line in text.splitlines():
                    if "launch.sh" not in line:
                        continue
                    literal = line.strip().strip("`")
                    if literal.startswith(prefix + "/bin/launch.sh"):
                        commands_checked += 1
                        if literal != f"{prefix}/bin/launch.sh control {host}":
                            invalid += 1
    if invalid:
        errors.add("generated_launcher_literal_invalid")
    return {
        "status": "fail" if errors else "pass",
        "hosts_checked": hosts_checked,
        "commands_checked": commands_checked,
        "invalid_commands": invalid,
        "error_codes": sorted(errors),
    }


def _optional_tool(name: str) -> dict[str, Any]:
    executable = shutil.which(name)
    if executable is None:
        return {"status": "unavailable", "available": False, "executed": False}
    try:
        completed = subprocess.run(
            [executable, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return {"status": "unavailable", "available": True, "executed": False}
    return {
        "status": "available" if completed.returncode == 0 else "unavailable",
        "available": True,
        "executed": False,
        "version_probe_exit_code": completed.returncode,
    }


def scan(root: Path) -> dict[str, Any]:
    production = _scan_production(root)
    dependencies = _dependency_check(root)
    sbom = _sbom_check(root)
    selector_boundary = _selector_boundary_check(root)
    launchers = _launcher_check(root)
    core = (production, dependencies, sbom, selector_boundary, launchers)
    statuses = {str(item.get("status")) for item in core}
    status = (
        "fail" if "fail" in statuses else "unavailable" if "unavailable" in statuses else "pass"
    )
    errors: set[str] = set()
    for item in core:
        values = item.get("error_codes", [])
        if isinstance(values, list):
            errors.update(str(value) for value in values)
    return {
        "schema": SCHEMA,
        "generated_at": _iso_now(),
        "status": status,
        "checks": {
            "production": production,
            "dependencies": dependencies,
            "sbom": sbom,
            "selector_boundary": selector_boundary,
            "generated_launchers": launchers,
        },
        "optional_tools": {
            name: _optional_tool(name) for name in ("bandit", "semgrep", "pip-audit")
        },
        "error_codes": sorted(errors),
        "privacy": {
            "source_content_recorded": False,
            "absolute_paths_recorded": False,
            "environment_recorded": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--report", default="build/evidence/security-scan.json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = _resolve(Path.cwd(), args.root)
    report_path = _resolve(root, args.report)
    try:
        report = scan(root)
    except (OSError, SecurityScanError) as exc:
        report = {
            "schema": SCHEMA,
            "generated_at": _iso_now(),
            "status": "unavailable",
            "error_codes": [type(exc).__name__],
            "privacy": {
                "source_content_recorded": False,
                "absolute_paths_recorded": False,
                "environment_recorded": False,
            },
        }
    _write_json(report_path, report)
    try:
        display_report = report_path.relative_to(root).as_posix()
    except ValueError:
        display_report = report_path.name
    print(
        f"security-scan: {str(report.get('status', 'unavailable')).upper()} report={display_report}"
    )
    return {"pass": 0, "fail": 1, "unavailable": 2}.get(str(report.get("status")), 2)


if __name__ == "__main__":
    raise SystemExit(main())
