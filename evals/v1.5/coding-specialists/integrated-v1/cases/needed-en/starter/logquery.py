def positional_slice(records, start=None, stop=None):
    return records[start:stop]


def query_window(records, start=None, stop=None, limit=None):
    raise NotImplementedError("new sequence-number query")


def export_lines(records, start=None, stop=None, limit=None):
    return "\n".join(row["text"] for row in query_window(records, start, stop, limit))
