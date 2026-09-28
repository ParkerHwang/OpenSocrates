def positional_slice(records, start=None, stop=None):
    return records[start:stop]


def query_window(records, start=None, stop=None, limit=None):
    for name, value in (("start", start), ("stop", stop), ("limit", limit)):
        if value is not None and (
            not isinstance(value, int) or isinstance(value, bool) or value < 0
        ):
            raise ValueError(f"{name} must be a nonnegative integer or None")

    if start is not None and stop is not None and start > stop:
        raise ValueError("start must be less than or equal to stop")

    matching = [
        record
        for record in records
        if (start is None or record["seq"] >= start)
        and (stop is None or record["seq"] <= stop)
    ]
    return matching if limit is None else matching[:limit]


def export_lines(records, start=None, stop=None, limit=None):
    return "\n".join(row["text"] for row in query_window(records, start, stop, limit))
