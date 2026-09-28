"""Supplementary sensitivities. Required policy scenarios remain unchanged."""
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'deliverables'
D=Decimal
m=json.loads((OUT/'metrics.json').read_text(),parse_float=D)
c={r['country']:r for r in m['countries']}
s={(r['country'],r['scenario']):r for r in m['hub_scenarios']}
t={r['country']:r for r in m['decision_thresholds']}
p={r['option']:r for r in m['portfolio_scenarios']}
q=lambda x:x.quantize(D('.01'),rounding=ROUND_HALF_UP)
caps=[]
for country,r in c.items():
    base=s[country,'base']; rate=t[country]['fulfillment_per_unit']
    lost=D('1.25')*D(r['shipped_units'])*(base['saving_eur_per_unit']-rate)
    caps.append(dict(country=country,assumed_saving_eur_per_unit=base['saving_eur_per_unit'],
                     recorded_fulfillment_eur_per_unit=rate,
                     ratio_assumed_saving_to_recorded_cost=base['saving_eur_per_unit']/rate,
                     capped_base_incremental_eur=q(base['incremental_contribution_eur']-lost),
                     capped_stress_incremental_eur=q(s[country,'stress']['incremental_contribution_eur']-lost)))
capmap={r['country']:r for r in caps}
capport=[]
for name in ['CZE+ESP','NLD+ESP','POL+ESP','ESP','DEFER']:
    pr=p[name]
    capport.append(dict(option=name,base_incremental_eur=sum((capmap[x]['capped_base_incremental_eur'] for x in pr['countries']),D(0)),
                        stress_incremental_eur=sum((capmap[x]['capped_stress_incremental_eur'] for x in pr['countries']),D(0))))
fav,alt=p['CZE+ESP'],p['NLD+ESP']
gap=fav['base_incremental_eur']-alt['base_incremental_eur']
lossdiff=(fav['base_incremental_eur']-fav['stress_incremental_eur'])-(alt['base_incremental_eur']-alt['stress_incremental_eur'])
alpha=gap/lossdiff
C,U=c['CZE']['contribution_eur'],D(c['CZE']['shipped_units'])
F,sv=s['CZE','base']['annual_fixed_eur'],s['CZE','base']['saving_eur_per_unit']
switch_u=(s['NLD','base']['incremental_contribution_eur']+F-U*sv)/(C+U*sv)
detail=dict(
    decision_preference='Analyst default: maximize base annual contribution inside hard limits, with staged release. No board risk weights supplied; show the alternative if downside preservation is preferred.',
    criteria_provenance=[
        dict(criterion='Capital and staffing feasibility',status='hard constraint',direction='<= EUR450,000; <=7 FTE; <=2 hubs',owner='Board / TASK.md and scenario-policy.md',evidence='given'),
        dict(criterion='Annual incremental contribution after recurring fixed cost',status='primary preference',direction='maximize base EUR/year',owner='Analyst default for this recommendation',evidence='computed; synthetic scenario inputs'),
        dict(criterion='Downside under low volume and defined stress',status='risk comparison',direction='higher EUR/year preferred; no imposed hurdle',owner='Analyst; stress specification from client',evidence='computed; probabilities unknown'),
        dict(criterion='Capex, FTE, payback',status='secondary preferences',direction='lower resources and faster positive payback preferred',owner='Analyst',evidence='computed; cash timing omitted'),
        dict(criterion='Service improvement and incremental demand',status='unverified benefit',direction='measure pilot results before full commitment',owner='COO and Commercial Director (proposed roles)',evidence='no actual delivery, conversion or interview evidence'),
    ],
    savings_cap_sensitivity=caps, savings_cap_portfolios=capport,
    switches=dict(cze_uplift_equal_nld_at_nld_base=switch_u,
                  cze_vs_nld_base_gap_eur=gap,
                  cze_additional_fixed_cost_equal_nld_eur=gap,
                  joint_stress_severity_fraction_equal_nld=alpha,
                  simultaneous_refund_gross_fraction_at_switch=D('.03')*alpha,
                  simultaneous_fx_net_sales_fraction_at_switch=D('.10')*alpha,
                  cze_stress_positive_uplift=(F+C)/(s['CZE','stress']['contribution_after_shock_eur']+U*sv)-1),
    interpretation=[
        'Cap sensitivity assumes savings can only remove existing recorded fulfillment cost. This is a diagnostic upper bound, not a corrected client forecast. Savings may include unrecorded activities, but evidence is absent.',
        'CZE+ESP dominates POL+ESP on the modeled low/base/high/stress increments, lower capex and fewer FTE. CZE+ESP and NLD+ESP are incomparable because NLD+ESP preserves more contribution in stress.',
        'The stress-severity switch scales the specified refund and FX shocks together. It is a deterministic interpolation, not a probability threshold.',
        'The CZE uplift switch varies only CZE; NLD remains at 25%. A common uplift applied to all countries is a different question.',
        'Defer preserves capital and produces zero modeled hub increment. It remains valid if pilot evidence fails, even though modeled base increments are positive.'
    ],
    release_sequence=['Spain first: conditional EUR130,000 and 3 FTE', 'Czechia second: conditional EUR95,000 and 2 FTE after savings/FX gate'],
    acceptance_risk='Czechia alone loses EUR37,826.95/year in the defined stress; Spain offsets it in the required pair scenario. The pair turns slightly negative under the fulfillment-capped savings stress.'
)
(OUT/'decision-support.json').write_text(json.dumps(detail,indent=2,default=float)+'\n')
# Attach the actual judgment and evidence caveat to the deterministic exchange.
m['recommendation'].update(release_sequence=detail['release_sequence'],
    strongest_base_alternative='POL+ESP',downside_alternative='NLD+ESP',
    risk_accepted=detail['acceptance_risk'],
    rationale='Conditionally reserve CZE+ESP: highest low/base/high annual increment and best base result within the resource limits. Start Spain first. Release Czechia only after verifying savings scope, commercial uplift and FX exposure; use NLD+ESP if downside preservation is the board priority. All hub savings exceed recorded fulfillment cost per unit, so the commitment is gated rather than unconditional.')
m['quality']['savings_assumption_anomaly']='All six saving assumptions exceed recorded fulfillment EUR/unit; required scenarios retained, separate capped-savings sensitivity supplied.'
(OUT/'metrics.json').write_text(json.dumps(m,indent=2,default=float,allow_nan=False)+'\n')
print(json.dumps(detail,indent=2,default=float))
