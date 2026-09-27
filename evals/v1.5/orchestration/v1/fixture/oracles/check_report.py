import hashlib, json, re, sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
report = Path(sys.argv[1]).read_text()
calc_bytes = Path(sys.argv[2]).read_bytes()
source_bytes = Path(sys.argv[3]).read_bytes()
calc = json.loads(calc_bytes)
source = json.loads(source_bytes)
errors = []
expected_source = {"countries":[{"country":"A","quantity":2,"saving_per_unit":3},{"country":"B","quantity":5,"saving_per_unit":7}]}
expected_rows = [["A", Decimal(2), Decimal(3), Decimal(6)],["B",Decimal(5),Decimal(7),Decimal(35)]]
expected_calc = {"source_sha256":hashlib.sha256(source_bytes).hexdigest(),"countries":[{"country":"A","quantity":2,"saving_per_unit":3,"savings":6},{"country":"B","quantity":5,"saving_per_unit":7,"savings":35}],"total_savings":41}
if source != expected_source: errors.append("source_fixture")
if calc != expected_calc: errors.append("calculation")
def value(label):
    matches = re.findall(r"^"+re.escape(label)+r":\s*([^\n]+)$", report, re.M)
    return matches[0].strip().strip("*` ") if len(matches) == 1 else None
if value("Source SHA-256") != hashlib.sha256(source_bytes).hexdigest(): errors.append("source_digest")
if value("Calculation SHA-256") != hashlib.sha256(calc_bytes).hexdigest(): errors.append("calculation_digest")
try:
    if Decimal(value("Total savings")) != Decimal(41): errors.append("narrative_total")
except (TypeError,InvalidOperation): errors.append("narrative_total")
rows=[]
for line in report.splitlines():
    if not line.strip().startswith("|"): continue
    cells=[c.strip().strip("*` ") for c in line.strip().strip("|").split("|")]
    if len(cells) != 4 or cells[0] not in {"A","B"}: continue
    try: rows.append([cells[0]]+[Decimal(c) for c in cells[1:]])
    except InvalidOperation: errors.append("table_number")
if rows != expected_rows: errors.append("country_rows")
print(json.dumps({"check":"source_results_narrative_reconciliation","passed":not errors,"failed_rules":errors}))
raise SystemExit(1 if errors else 0)
