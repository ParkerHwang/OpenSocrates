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
