import hashlib, json, sys
from pathlib import Path
source = Path(sys.argv[2]).read_bytes()
source_data = json.loads(source)
actual = json.loads(Path(sys.argv[1]).read_text())
# Expected arithmetic is written independently of candidate implementation.
expected = {"source_sha256":hashlib.sha256(source).hexdigest(),"countries":[{"country":"A","quantity":2,"saving_per_unit":3,"savings":6},{"country":"B","quantity":5,"saving_per_unit":7,"savings":35}],"total_savings":41}
source_ok = source_data == {"countries":[{"country":"A","quantity":2,"saving_per_unit":3},{"country":"B","quantity":5,"saving_per_unit":7}]}
ok = source_ok and actual == expected
print(json.dumps({"check":"country_calculation","source_matches_frozen_fixture":source_ok,"expected_total":41,"passed":ok}))
raise SystemExit(0 if ok else 1)
