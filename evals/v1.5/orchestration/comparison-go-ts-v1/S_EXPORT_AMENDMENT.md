# S24 post-call evidence export

The original frozen generic `export.py` looks for `external-qualification/`,
the O24 directory. The frozen S24 serial qualifier writes
`external-qualification-S/`. Running generic export alone would silently omit
S's external design/API/browser/performance receipts. This is an export-layer
omission, not a subject or checker failure; neither frozen source nor any
candidate will be changed to fix it.

`export_s.py` is a versioned post-call exporter. It loads the exact S execution
checkout's freeze verifier, requires all 24 cells to be terminal or explicitly
failed at startup, binds each included synthetic artifact to declared owned
paths and original native version hashes, and includes only the indexed
`external-qualification-S` root index and exact cell/variant receipts. It
also admits the frozen single-author `versions/single/v1/` copy only for A/B,
requiring exact equality with their returned artifact bytes; C/D published
files must equal the union of actually native-qualified unit versions.
Every indexed variant must match the retained native response and bundle hash.
The exporter rejects symlinks, unindexed receipts, candidate copies, auth, private oracle,
browser profiles, binaries, logs, transcripts, raw tool output and exports
inside the frozen checkout or original results. A manifest hashes every ZIP
member. It does **not** run a model, replay a candidate, regrade an artifact or
change the frozen S browser limitation.

The intended output is
`/private/tmp/opensocrates-go-ts-s24-export-v1-20260928.zip`. Execute only
after the separate frozen S24 qualifier has produced its terminal index:

```sh
PYTHONPATH=/private/tmp/opensocrates-go-ts-s24-execution-20260928/src \
  /Users/parkerhwang/.local/share/uv/python/cpython-3.14.4-macos-aarch64-none/bin/python3 -B \
  evals/v1.5/orchestration/comparison-go-ts-v1/export_s.py \
  --results /private/tmp/opensocrates-go-ts-s24-results-20260928 \
  --freeze /private/tmp/opensocrates-go-ts-s24-freeze-20260928.json \
  --freeze-sha256 3973a93cf491030d3aac47cfe4748c2a70b67d43ebed39b879d9253e4a92f815 \
  --output /private/tmp/opensocrates-go-ts-s24-export-v1-20260928.zip
```

Eight synthetic path, lineage and exact-receipt controls pass without an
outcome call; native candidate/path lineage also matches 288 files across 20
completed S candidate directories at the preparation checkpoint. Audit the
final source hash and ZIP membership before
claiming a portable S evidence package. S external qualification remains
pending until every S episode has a terminal or explicit unknown marker.
