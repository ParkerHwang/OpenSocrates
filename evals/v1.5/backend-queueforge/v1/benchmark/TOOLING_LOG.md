# Preparation verification and repairs

- Initial protocol read used root BENCHMARK.md; file absent. Re-read actual protocol/BENCHMARK.md before implementation.
- Initial Go source creation omitted the requested workdir and landed in an agent-created OpenSource/benchmark/loadgen. Next build reported missing target loadgen directory. Moved only those owned newly-created files into this benchmark/loadgen and removed the empty accidental directory. No sibling source was read or edited.
- First build and mock selfcheck passed. Subsequent tightened body/result/identity controls and seed WAL/reopen checks compiled successfully.
- Adding per-request tenant field initially produced `unknown field Tenant in struct literal of type Sample`. Added the missing Sample field, reran gofmt/build/race tests/selfcheck successfully. Failed build retained here; no candidate rerun occurred.
- Final preparation checks: Go1.26.3 darwin/arm64; go test -race ./... passed; go build passed; loadgen --selfcheck passed; Python unittest3controls passed; Python py_compile passed.
- No candidate/server implementation was executed during preparation. Seed creation and full candidate cell execution remain runtime operations for root after freeze. The tiny mock validates tooling behavior only.

- Before freeze, primary review identified cohort completions during drain being divided by the shorter measurement window. Added finish offsets, separate cohort/window/drain counts and window-only RPS. The200ms slow-read mock verifies10measure-cohort completions all in drain produce0window throughput. Warmup start-cohort labels remain unchanged.
- Added120s absolute seed preparation work deadline and2s absolute public request deadline with socket shutdown; Python trickle-body control passed and verifies failure within0.5s for a0.15s deadline. Python controls now4tests. No candidate calls occurred during this correction.
