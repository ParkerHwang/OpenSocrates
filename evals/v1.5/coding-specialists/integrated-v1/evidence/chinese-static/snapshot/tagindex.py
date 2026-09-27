from copy import deepcopy


class TagIndex:
    def __init__(self):
        self._items = {}

    def put(self, document, metadata):
        self._items[document] = deepcopy(metadata)

    def summary(self):
        return deepcopy(self._items)


def render_count(index):
    return f"documents={len(index.summary())}"
