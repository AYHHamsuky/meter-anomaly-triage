"""
Scoring. The same function scores the baseline and every agent variant.

Primary metric: disposition accuracy. That is the decision the billing officer
actually has to get right, and everything downstream (the adjustment, the letter,
whether an inspection is raised) follows from it.

Supporting metrics:
  action_correct        did it recommend the right next step
  adjustment_ok         is the naira figure within tolerance of the correct one
  evidence_coverage     fraction of the tools that hold the deciding evidence
                        which the run actually called
  memo_usable           the letter exists, is a reasonable length, and names the
                        figure when there is one
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOLERANCE = 0.02  # 2 percent on the adjustment amount


def load_ground_truth():
    with open(os.path.join(ROOT, "data", "ground_truth.json")) as fh:
        return json.load(fh)


def _num(v):
    try:
        return float(str(v).replace(",", "").replace("NGN", "").strip())
    except (TypeError, ValueError):
        return None


def score_case(result, truth):
    f = result.get("finding") or {}
    got_disp = (f.get("disposition") or "").strip().upper()
    want_disp = truth["disposition"]

    got_action = (f.get("recommended_action") or "").strip().upper()
    want_action = truth["action"]

    got_adj = _num(f.get("adjustment_ngn"))
    want_adj = float(truth["adjustment_ngn"])
    if got_adj is None:
        adj_ok = False
    elif want_adj == 0:
        adj_ok = abs(got_adj) < 1
    else:
        adj_ok = abs(got_adj - want_adj) <= TOLERANCE * want_adj

    required = set(truth.get("required_tools", []))
    called = set(result.get("tools_called") or [])
    coverage = 1.0 if not required else round(len(required & called) / len(required), 3)

    memo = (f.get("customer_memo") or "").strip()
    words = len(memo.split())
    names_figure = True
    if want_adj > 0:
        stripped = memo.replace(",", "")
        names_figure = any(str(int(want_adj))[:4] in stripped for _ in [0]) or f"{want_adj:,.0f}" in memo
    memo_usable = bool(memo) and 40 <= words <= 400 and names_figure

    return {
        "case_id": result.get("case_id"),
        "expected_disposition": want_disp,
        "got_disposition": got_disp or None,
        "disposition_correct": got_disp == want_disp,
        "expected_action": want_action,
        "got_action": got_action or None,
        "action_correct": got_action == want_action,
        "expected_adjustment_ngn": want_adj,
        "got_adjustment_ngn": got_adj,
        "adjustment_ok": adj_ok,
        "evidence_coverage": coverage,
        "required_tools": sorted(required),
        "tools_called": sorted(called),
        "memo_words": words,
        "memo_usable": memo_usable,
        "verifier_rounds": result.get("verifier_rounds", 0),
        "wall_seconds": result.get("wall_seconds"),
        "cost_usd": (result.get("usage") or {}).get("cost_usd", 0),
        "error": result.get("error"),
    }


def aggregate(scored):
    n = len(scored) or 1
    return {
        "cases": len(scored),
        "disposition_accuracy": round(sum(s["disposition_correct"] for s in scored) / n, 3),
        "action_accuracy": round(sum(s["action_correct"] for s in scored) / n, 3),
        "adjustment_accuracy": round(sum(s["adjustment_ok"] for s in scored) / n, 3),
        "mean_evidence_coverage": round(sum(s["evidence_coverage"] for s in scored) / n, 3),
        "memo_usable_rate": round(sum(s["memo_usable"] for s in scored) / n, 3),
        "mean_wall_seconds": round(sum(s["wall_seconds"] or 0 for s in scored) / n, 2),
        "total_cost_usd": round(sum(s["cost_usd"] or 0 for s in scored), 4),
        "cost_per_case_usd": round(sum(s["cost_usd"] or 0 for s in scored) / n, 5),
        "errors": sum(1 for s in scored if s["error"]),
    }
