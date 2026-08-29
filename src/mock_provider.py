"""
Offline stand-in for the model, used to test that the wiring works without an
API key and without spending anything.

This is NOT a model. It answers from hardcoded rules. Its baseline path is
deliberately naive and its agent path is deliberately competent, because its
only job is to exercise the tool loop, the verifier branch and the writer
branch end to end.

Numbers produced under TRIAGE_PROVIDER=mock are a smoke test, never evidence.
Every figure in the report comes from a run against the real API.
"""

import json
import re

from src import tools

TOKENS = {"input_tokens": 0, "output_tokens": 0}


def _msg(content, stop_reason="end_turn"):
    return {"content": content, "stop_reason": stop_reason,
            "usage": dict(TOKENS), "model": "mock"}


def _text(t):
    return _msg([{"type": "text", "text": t}])


def _case_id(messages):
    blob = json.dumps(messages)
    m = re.search(r"CASE-\d{2}", blob)
    return m.group(0) if m else "CASE-01"


def _assistant_turns(messages):
    return sum(1 for m in messages if m["role"] == "assistant")


def _naive_finding(case):
    """The baseline path: complaint keywords only, no arithmetic."""
    text = case["complaint"]["text"].lower()
    if "two bills" in text or "double" in text:
        d, a = "DOUBLE_BILLING", "CREDIT_ADJUSTMENT"
    elif "paid" in text:
        d, a = "PAYMENT_NOT_POSTED", "POST_PAYMENT"
    elif "theft" in text or "protection" in text:
        d, a = "METER_BYPASS_SUSPECTED", "FIELD_INSPECTION"
    elif "read my meter" in text or "estimate" in text:
        d, a = "ESTIMATION_OVERBILLING", "CREDIT_ADJUSTMENT"
    else:
        d, a = "NO_ANOMALY", "NO_ACTION"
    return {
        "disposition": d, "recommended_action": a, "adjustment_ngn": 0,
        "adjustment_direction": "NONE", "confidence": "MEDIUM",
        "evidence": [{"claim": "read the complaint", "source": "complaint"}],
        "approval_role": "Billing Supervisor",
        "customer_memo": "We have reviewed your account and will revert.",
    }


def _stats_finding(case):
    """The agent path: decide from compute_consumption_stats plus field notes."""
    s = tools.compute_consumption_stats(case)
    notes = " ".join(case["field_notes"]).lower()
    rate = s["tariff_rate_on_record"] or 0
    d, a, adj, direction = "NO_ANOMALY", "NO_ACTION", 0.0, "NONE"

    if s["duplicate_invoice_months"]:
        month = s["duplicate_invoice_months"][0]["month"]
        dupes = [b for b in case["billing_history"] if b["month"] == month]
        d, a, direction = "DOUBLE_BILLING", "CREDIT_ADJUSTMENT", "CREDIT_CUSTOMER"
        adj = dupes[-1]["amount_ngn"]
    elif s["register_rollovers"]:
        d, a, direction = "FAULTY_METER", "CREDIT_ADJUSTMENT", "CREDIT_CUSTOMER"
        roll = s["register_rollovers"][0]
        month = roll["to_date"][:7]
        bill = next((b for b in case["billing_history"] if b["month"] == month), None)
        if bill:
            adj = round((bill["billed_kwh"] - roll["kwh"]) * bill["rate_applied_ngn_per_kwh"], 2)
    elif s["months_billed_at_a_rate_other_than_record"]:
        applied = s["months_billed_at_a_rate_other_than_record"][0]["rate_applied"]
        kwh = sum(b["billed_kwh"] for b in case["billing_history"])
        d, a, direction = "TARIFF_BAND_MISCLASSIFICATION", "CREDIT_ADJUSTMENT", "CREDIT_CUSTOMER"
        adj = round(kwh * (applied - rate), 2)
    elif s["months_with_a_read_but_no_invoice"]:
        missing = s["months_with_a_read_but_no_invoice"]
        kwh = 0
        reads = sorted(case["meter_reads"], key=lambda r: r["date"])
        for prev, cur in zip(reads, reads[1:]):
            if cur["date"][:7] in missing:
                kwh += cur["reading"] - prev["reading"]
        d, a, direction = "UNBILLED_PERIOD", "DEBIT_ADJUSTMENT", "DEBIT_CUSTOMER"
        adj = round(kwh * rate, 2)
    elif s["zero_delta_periods"] and len(s["zero_delta_periods"]) >= 3:
        d, a = "FAULTY_METER", "METER_REPLACEMENT"
    elif any(r.get("difference_kwh") for r in s["estimate_run_reconciliation"]):
        run = next(r for r in s["estimate_run_reconciliation"] if r.get("difference_kwh"))
        diff = run["difference_kwh"]
        if diff > 0:
            d, a, direction = "ESTIMATION_OVERBILLING", "CREDIT_ADJUSTMENT", "CREDIT_CUSTOMER"
        else:
            d, a, direction = "ESTIMATION_UNDERBILLING", "DEBIT_ADJUSTMENT", "DEBIT_CUSTOMER"
        adj = round(abs(diff) * rate, 2)
    elif (s["consumption_drop_pct"] or 0) > 60:
        physical = any(k in notes for k in ("unsealed", "tamper", "broken seal", "direct connection"))
        explained = any(k in notes for k in ("closed", "vacant", "empty", "padlock", "renovation"))
        if physical and not explained:
            d, a = "METER_BYPASS_SUSPECTED", "FIELD_INSPECTION"
    elif case["payments"] and abs(s["outstanding_arrears_ngn"] - sum(
            p["amount_ngn"] for p in case["payments"])) < 1:
        d, a, direction = "PAYMENT_NOT_POSTED", "POST_PAYMENT", "CREDIT_CUSTOMER"
        adj = s["outstanding_arrears_ngn"]

    if (not physical_check(notes)) and d == "METER_BYPASS_SUSPECTED":
        d, a = "NO_ANOMALY", "NO_ACTION"

    return {
        "disposition": d, "recommended_action": a, "adjustment_ngn": adj,
        "adjustment_direction": direction,
        "adjustment_working": "computed by the mock provider from compute_consumption_stats",
        "confidence": "HIGH",
        "evidence": [{"claim": "derived figures", "source": "compute_consumption_stats"},
                     {"claim": "premises condition", "source": "get_field_notes"}],
        "open_questions": [],
        "approval_role": ("Revenue Assurance Manager" if adj > 100000 else "Billing Supervisor"),
        "customer_memo": "Placeholder memo from the mock provider.",
    }


def physical_check(notes):
    return any(k in notes for k in ("unsealed", "tamper", "broken seal", "direct connection"))


def complete(messages, system, tools_schemas=None):
    case = tools.load_case(_case_id(messages))

    if system.startswith("You check a colleague"):
        return _text(json.dumps({"approved": True, "issues": []}))

    if system.startswith("You write to electricity customers"):
        name = case["account"]["customer_name"]
        return _text(
            f"Dear {name}, we have finished reviewing your account "
            f"{case['account']['account_no']}. This letter is placeholder text produced by the "
            "offline mock provider so the pipeline can be tested without an API key."
        )

    if not tools_schemas:  # baseline path
        return _text(json.dumps(_naive_finding(case)))

    turn = _assistant_turns(messages)
    if turn == 0:
        return _msg([
            {"type": "tool_use", "id": "m1", "name": "get_account_summary", "input": {}},
            {"type": "tool_use", "id": "m2", "name": "get_billing_history", "input": {}},
        ], stop_reason="tool_use")
    if turn == 1:
        return _msg([
            {"type": "tool_use", "id": "m3", "name": "get_meter_reads", "input": {}},
            {"type": "tool_use", "id": "m4", "name": "compute_consumption_stats", "input": {}},
            {"type": "tool_use", "id": "m5", "name": "get_field_notes", "input": {}},
            {"type": "tool_use", "id": "m6", "name": "get_payments", "input": {}},
        ], stop_reason="tool_use")
    return _text(json.dumps(_stats_finding(case)))
