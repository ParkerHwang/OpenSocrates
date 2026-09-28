class TagIndex:
    def __init__(self):
        self._items = {}

    def put(self, document, metadata):
        self._items[document] = metadata

    def summary(self):
        return dict(self._items)


def render_count(index):
    return f"documents={len(index.summary())}"
