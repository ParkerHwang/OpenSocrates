# Effective-date cost contract

Produce `design.json`, a JSON design artifact defining the `effective_cost(rows, as_of)` Python interface. The design must cover the exact return fields `state`, `cost`, and `effective_date`; ISO dates; unique effective dates as a precondition; no input mutation; and the rules below. The fixture accepts a bounded, declarative design with this public structure:

```json
{
  "interface": {
    "function": "effective_cost",
    "parameters": [
      "rows",
      "as_of"
    ],
    "return_fields": [
      "state",
      "cost",
      "effective_date"
    ]
  },
  "selection": {
    "condition": "effective_date <= as_of",
    "order": "effective_date descending",
    "limit": 1
  },
  "states": {
    "number": "known",
    "zero": "known",
    "explicit_null": "unknown",
    "absent_cost": "missing",
    "no_eligible_row": "missing"
  },
  "mutates_input": false,
  "date_format": "YYYY-MM-DD",
  "same_date_policy": "precondition_unique_dates"
}
```

Implement `pricing.py` only after its design dependency is qualified. Pick the eligible row with the latest effective date, including equality; future rows are ineligible. Do not maximize cost. Numeric zero is known. A selected explicit null means unknown. A selected absent cost field means missing. No eligible row means missing with both cost and effective_date null. Each other return includes the selected effective_date. Costs are numbers, null or absent; rows have unique valid ISO effective dates. The function must not mutate rows. The six cases are stipulated correctness examples, not a quality benchmark.
