import copy, json, runpy, sys
from pathlib import Path
cases = json.loads(Path(sys.argv[2]).read_text())
module = runpy.run_path(sys.argv[1])
function = module.get("effective_cost")
failures = []
for case in cases:
    rows = copy.deepcopy(case["rows"])
    try:
        actual = function(rows, case["as_of"])
        valid = (isinstance(actual, dict) and set(actual) == {"state","cost","effective_date"} and actual == case["expected"] and rows == case["rows"])
        if actual and case["expected"]["state"] == "known":
            valid = valid and isinstance(actual.get("cost"), (int,float)) and not isinstance(actual.get("cost"), bool)
    except Exception as exc:
        valid = False
    if not valid:
        failures.append(case["id"])
print(json.dumps({"check":"cost_contract","case_count":len(cases),"failed_case_ids":failures,"passed":not failures}))
raise SystemExit(1 if failures else 0)
