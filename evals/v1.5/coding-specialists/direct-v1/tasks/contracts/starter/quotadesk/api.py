from .policy import apply_policy


def handle_edit(store, namespace, payload):
    return 200, apply_policy(store, namespace, payload)
