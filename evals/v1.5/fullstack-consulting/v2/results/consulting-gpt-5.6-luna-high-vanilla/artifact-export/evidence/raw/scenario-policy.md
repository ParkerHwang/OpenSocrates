# Board scenario assumptions (synthetic, not measured demand)

Maximum capex EUR450000, maximum seven FTE, at most two hubs; defer is allowed.
Per country baseline C = 2025 contribution EUR, U = shipped units, G = gross sales,
N = net sales. Savings s, recurring annual fixed cost F, capex K come from options.
Low/base/high volume uplifts u = 0.10/0.25/0.40. Annual incremental contribution
after recurring cost = C*u + U*(1+u)*s - F. Capex is NOT subtracted from this annual
measure. Simple undiscounted payback = K / positive annual incremental contribution;
otherwise null (not a negative or zero-year payback).

Stress uses base volume uplift 0.25. Additional refund shock is 0.03*G with no
additional cost recovery; depreciation shock is 0.10*N for PLN/CZK markets only.
C_stress = C - 0.03*G - FX_shock. Annual incremental stress contribution relative
to unchanged normal baseline = C_stress*1.25 - C + U*1.25*s - F.
This is a deliberate conservative joint stress, not a forecast probability.

Pairs add country figures/capex/FTE without synergy. Rank feasible alternatives,
compare to defer, and disclose volume/scenario and timing assumptions. A different
recommendation is allowed with supported risk reasoning. Do not claim this simple
scenario arithmetic is a causal estimate of hubs or a full discounted cash-flow model.
