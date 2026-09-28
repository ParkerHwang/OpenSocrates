"""Author the new synthetic source room and archive real public source bytes.

Preparation only. Never run after manifest.json has been frozen.
"""

from __future__ import annotations
import csv
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import random
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
ROOM = HERE / "source-room"
COUNTRIES = ("DEU", "FRA", "NLD", "POL", "CZE", "ESP")


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        out = csv.DictWriter(f, fieldnames=list(rows[0]))
        out.writeheader()
        out.writerows(rows)


def main():
    assert not (HERE / "manifest.json").exists(), "already frozen"
    ROOM.mkdir(exist_ok=True)
    urls = {
        "population.json": "https://api.worldbank.org/v2/country/DEU;FRA;NLD;POL;CZE;ESP/indicator/SP.POP.TOTL?date=2022:2024&format=json&per_page=1000",
        "gdp-per-capita.json": "https://api.worldbank.org/v2/country/DEU;FRA;NLD;POL;CZE;ESP/indicator/NY.GDP.PCAP.CD?date=2022:2024&format=json&per_page=1000",
        "ecb-history.zip": "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip",
    }

    def fetch(item):
        name, url = item
        path = ROOM / name
        stamp = datetime.now(timezone.utc).isoformat()
        if not path.exists():
            result = subprocess.run(
                ["/usr/bin/curl", "--fail", "--location", "--silent", "--show-error", url],
                capture_output=True,
                check=True,
            )
            path.write_bytes(result.stdout)
        data = path.read_bytes()
        if name.endswith(".json"):
            value = json.loads(data)
            assert isinstance(value, list) and len(value[1]) == 18, name
        return {
            "file": name,
            "original_url": url,
            "retrieved_utc": stamp,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "kind": "official_public_snapshot",
        }

    with ThreadPoolExecutor(max_workers=3) as pool:
        public = list(pool.map(fetch, urls.items()))
    with zipfile.ZipFile(ROOM / "ecb-history.zip") as archive:
        csv_name = next(n for n in archive.namelist() if n.endswith(".csv"))
        raw = archive.read(csv_name)
    (ROOM / "ecb-history.csv").write_bytes(raw)
    public.append(
        {
            "file": "ecb-history.csv",
            "derived_from": "ecb-history.zip",
            "transformation": "lossless ZIP extraction",
            "kind": "official_public_snapshot",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
    )
    rate_rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    assert sum(r["Date"].startswith("2025-") for r in rate_rows) > 240

    rng = random.Random(2026092736)
    orders, corrections, returns = [], [], []
    options = []
    for ci, country in enumerate(COUNTRIES):
        currency = {"POL": "PLN", "CZE": "CZK"}.get(country, "EUR")
        multiplier = {"PLN": 4.25, "CZK": 24.9, "EUR": 1}[currency]
        for month in range(1, 13):
            for j in range(18):
                sku = ("AXLE", "BRAKE", "SENSOR")[j % 3]
                quantity = 10 + rng.randrange(95) + ci * 2
                price = round(
                    ({"AXLE": 37, "BRAKE": 58, "SENSOR": 79}[sku] + (ci - 2) * 2) * multiplier, 2
                )
                oid = f"M{ci + 1}-{month:02}-{j + 1:03}"
                shipped = f"2025-{month:02}-{min(j + 3, 28):02}"
                order = dict(
                    order_id=oid,
                    revision=1,
                    country=country,
                    ordered_at=f"2025-{month:02}-{j + 1:02}",
                    shipped_at=shipped,
                    status="shipped",
                    is_test="false",
                    sku=sku,
                    quantity=quantity,
                    unit_price_local=f"{price:.2f}",
                    discount_local=f"{round(quantity * price * (0.06 if j % 5 == 0 else 0), 2):.2f}",
                    currency=currency,
                    fulfillment_eur=f"{(12 + quantity * (0.9 + ci * 0.11)):.2f}",
                )
                if j == 16 and month % 3 == 0:
                    order.update(status="cancelled", shipped_at="")
                if j == 17 and month % 4 == 0:
                    order["is_test"] = "true"
                if j == 0 and month in (3, 9):
                    order.update(unit_price_local="0.00", discount_local="0.00")
                orders.append(order)
                if j == 5 and month in (2, 7, 11):
                    corrected = {
                        **order,
                        "revision": 2,
                        "discount_local": f"{round(quantity * price * 0.12, 2):.2f}",
                    }
                    corrections.append(corrected)
                effective = (
                    corrections[-1] if corrections and corrections[-1]["order_id"] == oid else order
                )
                if j % (4 if ci in (1, 4) else 6) == 2 and order["status"] == "shipped":
                    q = min(quantity, 2 + ci)
                    refund = (
                        (quantity * float(price) - float(effective["discount_local"]))
                        * q
                        / quantity
                    )
                    ret = dict(
                        return_id="R-" + oid,
                        revision=1,
                        order_id=oid,
                        received_at=f"2025-{month:02}-28",
                        quantity=q,
                        restocked_quantity=q // 2,
                        refund_local=f"{refund:.2f}",
                    )
                    returns.append(ret)
                    if month == 6:
                        returns.append(dict(ret))
        capex = (280000, 210000, 140000, 110000, 95000, 130000)[ci]
        options.append(
            dict(
                country=country,
                capex_eur=capex,
                fte=(5, 4, 3, 3, 2, 3)[ci],
                annual_fixed_eur=(95000, 85000, 65000, 45000, 40000, 55000)[ci],
                saving_eur_per_unit=(2.6, 2.9, 3.2, 2.4, 2.1, 3.0)[ci],
            )
        )
    orders.extend(dict(x) for x in orders[::103])
    orders.append(
        {
            **orders[20],
            "order_id": "FUTURE-2026",
            "ordered_at": "2026-01-02",
            "shipped_at": "2026-01-05",
        }
    )
    # A corrected return, cutoff edge, excluded later return and orphan.
    returns.append(
        {
            **returns[0],
            "revision": 2,
            "refund_local": f"{float(returns[0]['refund_local']) - 1:.2f}",
        }
    )
    returns.append(
        dict(
            return_id="R-CUTOFF",
            revision=1,
            order_id="M1-12-002",
            received_at="2026-01-31",
            quantity=1,
            restocked_quantity=1,
            refund_local="54.00",
        )
    )
    returns.append(
        dict(
            return_id="R-LATE",
            revision=1,
            order_id="M1-12-004",
            received_at="2026-02-01",
            quantity=1,
            restocked_quantity=0,
            refund_local="33.00",
        )
    )
    returns.append(
        dict(
            return_id="R-ORPHAN",
            revision=1,
            order_id="ABSENT",
            received_at="2025-12-20",
            quantity=2,
            restocked_quantity=1,
            refund_local="60.00",
        )
    )
    write_csv(ROOM / "orders-part1.csv", orders[::2])
    write_csv(ROOM / "orders-part2.csv", orders[1::2])
    write_csv(ROOM / "order-corrections.csv", corrections)
    write_csv(ROOM / "returns.csv", returns)
    write_csv(ROOM / "hub-options.csv", options)
    write_csv(
        ROOM / "unit-costs.csv",
        [
            dict(sku=s, valid_from=start, unit_cost_eur=cost)
            for s, a, b in [("AXLE", 17.5, 19.0), ("BRAKE", 27.0, 29.5), ("SENSOR", 43.0, 41.5)]
            for start, cost in [("2025-01-01", a), ("2025-07-01", b)]
        ],
    )
    (ROOM / "data-dictionary.md").write_text(
        """# Client data dictionary (synthetic)

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
""",
        encoding="utf-8",
    )
    (ROOM / "scenario-policy.md").write_text(
        """# Board scenario assumptions (synthetic, not measured demand)

Maximum capex EUR450000, maximum seven FTE, at most two hubs; defer is allowed.
Per country baseline C = 2025 contribution EUR, U = shipped units, G = gross sales,
N = net sales. Savings s, recurring annual fixed cost F, capex K come from options.
Low/base/high volume uplifts u = 0.10/0.25/0.40. Annual incremental contribution
after recurring cost = C*u + U*(1+u)*s - F. Capex is NOT subtracted from this annual
measure. Simple undiscounted payback = K / positive annual incremental contribution;
otherwise null (not a negative or zero-year payback).

Stress uses base volume uplift 0.25. Additional refund shock is 0.03*G with no
additional cost recovery; depreciation shock is 0.10*N for PLN/CZK markets only.
C_stress = C - 0.03*G - FX_shock. Annual incremental stress contribution relative
to unchanged normal baseline = C_stress*1.25 - C + U*1.25*s - F.
This is a deliberate conservative joint stress, not a forecast probability.

Pairs add country figures/capex/FTE without synergy. Rank feasible alternatives,
compare to defer, and disclose volume/scenario and timing assumptions. A different
recommendation is allowed with supported risk reasoning. Do not claim this simple
scenario arithmetic is a causal estimate of hubs or a full discounted cash-flow model.
""",
        encoding="utf-8",
    )
    (ROOM / "source-register.json").write_text(
        json.dumps(
            {
                "public": public,
                "client_data": "entirely synthetic; generated with seed 2026092736",
                "vintage_note": "Archive fetched before outcome calls. This vintage may include subsequent revisions of historical years.",
            },
            indent=2,
        )
        + "\n"
    )
    names = sorted(p.name for p in ROOM.iterdir() if p.is_file() and p.name != "index.html")
    (ROOM / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>Meridian source room</title><h1>Meridian source room</h1><p>Raw client exports, metadata and official-source archives. Inspect data-dictionary.md and scenario-policy.md.</p><ul>'
        + "".join(f'<li><a href="{n}">{n}</a></li>' for n in names)
        + "</ul>"
    )
    print(
        json.dumps(
            {
                "files": len(names) + 1,
                "orders_raw": len(orders),
                "corrections": len(corrections),
                "returns_raw": len(returns),
                "official": public,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
