"""Independent expected observations, authored and frozen before outcome calls."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading


def equal(actual, expected):
    assert actual == expected, f"expected {expected!r}; observed {actual!r}"


def raises(kind, action, code=None):
    try:
        action()
    except kind as error:
        if code is not None:
            equal(error.code, code)
        return
    label = kind.__name__ if isinstance(kind, type) else "/".join(x.__name__ for x in kind)
    raise AssertionError(f"expected {label}")


def contracts():
    p = importlib.import_module("quotadesk.policy")
    api = importlib.import_module("quotadesk.api")
    cli = importlib.import_module("quotadesk.cli")

    def fresh():
        store = p.Store(100)
        store.seed("alpha", 40, "existing")
        return store

    def patch_values():
        store = fresh()
        payload = {"expected_revision": 1, "max_jobs": 0, "label": None}
        old = deepcopy(payload)
        result = p.apply_policy(store, "alpha", payload)
        equal(result, {"namespace": "alpha", "revision": 2, "configured_max_jobs": 0,
                       "effective_max_jobs": 0, "label": ""})
        equal(payload, old)
        equal(store.audit_entries(), [{"namespace": "alpha", "old_revision": 1, "new_revision": 2}])

    def inheritance():
        store = fresh()
        result = p.apply_policy(store, "alpha", {"expected_revision": 1, "max_jobs": None})
        equal(result["effective_max_jobs"], 100)
        equal(result["configured_max_jobs"], None)
        store.default_limit = 90
        equal(store.read("alpha")["effective_max_jobs"], 90)

    def no_op():
        store = fresh()
        for payload in ({"expected_revision": 1}, {"expected_revision": 1, "max_jobs": 40, "label": "existing"}):
            equal(p.apply_policy(store, "alpha", payload)["revision"], 1)
        equal(store.audit_entries(), [])

    def strict_values():
        for value in [True, False, "0", 2.0, -1, 1001, [], {}]:
            store = fresh()
            raises(p.PolicyError, lambda: p.apply_policy(store, "alpha", {"expected_revision": 1, "max_jobs": value}), "invalid")
            equal(store.read("alpha")["revision"], 1)
            equal(store.audit_entries(), [])

    def shape_and_revision():
        for body in [None, [], {}, {"expected_revision": True}, {"expected_revision": 0},
                     {"expected_revision": "1"}, {"expected_revision": 1, "unexpected": 1}]:
            raises(p.PolicyError, lambda: p.apply_policy(fresh(), "alpha", body), "invalid")
        raises(p.PolicyError, lambda: p.apply_policy(fresh(), "alpha", {"expected_revision": 5, "max_jobs": True}), "invalid")

    def atomic_rejection():
        store = fresh()
        before = store.read("alpha")
        raises(p.PolicyError, lambda: p.apply_policy(store, "alpha", {"expected_revision": 1, "max_jobs": 80, "label": "x" * 41}), "invalid")
        equal(store.read("alpha"), before)
        equal(store.audit_entries(), [])

    def conflicts_and_missing():
        store = fresh()
        p.apply_policy(store, "alpha", {"expected_revision": 1, "max_jobs": 12})
        raises(p.PolicyError, lambda: p.apply_policy(store, "alpha", {"expected_revision": 1, "max_jobs": 12}), "conflict")
        raises(p.PolicyError, lambda: p.apply_policy(store, "absent", {"expected_revision": 1}), "not_found")
        equal(len(store.audit_entries()), 1)

    def independent_results():
        store = fresh()
        row = p.apply_policy(store, "alpha", {"expected_revision": 1, "label": "next"})
        row["label"] = "corruption"
        entries = store.audit_entries()
        entries[0]["new_revision"] = 900
        equal(store.read("alpha")["label"], "next")
        equal(store.audit_entries()[0]["new_revision"], 2)

    def legacy_and_consumer():
        store = fresh()
        equal(cli.import_line(store, "b", "0"), "unlimited")
        equal(cli.import_line(store, "c", "12"), "limit=12")
        equal(cli.import_line(store, "d", None), "limit=100")
        equal(cli.render_record(p.apply_policy(store, "alpha", {"expected_revision": 1, "label": "done"})), "alpha@2: 40 (done)")

    def adapter():
        store = fresh()
        equal(api.handle_edit(store, "absent", {"expected_revision": 1}), (404, {"error": "not_found"}))
        equal(api.handle_edit(store, "alpha", {"expected_revision": 99}), (409, {"error": "conflict"}))
        equal(api.handle_edit(store, "alpha", {"expected_revision": True}), (400, {"error": "invalid"}))
        equal(api.handle_edit(store, "alpha", {"expected_revision": 1, "max_jobs": 1000})[0], 200)

    return [patch_values, inheritance, no_op, strict_values, shape_and_revision,
            atomic_rejection, conflicts_and_missing, independent_results, legacy_and_consumer, adapter]


def transitions():
    p = importlib.import_module("parcelseal.publisher")
    t = importlib.import_module("parcelseal.transport")

    def run(action):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            transport = t.FileTransport(root / "effects")
            instance = p.Publisher(root / "publisher.sqlite", transport)
            try:
                action(instance, transport, root)
            finally:
                instance.close()

    def delivered():
        def check(instance, transport, _):
            first = instance.publish("a", "x", b"body")
            equal(set(first), {"status", "receipt"})
            equal(first["status"], "delivered")
            equal(instance.publish("a", "x", b"body"), first)
            equal(len(transport.calls), 1)
            equal(transport.effect_count(), 1)
        run(check)

    def invalid():
        def check(instance, transport, _):
            for args in [("", "x", b"b"), ("a", "", b"b"), ("a", "x", "string"),
                         ("a"*81, "x", b"b"), ("a", "x"*81, b"b"), (True, "x", b"b")]:
                raises(ValueError, lambda: instance.publish(*args))
            equal(transport.calls, [])
        run(check)

    def conflict_scope():
        def check(instance, transport, _):
            instance.publish("a", "x", b"body")
            raises(p.PublishConflict, lambda: instance.publish("a", "x", b"different"))
            instance.publish("b", "x", b"body")
            instance.publish("a", "y", b"body")
            equal(transport.effect_count(), 3)
            equal(len(transport.calls), 3)
        run(check)

    def timeout_after():
        def check(instance, transport, _):
            transport.fault = "timeout-after"
            equal(instance.publish("a", "x", b"body"), {"status": "pending", "receipt": None})
            equal(transport.effect_count(), 1)
            equal(instance.publish("a", "x", b"body")["status"], "delivered")
            equal(len(transport.calls), 1)
        run(check)

    def timeout_before():
        def check(instance, transport, _):
            transport.fault = "timeout-before"
            equal(instance.publish("a", "x", b"body")["status"], "pending")
            equal(transport.effect_count(), 0)
            equal(instance.publish("a", "x", b"body")["status"], "delivered")
            equal(len(transport.calls), 2)
            equal(transport.effect_count(), 1)
        run(check)

    def unknown_lookup():
        def check(instance, transport, _):
            transport.fault = "timeout-after"
            instance.publish("a", "x", b"body")
            transport.lookup_unavailable = True
            equal(instance.publish("a", "x", b"body")["status"], "pending")
            raises(p.PublishConflict, lambda: instance.publish("a", "x", b"different"))
            equal(len(transport.calls), 1)
            transport.lookup_unavailable = False
            equal(instance.publish("a", "x", b"body")["status"], "delivered")
        run(check)

    def rejected():
        def check(instance, transport, _):
            transport.fault = "reject"
            equal(instance.publish("a", "x", b"body"), {"status": "rejected", "receipt": None})
            equal(instance.publish("a", "x", b"body")["status"], "rejected")
            raises(p.PublishConflict, lambda: instance.publish("a", "x", b"different"))
            equal(len(transport.calls), 1)
            equal(transport.effect_count(), 0)
        run(check)

    def restart():
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            transport = t.FileTransport(root / "effects")
            one = p.Publisher(root / "state.sqlite", transport)
            transport.fault = "timeout-after"
            equal(one.publish("a", "x", b"body")["status"], "pending")
            one.close()
            equal(transport.closed, False)
            two = p.Publisher(root / "state.sqlite", transport)
            try:
                equal(two.publish("a", "x", b"body")["status"], "delivered")
                equal(len(transport.calls), 1)
            finally:
                two.close()

    def alias():
        def check(instance, transport, _):
            first = instance.publish("a", "x", b"body")
            first["receipt"]["meta"]["bytes"] = 999
            equal(instance.publish("a", "x", b"body")["receipt"]["meta"]["bytes"], 4)
        run(check)

    def concurrent():
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            transport = t.FileTransport(root / "effects")
            pair = [p.Publisher(root / "state.sqlite", transport) for _ in range(2)]
            barrier = threading.Barrier(2)
            def action(index):
                barrier.wait(timeout=8)
                return pair[index].publish("a", "same", b"body")
            try:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(action, [0, 1]))
                assert all(x["status"] in {"pending", "delivered"} for x in results)
                equal(pair[0].publish("a", "same", b"body")["status"], "delivered")
                equal(transport.effect_count(), 1)
                pair[1].publish("a", "other", b"body")
                equal(transport.effect_count(), 2)
            finally:
                for instance in pair:
                    instance.close()

    return [delivered, invalid, conflict_scope, timeout_after, timeout_before,
            unknown_lookup, rejected, restart, alias, concurrent]


def ownership(workspace, followup):
    t = importlib.import_module("batchflow.templates")
    r = importlib.import_module("batchflow.runs")
    cli = importlib.import_module("batchflow.cli")

    def stages():
        return [{"name": "parse", "workers": 2, "options": {"labels": ["base"], "nested": {"limit": 4}}},
                {"name": "merge", "workers": 3}]

    def registry():
        value = t.TemplateRegistry()
        value.put("alpha", stages())
        return value

    def run(action):
        with tempfile.TemporaryDirectory() as directory:
            reg = registry()
            action(r.RunStore(directory, reg), reg, Path(directory))

    def create_and_load():
        def check(store, reg, directory):
            value = store.create("alpha")
            fields = {"run_id", "template_name", "source_revision", "stages", "total_workers"}
            if followup:
                fields.add("factor")
            equal(set(value), fields)
            equal(value["source_revision"], 1)
            equal(value["total_workers"], 5)
            equal(value["template_name"], "alpha")
            equal(r.RunStore(directory, reg).load(value["run_id"]), value)
        run(check)

    def input_alias():
        source = stages()
        reg = t.TemplateRegistry()
        reg.put("alpha", source)
        source[0]["workers"] = 44
        source[0]["options"]["labels"].append("mutated")
        equal(reg.describe("alpha")["total_workers"], 5)
        equal(reg.describe("alpha")["stages"][0]["options"]["labels"], ["base"])

    def read_alias():
        reg = registry()
        value = reg.describe("alpha")
        value["stages"][0]["options"]["nested"]["limit"] = 999
        t.Monitor(reg, "alpha").as_dict()["stages"][1]["workers"] = 62
        equal(reg.describe("alpha")["total_workers"], 5)
        equal(reg.describe("alpha")["stages"][0]["options"]["nested"]["limit"], 4)

    def result_alias():
        def check(store, _, __):
            value = store.create("alpha")
            identifier = value["run_id"]
            value["stages"][0]["options"]["labels"].append("changed")
            loaded = store.load(identifier)
            equal(loaded["stages"][0]["options"]["labels"], ["base"])
            loaded["stages"][0]["workers"] = 60
            equal(store.load(identifier)["stages"][0]["workers"], 2)
        run(check)

    def live_and_retained():
        def check(store, reg, _):
            monitor = t.Monitor(reg, "alpha")
            old = store.create("alpha")
            reg.put("alpha", [{"name": "new", "workers": 8}])
            equal(monitor.as_dict()["total_workers"], 8)
            retained = store.load(old["run_id"])
            equal(retained["total_workers"], 5)
            equal(retained["source_revision"], 1)
            new = store.create("alpha")
            equal(new["total_workers"], 8)
            equal(new["source_revision"], 2)
        run(check)

    def no_partial_files():
        def check(store, reg, directory):
            first = store.create("alpha")
            before = {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()}
            try:
                store.create("absent")
            except (KeyError, ValueError):
                pass
            else:
                raise AssertionError("missing template accepted")
            original = reg.describe
            reg.describe = lambda _: {"revision": 2, "stages": [{"name": "bad", "workers": True}], "total_workers": 1}
            try:
                try:
                    store.create("alpha")
                except (ValueError, TypeError):
                    pass
                else:
                    raise AssertionError("malformed template accepted")
            finally:
                reg.describe = original
            equal({str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()}, before)
            equal(store.load(first["run_id"])["total_workers"], 5)
        run(check)

    def legacy():
        def check(store, reg, directory):
            subprocess.run([sys.executable, str(workspace/'legacy/produce_v1.py'), str(directory)], check=True)
            path = directory / "legacy-1.json"
            before = path.read_bytes()
            reg.put("alpha", [{"name": "current", "workers": 12}])
            value = store.load("legacy-1")
            equal(value["source_revision"], None)
            equal(value["total_workers"], 3)
            equal(value["stages"][0]["options"]["labels"], ["historic"])
            if followup:
                equal(value["factor"], 1)
            equal(path.read_bytes(), before)
        run(check)

    def identities():
        def check(store, reg, directory):
            first = store.create("alpha")
            second = r.RunStore(directory, reg).create("alpha")
            assert first["run_id"] != second["run_id"]
            equal(store.load(first["run_id"])["total_workers"], 5)
        run(check)

    def consumers():
        def check(store, _, __):
            value = store.create("alpha")
            expected = f"alpha:{value['run_id']} workers=5"
            equal(store.export(value["run_id"]), expected)
            equal(cli.show_run(store, value["run_id"]), expected)
        run(check)

    def independent_total():
        def check(store, reg, _):
            reg.put("alpha", [{"name": "x", "workers": 3}, {"name": "y", "workers": 9}])
            equal(store.create("alpha")["total_workers"], 12)
            equal(t.Monitor(reg, "alpha").as_dict()["total_workers"], 12)
        run(check)

    checks = [create_and_load, input_alias, read_alias, result_alias, live_and_retained,
              no_partial_files, legacy, identities, consumers, independent_total]
    if followup:
        def scaling():
            def check(store, reg, _):
                old = store.create("alpha")
                value = store.create("alpha", factor=2)
                equal(value["factor"], 2)
                equal(value["total_workers"], 10)
                equal([x["workers"] for x in value["stages"]], [4, 6])
                equal(reg.describe("alpha")["total_workers"], 5)
                equal(store.load(old["run_id"])["total_workers"], 5)
            run(check)

        def invalid_factor():
            def check(store, _, directory):
                for factor in [True, False, 0, 5, 2.0, "2", None]:
                    raises((ValueError, TypeError), lambda: store.create("alpha", factor=factor))
                equal([p for p in directory.rglob('*.json')], [])
            run(check)

        def overflow_atomic():
            def check(store, reg, directory):
                reg.put("alpha", [{"name": "large", "workers": 40}])
                raises((ValueError, TypeError), lambda: store.create("alpha", factor=2))
                equal(reg.describe("alpha")["total_workers"], 40)
                equal([p for p in directory.rglob('*.json')], [])
            run(check)

        def pre_factor_encoding():
            def check(store, _, directory):
                record = {"run_id": "pre-factor", "template_name": "alpha", "source_revision": 7,
                          "stages": stages(), "total_workers": 5}
                path = directory / "pre-factor.json"
                path.write_text(json.dumps(record))
                before = path.read_bytes()
                value = store.load("pre-factor")
                equal(value["factor"], 1)
                equal(value["source_revision"], 7)
                equal(value["total_workers"], 5)
                equal(path.read_bytes(), before)
            run(check)
        checks += [scaling, invalid_factor, overflow_atomic, pre_factor_encoding]
    return checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("task", choices=("contracts", "transitions", "ownership"))
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--followup", action="store_true")
    args = parser.parse_args()
    sys.path.insert(0, str(args.workspace.resolve()))
    results = []
    try:
        checks = contracts() if args.task == "contracts" else transitions() if args.task == "transitions" else ownership(args.workspace.resolve(), args.followup)
    except Exception as error:
        print(json.dumps({"setup_error": f"{type(error).__name__}: {error}", "checks": [], "passed": 0, "total": 10 if not args.followup else 14}))
        return 1
    for check in checks:
        try:
            check()
            results.append({"id": check.__name__, "passed": True})
        except Exception as error:
            results.append({"id": check.__name__, "passed": False, "error": f"{type(error).__name__}: {error}"})
    value = {"checks": results, "passed": sum(x["passed"] for x in results), "total": len(results)}
    print(json.dumps(value, ensure_ascii=False))
    return 0 if value["passed"] == value["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
