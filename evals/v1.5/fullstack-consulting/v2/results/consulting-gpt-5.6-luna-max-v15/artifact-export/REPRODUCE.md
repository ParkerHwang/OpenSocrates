# Meridian Parts reproducibility

This project is reproducible from the saved frozen source-room files under
`evidence/raw/`. The client order, return, cost, hub-option and policy files are
synthetic. The World Bank and ECB files are archived official snapshots; their
original URLs, retrieval vintage, units and SHA-256 hashes are in
`evidence/source_register.json` and `deliverables/source_register.json`.

From the project root, run:

```bash
<SHARED_RUNTIME>/python/bin/python3 scripts/generate_all.py
```

The command rebuilds:

- `analysis_outputs/`: canonical audit tables, order-level calculations, monthly/country results, FX means, market context, hub/pair scenarios, rankings and chart PNGs;
- `deliverables/metrics.json`: the deterministic exchange contract and quality notes;
- `deliverables/meridian_parts_analysis.xlsx`: usable analytical workbook;
- `deliverables/meridian_parts_executive_report.pdf`: executive consulting report;
- `deliverables/meridian_parts_board_presentation.pptx`: board presentation;
- `deliverables/source_register.json`: source register.

The main analysis implementation is `scripts/analysis.py`. It applies the data
dictionary rules: highest numeric revision wins, exact duplicates are removed,
cancelled/test/future shipments are excluded, valid zero-price shipments remain,
orphan returns are quarantined, return receipts use the inclusive 2026-01-31
cutoff, original sale-month ECB means are used for sale and refund conversion,
and monetary components are rounded half-up per order before summing.

Useful verification checks:

```bash
<SHARED_RUNTIME>/python/bin/python3 -c "import json; from pathlib import Path; m=json.loads(Path('deliverables/metrics.json').read_text()); assert len(m['monthly']) == 72; assert len(m['countries']) == 6; assert len(m['fx_monthly']) == 24; assert len(m['market_context']) == 18; assert m['recommendation']['countries'] == ['CZE','ESP']; print('metrics contract checks passed')"
<SHARED_RUNTIME>/python/bin/python3 -c "from pypdf import PdfReader; r=PdfReader('deliverables/meridian_parts_executive_report.pdf'); assert len(r.pages) >= 8; print('report pages',len(r.pages))"
<SHARED_RUNTIME>/python/bin/python3 -c "from openpyxl import load_workbook; from pptx import Presentation; w=load_workbook('deliverables/meridian_parts_analysis.xlsx',read_only=True); assert 'Countries' in w.sheetnames and 'Charts' in w.sheetnames; p=Presentation('deliverables/meridian_parts_board_presentation.pptx'); assert len(p.slides)==10; print('workbook/deck checks passed')"
```

The source room is deliberately not live client access. Re-running after a new
source-room vintage may change hashes, retrieval metadata, historical public
observations and the resulting figures; preserve the source register with any
new run.
