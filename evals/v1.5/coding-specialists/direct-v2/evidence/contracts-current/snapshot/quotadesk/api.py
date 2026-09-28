from .policy import PolicyError, apply_policy


def handle_edit(store, namespace, payload):
    try:
        return 200, apply_policy(store, namespace, payload)
    except PolicyError as error:
        status = {"not_found": 404, "invalid": 400, "conflict": 409}[error.code]
        return status, {"error": error.code}
