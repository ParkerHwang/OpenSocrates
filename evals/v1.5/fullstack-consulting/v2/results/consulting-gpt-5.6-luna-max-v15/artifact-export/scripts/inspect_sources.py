from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "evidence" / "raw"

for f in ["orders-part1.csv", "orders-part2.csv", "order-corrections.csv", "returns.csv", "unit-costs.csv", "hub-options.csv", "ecb-history.csv"]:
    df = pd.read_csv(P / f)
    print("\n", f, df.shape, df.columns.tolist())
    print(df.head(2).to_string(index=False))

orders = pd.concat(
    [pd.read_csv(P / "orders-part1.csv"), pd.read_csv(P / "orders-part2.csv")],
    ignore_index=True,
)
corr = pd.read_csv(P / "order-corrections.csv")
returns = pd.read_csv(P / "returns.csv")
print("\norders extracts", len(orders), "unique ids", orders.order_id.nunique(), "repeated rows", len(orders) - len(orders.drop_duplicates()))
print("duplicate ids")
print(orders[orders.duplicated("order_id", False)].sort_values("order_id").head(20).to_string(index=False))
print("corrections", len(corr), "ids", corr.order_id.nunique(), "overlap", len(set(corr.order_id) & set(orders.order_id)))
print("returns rows", len(returns), "unique return", returns.return_id.nunique(), "duplicated exact", returns.duplicated().sum())
print("duplicate return ids")
print(returns[returns.duplicated("return_id", False)].head(30).to_string(index=False))
print("order statuses", orders.status.value_counts(dropna=False).to_dict(), "tests", orders.is_test.value_counts(dropna=False).to_dict())
print("order dates", pd.to_datetime(orders.ordered_at, errors="coerce").min(), pd.to_datetime(orders.ordered_at, errors="coerce").max(), pd.to_datetime(orders.shipped_at, errors="coerce").min(), pd.to_datetime(orders.shipped_at, errors="coerce").max())
print("currencies", orders.currency.value_counts(dropna=False).to_dict())
print("countries", orders.country.value_counts(dropna=False).to_dict())
print("returns dates", pd.to_datetime(returns.received_at, errors="coerce").min(), pd.to_datetime(returns.received_at, errors="coerce").max())
print("return duplicate ids", returns[returns.duplicated("return_id", False)].return_id.unique()[:20], "count", returns[returns.duplicated("return_id", False)].return_id.nunique())
print("return order ids not in extracts", len(set(returns.order_id) - set(orders.order_id)), sorted(set(returns.order_id) - set(orders.order_id))[:20])
print("returns order ids", returns.order_id.nunique())
print("return revisions", returns.groupby("return_id").revision.nunique().sort_values(ascending=False).head(20).to_dict())
print("returns exact duplicate rows", returns.duplicated().sum())
print("returns duplicate id counts", returns[returns.duplicated("return_id", False)].groupby("return_id").size().value_counts().to_dict())
fx = pd.read_csv(P / "ecb-history.csv")
print("fx dates", fx.Date.min(), fx.Date.max(), "rows", len(fx), "columns", len(fx.columns))
print("2025 rows", fx[fx.Date.str.startswith("2025")].shape)
for c in ["PLN", "CZK", "USD"]:
    f25 = fx[fx.Date.str.startswith("2025")]
    print(c, fx[c].head().tolist(), "missing", f25[c].isna().sum(), "NA", f25[c].eq("N/A").sum())
