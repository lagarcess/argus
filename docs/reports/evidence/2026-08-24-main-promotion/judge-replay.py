"""Judge-only replay: same v2 judge, same rendered surface, two recorded texts.

Isolates the grader. The product is not run at all.
"""
import json, os, sys

TREE = os.environ["TREE"]
sys.path.insert(0, TREE)
from tests.evals.measurement_eval_harness import (  # noqa: E402
    load_eval_cases, judge_prose_quality, PROSE_JUDGE_RUBRIC_VERSION,
)

CASE = "capability_honesty_future_performance_btc_regression"
N = int(os.environ.get("N", "3"))

BASELINE_TEXT = (
    "I can't predict future value, but I can test how that $10,000 buy-and-hold "
    "would have performed historically. Would you like to see the results over a "
    "past period, or compare it with a buy-and-hold benchmark?"
)
CANDIDATE_TEXT = (
    "I can't predict future value, but I can test how a $10,000 Bitcoin buy-and-hold "
    "would have performed over a historical period. Would you like to run that "
    "historical test, or compare it with another strategy?"
)
SURFACE = {
    "recovery_options": [
        {"id": "option_0", "label": "Test this idea over a historical period"},
        {"id": "buy_and_hold", "label": "Compare with buy and hold historically"},
    ]
}

case = {c.id: c for c in load_eval_cases()}[CASE]
print(f"rubric under test: {PROSE_JUDGE_RUBRIC_VERSION}", flush=True)

out = {}
for side, text in (("baseline_text", BASELINE_TEXT), ("candidate_text", CANDIDATE_TEXT)):
    verdicts = []
    for i in range(N):
        r = judge_prose_quality(case=case, assistant_text=text, rendered_beside_reply=SURFACE)
        verdicts.append("PASS" if r["pass"] else "FAIL")
        print(f"  {side} {i+1}: {verdicts[-1]} {','.join(r['failed_criteria'])}", flush=True)
        if not r["pass"]:
            print(f"      note: {r['notes'][:160]}", flush=True)
    out[side] = verdicts
print(json.dumps(out))
