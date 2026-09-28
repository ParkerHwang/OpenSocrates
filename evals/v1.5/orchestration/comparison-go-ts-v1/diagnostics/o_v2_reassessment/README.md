# O v2 post-call representation diagnostic

This is a separate, unblinded analysis of **unchanged** O24 artifacts. It does
not edit the frozen O24 execution checkout, the original 28-row external index,
the original portable ZIP, any candidate artifact, or any original score. It
does not call a model, rerun candidate Go, repair an artifact, or replace native
qualification. The original grader compared whole JSON objects and resolved
memo pointers against its answer key; those are stricter than the public task
contract for equivalent layouts and can falsely reject correct facts.

`RULES.json` fixes the admitted map/list representations, field aliases,
strict typed comparisons, source-register identity and digest requirements,
memo RFC6901 resolution against candidate metrics, citation requirements, and
the separate generated-vs-committed program gate. `diagnostic.py controls`
uses frozen good artifacts and synthetic mutations before any cohort artifact
is assessed. The public task still requires human review of recommendation
quality; a bounded diagnostic pass is not a full product-quality verdict.

After source review, commit these exact files. Then `prepare` writes an
append-only controls receipt and freeze outside the frozen checkout and
original results. The freeze hashes the code, rules, controls, original O24
freeze/index/export, trusted oracle/public data and the exact 28-row
native-version artifact inventory. Have an independent auditor check its hash
and controls **before** `run`. `run` verifies the freeze and writes versioned
receipts into a new, disjoint output root. It keeps original failure labels in
every row and reports numeric/source/program/memo gates independently. A
missing, altered or unparseable original artifact remains unassessable.

Example commands use `/private/tmp/opensocrates-go-ts-o24-execution-20260928`
as `--study-root`. Do not place `--controls`, `--freeze` or `--output` under
that checkout or `/private/tmp/opensocrates-go-ts-o24-results-20260928`.
