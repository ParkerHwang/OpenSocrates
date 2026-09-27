# Country calculation and report contract

The source lists country, quantity, and saving_per_unit. Compute each country's quantity * saving_per_unit, then sum those country products. Never multiply the sum of quantities by the sum of per-unit savings. No money/currency or external factual claim is implied.

The data producer owns `calculation.json`, with only `source_sha256`, `countries`, and `total_savings`. `source_sha256` is the exact SHA-256 of the source file. Each country result has `country`, `quantity`, `saving_per_unit`, and `savings`. Country order remains source order.

The document producer depends on the qualified calculation and owns `report.md`. It must include these exact labels, with optional Markdown inline emphasis/backticks around values: `Source SHA-256: <source digest>`, `Calculation SHA-256: <calculation digest>`, and `Total savings: <total>`. Include a four-column Markdown table with header `Country | Quantity | Saving per unit | Savings` and a row for each country. State in prose that the total is the sum of the country products. Every number must reconcile to source and calculation. The check is a numeric/source reconciliation; independent review must also inspect prose.

The source fixture implies A=6, B=35, total=41. A copied report claiming 70 must fail. Changed calculation bytes invalidate the report's calculation digest even if numeric values did not change.
