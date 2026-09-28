import json, sys
from pathlib import Path
expected = {"interface":{"function":"effective_cost","parameters":["rows","as_of"],"return_fields":["state","cost","effective_date"]},"selection":{"condition":"effective_date <= as_of","order":"effective_date descending","limit":1},"states":{"number":"known","zero":"known","explicit_null":"unknown","absent_cost":"missing","no_eligible_row":"missing"},"mutates_input":False,"date_format":"YYYY-MM-DD","same_date_policy":"precondition_unique_dates"}
actual = json.loads(Path(sys.argv[1]).read_text())
ok = actual == expected
print(json.dumps({"check":"design_contract","passed":ok}))
raise SystemExit(0 if ok else 1)
