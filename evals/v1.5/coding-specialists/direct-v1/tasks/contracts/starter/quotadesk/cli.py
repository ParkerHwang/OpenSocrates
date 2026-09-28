from .policy import import_legacy


def import_line(store, namespace, value):
    result = import_legacy(store, namespace, {"limit": value, "name": "cli"})
    number = result["legacy_limit"]
    return "unlimited" if number is None else f"limit={number}"


def render_record(record):
    return f"{record['namespace']}@{record['revision']}: {record['effective_max_jobs']} ({record['label']})"
