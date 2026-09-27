# Frozen independent acceptance fixtures

Owner: orchestration_verifier, separate from design author, implementation maker and code reviewer. This directory is external to the repository and contains only synthetic fixtures, independent oracles, and verification evidence. No live model calls, production writes, account actions or real enrollment are authorized for this verifier. Parent runs the product adapter after freeze.

Baseline: `edab8f8d5c8434a705e706422ce5e8d6dc540e32`. Accepted contract SHA-256: `a7b8264416f89d1b8aa9d0aa7e95366337e0ab42e10c755a6f80e3b606bade99`.

## Independently stipulated expectations

- Software design -> implementation: latest eligible date gives 8, not max cost 10. Six fixed cases distinguish absent field, explicit null, zero, no eligible date and input order. `fixtures/defective_pricing.py` is the deliberately defective seed; it must fail independent review, then the designated maker repairs it, and the changed bytes require fresh review and execution verification.
- Data -> document: A=2*3=6, B=5*7=35, total=41. Multiplying sums gives 70 and must fail. The report binds exact source and calculation hashes and reconciles table/narrative.
- Continuation: long accepted constraint is 2185 characters / 2185 bytes. Its full bytes govern both maker and reviewer. Current-attempt self-evaluation, stale claims, deleted and unrelated scoped records are excluded as specified. Absent/disabled/unavailable memory uses explicit bounded handoff without initialization.

## Oracle arguments in a prepared candidate directory

The parent declares each oracle and fixture as a source so the adapter copies it under `inputs/<id>/<basename>`. The following argument patterns are fixed before live calls; substitute the supported Python executable path only:

- `<python> -B inputs/design-oracle/check_design.py design.json`
- `<python> -B inputs/cost-oracle/check_cost.py pricing.py inputs/cost-cases/cost_cases.json`
- `<python> -B inputs/calculation-oracle/check_calculation.py calculation.json inputs/country-source/country_effects.json`
- `<python> -B inputs/report-oracle/check_report.py report.md calculation.json inputs/country-source/country_effects.json`

Run approved checks only through the declared read-only Codex sandbox with network disabled. They require no writes. Parent must preserve actual command/state receipts and rehash candidate/source inputs after every check. The scripts import only Python standard library and never import OpenSocrates implementation helpers.

`negative_cases.json` freezes runtime expectations before product API stabilization. Wire-format requests are parent-owned and may adapt field names without changing expected behavior. `baseline_identity.json` records all committed old schema/canonical method bytes. `oracle_self_tests/` are checker tests only, never product acceptance evidence. A checked fixture does not establish quality benefit, platform support, account isolation, backend attestation, install state, publication or user acceptance.
