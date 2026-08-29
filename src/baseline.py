"""
The baseline: one direct prompt with basic instructions.

This is what someone reaches for first. The whole case record is pasted in,
the model is asked for a decision, and there are no tools, no policy file and
no checking. Same model and same task as the agent, so the comparison is fair.

    python -m src.baseline --case CASE-02
"""

import argparse
import json
import time

from src import llm, tools
from src.trajectory import Trajectory

DISPOSITIONS = [
    "NO_ANOMALY", "ESTIMATION_OVERBILLING", "ESTIMATION_UNDERBILLING",
    "TARIFF_BAND_MISCLASSIFICATION", "FAULTY_METER", "METER_BYPASS_SUSPECTED",
    "UNBILLED_PERIOD", "DOUBLE_BILLING", "PAYMENT_NOT_POSTED",
]

SYSTEM = (
    "You are a billing officer at an electricity distribution company. You review "
    "disputed customer accounts and decide what is wrong and what should be done."
)

PROMPT = """Here is a disputed account.

{case}

Decide what is wrong with this account and what should happen next.

Reply with only a JSON object:
{{
  "disposition": one of {dispositions},
  "recommended_action": one of ["NO_ACTION","CREDIT_ADJUSTMENT","DEBIT_ADJUSTMENT","METER_REPLACEMENT","FIELD_INSPECTION","POST_PAYMENT"],
  "adjustment_ngn": number (0 if none),
  "adjustment_direction": one of ["CREDIT_CUSTOMER","DEBIT_CUSTOMER","NONE"],
  "confidence": one of ["HIGH","MEDIUM","LOW"],
  "evidence": [{{"claim": "...", "source": "..."}}],
  "approval_role": "...",
  "customer_memo": "the message to send to the customer"
}}"""


def run(case_id, model=None, provider=None, tag=None):
    case = tools.load_case(case_id)
    traj = Trajectory("baseline", case_id, "v0", model or llm.DEFAULT_MODEL, tag=tag)
    usage = llm.Usage()
    t0 = time.time()

    user = PROMPT.format(case=json.dumps(case, indent=2), dispositions=DISPOSITIONS)
    traj.instructions(SYSTEM, user)

    msg = llm.complete([{"role": "user", "content": user}], SYSTEM,
                       max_tokens=2000, model=model, provider=provider)
    traj.model_turn(msg)
    usage.add(msg.get("usage", {}))

    try:
        finding = llm.parse_json_block(llm.text_of(msg))
        error = None
    except Exception as exc:
        finding, error = {}, f"unparseable reply: {exc}"

    out = {
        "case_id": case_id,
        "variant": "v0-baseline",
        "finding": finding,
        "error": error,
        "tools_called": [],
        "verifier_rounds": 0,
        "wall_seconds": round(time.time() - t0, 2),
        "usage": usage.as_dict(),
        "trajectory": traj.path,
    }
    traj.finish(out["finding"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--model")
    ap.add_argument("--provider")
    args = ap.parse_args()
    print(json.dumps(run(args.case, args.model, args.provider), indent=2))


if __name__ == "__main__":
    main()
