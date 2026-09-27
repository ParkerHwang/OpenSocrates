# Evidence provenance

The `raw/` directory is a byte-preserved collection of the frozen room specified in `TOOLING.md`. No data was collected from a client account. Client exports, costs and hub assumptions are synthetic; World Bank and ECB series are official public snapshots supplied by the room.

Use `source-register.csv` or `source-register.json` for the combined analyst register. Each entry records its collection URL/time, SHA-256, original source URL, archive retrieval time where applicable, units, period, synthetic/public status and source vintage. The saved `raw/source-register.json` is the original archive manifest. `collection-manifest.json` is the analyst download record.

The ECB ZIP contains one CSV that is byte-identical to `raw/ecb-history.csv`; these are two representations of one source, not independent corroborating evidence. World Bank population and GDP are separate indicators from the same publisher. They do not independently validate the synthetic hub demand assumptions.

All required archived observations are present: 18 country-years for each World Bank indicator, and 255 published 2025 dates for each of PLN and CZK. The archive includes other ECB currencies/years; those are preserved but excluded from the model. No missing financial or required market observations were imputed.
