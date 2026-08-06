PYTHON ?= $(shell if command -v uv >/dev/null 2>&1; then uv python find 3.12; else command -v python3; fi)
PYTHONPATH := src
ROOT := $(CURDIR)

.PHONY: bootstrap format format-check lint typecheck generate generated-check content-check docs-check package-check security-scan smoke installer-check package release-check version

bootstrap:
	@PYTHONPATH="$(PYTHONPATH)" "$(PYTHON)" -c 'import pathlib,sys,tomllib; assert sys.version_info[:2] == (3, 12), sys.version; root=pathlib.Path("."); project=tomllib.loads((root/"pyproject.toml").read_text()); lock=tomllib.loads((root/"uv.lock").read_text()); expected=("openai-codex==0.144.4", "openai-codex-cli-bin==0.144.4", "pydantic>=2.12,<3"); assert tuple(project["project"].get("dependencies", [])) == expected; packages={item.get("name"): item for item in lock.get("package", []) if isinstance(item, dict) and isinstance(item.get("name"), str)}; assert packages.get("openai-codex", {}).get("version") == "0.144.4"; assert packages.get("openai-codex-cli-bin", {}).get("version") == "0.144.4"; pydantic=packages.get("pydantic", {}).get("version", ""); assert pydantic.startswith("2.") and tuple(map(int, pydantic.split(".")[:2])) >= (2, 12); assert packages.get("pydantic-core", {}).get("version"); opensocrates=packages.get("opensocrates", {}); direct={item.get("name") for item in opensocrates.get("dependencies", []) if isinstance(item, dict)}; assert {"openai-codex", "openai-codex-cli-bin", "pydantic"} <= direct; print("Python 3.12 and locked Codex SDK/runtime metadata ready")'
	@if command -v uv >/dev/null 2>&1; then uv lock --check && uv sync --locked --no-install-project; else "$(PYTHON)" -m mypy --version && "$(PYTHON)" -m ruff --version; fi

format:
	@if command -v uv >/dev/null 2>&1; then uv run --locked --no-sync ruff format src tools; else "$(PYTHON)" -m ruff format src tools; fi

format-check:
	@if command -v uv >/dev/null 2>&1; then uv run --locked --no-sync ruff format --check src tools; else "$(PYTHON)" -m ruff format --check src tools; fi

lint: typecheck
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) tools/check_import_boundaries.py
	@if command -v uv >/dev/null 2>&1; then uv run --locked --no-sync ruff check src tools; else "$(PYTHON)" -m ruff check src tools; fi

typecheck:
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m compileall -q src tools
	@if command -v uv >/dev/null 2>&1; then MYPYPATH=$(PYTHONPATH) uv run --locked --no-sync mypy src; else MYPYPATH=$(PYTHONPATH) "$(PYTHON)" -m mypy src; fi

generate:
	@PYTHONPATH="$(PYTHONPATH)" "$(PYTHON)" tools/generate_schemas.py
	@PYTHONPATH="$(PYTHONPATH)" "$(PYTHON)" tools/validate_content.py --output "$(ROOT)/content/compiled-content.bundle.json" --reasoning-projections-output "$(ROOT)/content/compiled-reasoning-content.bundle.json"
	@PYTHONPATH="$(PYTHONPATH)" "$(PYTHON)" tools/build_plugins.py --root "$(ROOT)" --host claude --runtime-root "$(ROOT)/dist/runtime" --output "$(ROOT)/build/generated/plugins/claude" >/dev/null
	@PYTHONPATH="$(PYTHONPATH)" "$(PYTHON)" tools/build_plugins.py --root "$(ROOT)" --host codex --runtime-root "$(ROOT)/dist/runtime" --output "$(ROOT)/build/generated/plugins/codex" >/dev/null

generated-check:
	@set -eu; tmp="$$(mktemp -d)"; trap 'rm -rf "$$tmp"' EXIT; out="$$tmp/generated output — 日本語"; mkdir -p "$$out"; \
	PYTHONPATH="$(PYTHONPATH)" "$(PYTHON)" tools/generate_schemas.py --output-dir "$$out/schemas"; \
	PYTHONPATH="$(PYTHONPATH)" "$(PYTHON)" tools/validate_content.py --output "$$out/content/compiled-content.bundle.json" --reasoning-projections-output "$$out/content/compiled-reasoning-content.bundle.json"; \
	diff -ru "$(ROOT)/schemas/v1" "$$out/schemas/v1"; diff -u "$(ROOT)/content/compiled-content.bundle.json" "$$out/content/compiled-content.bundle.json"; diff -u "$(ROOT)/content/compiled-reasoning-content.bundle.json" "$$out/content/compiled-reasoning-content.bundle.json"; \
	echo "generated-check: byte-identical schemas and content bundles"

content-check:
	@PYTHONPATH="$(PYTHONPATH)" "$(PYTHON)" tools/validate_content.py --output "$(ROOT)/content/compiled-content.bundle.json" --reasoning-projections-output "$(ROOT)/content/compiled-reasoning-content.bundle.json"

docs-check:
	@PYTHONPATH="$(PYTHONPATH)" "$(PYTHON)" tools/check_links.py --root "$(ROOT)" \
		--path README.md \
		--path README.ko.md \
		--path CHANGELOG.md \
		--path CONTRIBUTING.md \
		--path SECURITY.md \
		--path CODE_OF_CONDUCT.md \
		--path .github/release-notes \
		--report build/evidence/links.json

package-check: generate
	@PYTHONPATH="$(PYTHONPATH)" "$(PYTHON)" tools/check_packaged_launcher.py --root "$(ROOT)" --report build/evidence/packaged-launcher.json
	@PYTHONPATH="$(PYTHONPATH)" "$(PYTHON)" tools/check_package_docs.py --root "$(ROOT)" --report build/evidence/package-docs.json

security-scan: generate
	@set -eu; set -- --artifact content/compiled-content.bundle.json --artifact content/compiled-reasoning-content.bundle.json; for artifact in $$(find "$(ROOT)/dist/runtime" -type f -name opensocrates-runtime -perm -111 2>/dev/null); do set -- "$$@" --artifact "$${artifact#$(ROOT)/}"; done; for artifact in "$(ROOT)"/dist/opensocrates-*.zip; do if [ -f "$$artifact" ]; then set -- "$$@" --artifact "$${artifact#$(ROOT)/}"; fi; done; PYTHONPATH="$(PYTHONPATH)" "$(PYTHON)" tools/build_sbom.py --root "$(ROOT)" --output build/evidence/sbom.spdx.json --report build/evidence/sbom.json "$$@"
	@PYTHONPATH="$(PYTHONPATH)" "$(PYTHON)" tools/security_scan.py --root "$(ROOT)" --report build/evidence/security-scan.json

smoke:
	@PYTHONPATH="$(PYTHONPATH)" "$(PYTHON)" tools/smoke_product.py
	@PYTHONPATH="$(PYTHONPATH)" "$(PYTHON)" tools/check_selector.py
	@PYTHONPATH="$(PYTHONPATH)" "$(PYTHON)" tools/check_claude.py

installer-check:
	@npm test
	@npm pack --dry-run

package:
	@if command -v uv >/dev/null 2>&1; then PYTHONPATH="$(PYTHONPATH)" uv run --locked --group build python tools/release_check.py --root "$(ROOT)" --assemble; else PYTHONPATH="$(PYTHONPATH)" "$(PYTHON)" tools/release_check.py --root "$(ROOT)" --assemble; fi

release-check:
	@if command -v uv >/dev/null 2>&1; then PYTHONPATH="$(PYTHONPATH)" uv run --locked --group build python tools/release_check.py --root "$(ROOT)" --assemble --report build/evidence/release-check.json; else PYTHONPATH="$(PYTHONPATH)" "$(PYTHON)" tools/release_check.py --root "$(ROOT)" --assemble --report build/evidence/release-check.json; fi

version:
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m opensocrates version --json
