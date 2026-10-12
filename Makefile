GO ?= go
DEV := $(GO) run ./src/opensocrates/cmd/opensocrates-dev
TARGET ?= darwin-arm64

.PHONY: bootstrap format format-check lint typecheck generate generated-check content-check adjudication-check docs-check governance-check package-check security-scan smoke installer-check codex-hook-timing package release-check version windows-check macos-check

bootstrap:
	@$(GO) mod download

format:
	@$(DEV) format

format-check:
	@$(DEV) format --check

lint:
	@$(GO) vet ./src/opensocrates/...
	@$(DEV) check boundaries

typecheck:
	@$(GO) vet ./src/opensocrates/...

generate:
	@$(DEV) generate

generated-check:
	@$(DEV) check generated --report build/evidence/generated.json

content-check:
	@$(DEV) check content --report build/evidence/content.json

adjudication-check:
	@$(DEV) check adjudication --report build/evidence/adjudication.json

docs-check:
	@$(DEV) check docs --report build/evidence/links.json

governance-check:
	@$(DEV) check governance --report build/evidence/governance.json

package-check: generate
	@$(DEV) check package --report build/evidence/package.json

security-scan: package
	@$(DEV) sbom --package dist/native/$(TARGET) --output build/evidence/sbom.json
	@$(DEV) check security --report build/evidence/security-scan.json

smoke:
	@$(GO) test ./src/opensocrates/...

installer-check:
	@$(GO) test ./src/opensocrates/internal/lifecycle ./src/opensocrates/internal/platform ./src/opensocrates/internal/update

codex-hook-timing:
	@$(DEV) acceptance timing --package dist/native/$(TARGET)/packages/codex --report build/evidence/codex-hook-timing.json

package:
	@$(DEV) build --target $(TARGET) --output dist/runtime
	@$(DEV) package --target $(TARGET) --runtime-root dist/runtime --output dist/native/$(TARGET)

release-check:
	@$(DEV) release-check --target $(TARGET) --package dist/native/$(TARGET)

windows-check:
	@$(DEV) check windows --report build/evidence/windows-package.json

macos-check:
	@$(DEV) check macos-hosts --report build/evidence/macos-package.json

version:
	@$(GO) run ./src/opensocrates/cmd/opensocrates version --json
