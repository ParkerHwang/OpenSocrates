"""Resolve costs using the latest eligible effective date.

Select the row with the latest effective date at or before as_of, regardless
of whether its price is higher or lower than older prices. Future rows are
ineligible. The selected row supplies both the cost and its evidence date.
Numeric zero is a known cost. Explicit null (None) is unknown; an absent
cost field is missing. Neither null nor missing falls back to an older cost.
A missing field returns a null cost with the selected row's effective date.
With no eligible row, return missing with null cost and null effective date.
Preserve the caller's input rows without mutation.
"""
def effective_cost(rows, as_of):
    eligible = [r for r in rows if r["effective_date"] <= as_of]
    if not eligible:
        return {"state": "missing", "cost": None, "effective_date": None}
    row = max(eligible, key=lambda r: r["effective_date"])
    if "cost" not in row:
        state = "missing"
    elif row["cost"] is None:
        state = "unknown"
    else:
        state = "known"
    return {"state": state, "cost": row.get("cost"), "effective_date": row["effective_date"]}
