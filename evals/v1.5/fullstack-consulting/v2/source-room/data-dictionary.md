# Client data dictionary (synthetic)

Orders: one order, one SKU per row. Select highest numeric revision for each
order_id across both extracts and corrections. Identical repeated rows are one
record. Corrections replace the whole row, not an additive adjustment. Include
status shipped, is_test false, shipped_at in 2025. Count free/sample orders normally.
Other statuses/test/future records are excluded from the 2025 analysis.

Returns: one return_id per record, highest revision wins. Include received_at up
to and including 2026-01-31 and only when the linked order is eligible. Orphan
returns are quarantined, not matched by guess. Multiple legitimate distinct return
IDs on an order are additive. restocked_quantity is physically reusable stock;
no blanket assumption that every returned unit recovers its product cost.

unit-costs.csv: effective-dated EUR per unit; use the latest valid_from on or before
the original shipment. Fulfillment costs are actual nonrefundable EUR order costs.
Unit cost is unaffected by sales currency. Prices and discounts exclude taxes.
Gross local sales = quantity * unit_price_local - discount_local. Refund amounts
are explicit credit values in the original order currency. Convert gross and
summed refunds with that sale month's mean ECB local units per EUR. Round each
component per order half up to cents before summing. Gross COGS = quantity * unit
cost; recover COGS only for restocked_quantity at the original unit cost. Net COGS
= gross COGS minus recovered COGS. Contribution = gross sales - refunds - net COGS
- fulfillment. Returned units is physical quantity, not an order return count.

ECB: actual official reference-rate observations, quote units per EUR. Arithmetic
mean across available published business days in each 2025 calendar month; EUR=1.
Reference rates are analytical translation assumptions, not actual transaction FX.
World Bank: public 2022-2024 series, population persons; GDP per capita current USD.
Current USD is not PPP or constant-price real income. Preserve revisions/missingness.
