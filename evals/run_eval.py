"""
Run one arm of the evaluation over the whole case set and score it.

    python -m evals.run_eval --arm baseline
    python -m evals.run_eval --arm v4
    python -m evals.run_eval --compare            # table across every arm already run

Arms: baseline, v1, v2, v3, v4. Every arm sees the same cases and is scored by
the same function in evals/score.py.
"""

import argparse
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evals import score as scoring  # noqa: E402
from src import agent, baseline, llm, tools  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")

ARMS = ["baseline", "v1", "v2", "v3", "v4"]
LABELS = {
    "baseline": "v0 baseline, one direct prompt",
    "v1": "v1 tool loop",
    "v2": "v2 tool loop + policy skill",
    "v3": "v3 + verifier",
    "v4": "v4 + memo writer (final)",
}


def run_arm(arm, case_ids, provider=None, model=None):
    rows = []
    for cid in case_ids:
        print(f"  {arm:9s} {cid} ... ", end="", flush=True)
        try:
            if arm == "baseline":
                r = baseline.run(cid, model=model, provider=provider, tag=arm)
            else:
                r = agent.run(cid, variant=arm, model=model, provider=provider, tag=arm)
        except Exception as exc:
            traceback.print_exc()
            r = {"case_id": cid, "variant": arm, "finding": {}, "error": str(exc),
                 "tools_called": [], "wall_seconds": 0, "usage": {}}
        got = (r.get("finding") or {}).get("disposition")
        print(f"{got or 'ERROR'} ({r.get('wall_seconds')}s)")
        rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=ARMS)
    ap.add_argument("--cases", default="all", help="'all' or a comma separated list of case ids")
    ap.add_argument("--provider", help="anthropic or mock; defaults to TRIAGE_PROVIDER")
    ap.add_argument("--model")
    ap.add_argument("--compare", action="store_true", help="print the table across saved arms")
    args = ap.parse_args()

    os.makedirs(RESULTS, exist_ok=True)

    if args.compare:
        print_comparison()
        return

    if not args.arm:
        ap.error("--arm is required unless --compare is given")

    case_ids = tools.all_case_ids() if args.cases == "all" else args.cases.split(",")
    provider = args.provider or llm.PROVIDER
    print(f"arm={args.arm} provider={provider} model={args.model or llm.DEFAULT_MODEL} "
          f"cases={len(case_ids)}")
    if provider == "mock":
        print("  NOTE: mock provider. This is a smoke test, not evidence.")

    raw = run_arm(args.arm, case_ids, provider=provider, model=args.model)
    truth = scoring.load_ground_truth()
    scored = [scoring.score_case(r, truth[r["case_id"]]) for r in raw]
    summary = scoring.aggregate(scored)
    summary["arm"] = args.arm
    summary["provider"] = provider
    summary["model"] = args.model or llm.DEFAULT_MODEL

    out = {"summary": summary, "scored": scored, "raw": raw}
    path = os.path.join(RESULTS, f"{args.arm}.json")
    with open(path, "w") as fh:
        json.dump(out, fh, indent=2, default=str)

    print()
    print(json.dumps(summary, indent=2))
    print(f"\nwrote {path}")
    misses = [s for s in scored if not s["disposition_correct"]]
    if misses:
        print("\nmissed cases:")
        for m in misses:
            print(f"  {m['case_id']}: expected {m['expected_disposition']}, got {m['got_disposition']}")


def print_comparison():
    rows = []
    for arm in ARMS:
        p = os.path.join(RESULTS, f"{arm}.json")
        if os.path.exists(p):
            with open(p) as fh:
                rows.append(json.load(fh)["summary"])
    if not rows:
        print("no results yet. run an arm first.")
        return

    cols = [("arm", "arm"), ("disposition_accuracy", "disposition"),
            ("action_accuracy", "action"), ("adjustment_accuracy", "adjustment"),
            ("mean_evidence_coverage", "evidence"), ("memo_usable_rate", "memo"),
            ("cost_per_case_usd", "usd/case"), ("mean_wall_seconds", "sec/case")]
    header = " | ".join(f"{label:>12s}" for _, label in cols)
    print(header)
    print("-" * len(header))
    for r in rows:
        cells = []
        for key, _ in cols:
            v = r.get(key)
            cells.append(f"{LABELS.get(v, v):>12s}" if key == "arm" and False else f"{v:>12}")
        print(" | ".join(cells))
    print()
    for r in rows:
        print(f"{r['arm']:>9s}  {LABELS[r['arm']]}  (provider={r.get('provider')}, model={r.get('model')})")


if __name__ == "__main__":
    main()
