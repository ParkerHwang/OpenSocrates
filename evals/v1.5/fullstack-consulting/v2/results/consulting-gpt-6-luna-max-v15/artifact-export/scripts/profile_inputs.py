"""Profile saved client exports before applying the accounting rules."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "evidence" / "source_room"

orders = pd.concat(
    [pd.read_csv(SRC / name, dtype=str, keep_default_na=False).assign(_source=name)
     for name in ("orders-part1.csv", "orders-part2.csv", "order-corrections.csv")],
    ignore_index=True,
)
print("ORDER ROWS", len(orders), "exact duplicates", int(orders.drop(columns="_source").duplicated().sum()))
print("ORDER SOURCES", orders.groupby("_source").size().to_dict())
orders = orders.drop_duplicates(subset=list(orders.columns.drop("_source")), keep="first")
orders["revision"] = pd.to_numeric(orders.revision)
print("UNIQUE ORDER IDS", orders.order_id.nunique(), "IDs with multiple revs", int((orders.groupby("order_id").revision.nunique() > 1).sum()))
latest_rev = orders.groupby("order_id").revision.transform("max")
latest = orders[orders.revision.eq(latest_rev)]
payload_cols = [c for c in orders.columns if c != "_source"]
ties = latest.groupby("order_id")[payload_cols].apply(lambda g: len(g.drop_duplicates()) > 1)
print("LATEST-REV CONFLICT IDS", ties[ties].index.tolist())
print("STATUS COUNTS", latest.status.value_counts().to_dict())
print("TEST COUNTS", latest.is_test.value_counts().to_dict())
print("SHIP YEARS", latest.shipped_at.str[:4].value_counts().to_dict())
print("NULLS", latest.replace("", pd.NA).isna().sum().to_dict())
print("CURRENCIES", latest.currency.value_counts().to_dict(), "SKUS", latest.sku.value_counts().to_dict())
print("TIED ORDER IDs AT ANY REV", orders.groupby(["order_id", "revision"])[payload_cols].apply(lambda g: len(g.drop_duplicates()) > 1).loc[lambda x: x].index.tolist())

returns = pd.read_csv(SRC / "returns.csv", dtype=str, keep_default_na=False)
print("RETURN ROWS", len(returns), "exact duplicates", int(returns.duplicated().sum()))
returns = returns.drop_duplicates()
returns["revision"] = pd.to_numeric(returns.revision)
latest_ret = returns[returns.revision.eq(returns.groupby("return_id").revision.transform("max"))]
print("RETURN IDS", returns.return_id.nunique(), "IDs with multiple revs", int((returns.groupby("return_id").revision.nunique() > 1).sum()))
print("LATEST-REV RETURN CONFLICTS", latest_ret.groupby("return_id").apply(lambda g: len(g.drop_duplicates()) > 1).loc[lambda x: x].index.tolist())
print("RETURN YEARS", latest_ret.received_at.str[:4].value_counts().to_dict())
print("RETURN EMPTY VALUES", latest_ret.replace("", pd.NA).isna().sum().to_dict())
print("RETURN QTY CHECKS", latest_ret.assign(q=lambda d: pd.to_numeric(d.quantity), r=lambda d: pd.to_numeric(d.restocked_quantity)).query("q < 0 or r < 0 or r > q")["return_id"].tolist())

wb = {}
for filename in ("population.json", "gdp-per-capita.json"):
    import json
    data = json.loads((SRC / filename).read_text())
    wb[filename] = data
    recs = data[1]
    print(filename, "rows", len(recs), "nulls", sum(x.get("value") is None for x in recs), "codes", sorted({x.get("countryiso3code") for x in recs}), "years", sorted({x.get("date") for x in recs}))
