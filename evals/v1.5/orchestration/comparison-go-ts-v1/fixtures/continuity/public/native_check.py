#!/usr/bin/env python3
"""Read-only shape check for the separate continuity lane."""
import json
from pathlib import Path

payload = json.loads(Path("continuation.json").read_text())
required = {"source_revision", "p1_delay_minutes", "backend", "frontend", "notification_target", "viewer_permission", "focus_rule", "proposal_accepted", "unassigned_handover_owner", "side_answer"}
assert required <= payload.keys()
assert Path("handoff.md").is_file() and len(Path("handoff.md").read_text().strip()) > 150
