"""
The tools the triage agent can call. Every tool reads from the case record and
returns a small, typed slice of it. Nothing here writes to a real system: an
adjustment is only ever proposed, never posted (ground rule 04).

compute_consumption_stats is the one tool that does arithmetic. It exists
because the failure the baseline keeps making is arithmetic, not reasoning.
"""

import json
import os
from statistics import median

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def load_case(case_id):
    with open(os.path.join(DATA, "cases", f"{case_id}.json")) as fh:
        return json.load(fh)


def load_tariff_table():
    with open(os.path.join(DATA, "tariff_table.json")) as fh:
        return json.load(fh)


def all_case_ids():
    files = sorted(os.listdir(os.path.join(DATA, "cases")))
    return [f[:-5] for f in files if f.endswith(".json")]


# --------------------------------------------------------------------------
# tool implementations
# --------------------------------------------------------------------------

def get_account_summary(case, **_):
    a = case["account"]
    return {
        "account_no": a["account_no"],
        "customer_name": a["customer_name"],
        "tariff_class": a["tariff_class"],
        "service_band_on_record": a["service_band_on_record"],
        "band_used_for_billing": a["band_used_for_billing"],
        "meter_type": a["meter_type"],
        "feeder": a["feeder"],
        "outstanding_arrears_ngn": a["outstanding_arrears_ngn"],
        "complaint": case["complaint"],
    }


def get_billing_history(case, months=None, **_):
    rows = case["billing_history"]
    if months:
        rows = [r for r in rows if r["month"] in months]
    return {
        "rows": rows,
        "month_count": len({r["month"] for r in rows}),
        "invoice_count": len(rows),
    }


def get_meter_reads(case, **_):
    return {"reads": case["meter_reads"], "read_count": len(case["meter_reads"])}


def get_payments(case, **_):
    rows = case["payments"]
    return {
        "payments": rows,
        "total_paid_ngn": round(sum(p["amount_ngn"] for p in rows), 2),
        "payment_count": len(rows),
    }


def get_field_notes(case, **_):
    return {"notes": case["field_notes"], "note_count": len(case["field_notes"])}


def lookup_tariff(case, tariff_class=None, band=None, **_):
    table = load_tariff_table()
    if tariff_class and band:
        key = f"{tariff_class}|{band}"
        if key not in table:
            return {"error": f"no rate on file for {key}", "available": sorted(table)}
        return {"tariff_class": tariff_class, "band": band, "rate_ngn_per_kwh": table[key]}
    return {"table": table}


def compute_consumption_stats(case, **_):
    """Reconcile reads against invoices and surface the numbers that decide a case."""
    bills = sorted(case["billing_history"], key=lambda r: (r["month"], r["invoice_no"]))
    reads = sorted(case["meter_reads"], key=lambda r: r["date"])

    by_month = {}
    for b in bills:
        by_month.setdefault(b["month"], []).append(b)

    duplicates = [
        {"month": m, "invoices": [x["invoice_no"] for x in v]}
        for m, v in by_month.items() if len(v) > 1
    ]

    read_deltas = []
    for prev, cur in zip(reads, reads[1:]):
        delta = round(cur["reading"] - prev["reading"], 1)
        rolled = False
        if delta < 0:
            # five digit register rollover
            rolled = True
            delta = round(cur["reading"] + 100000 - prev["reading"], 1)
        read_deltas.append({
            "from_date": prev["date"], "to_date": cur["date"],
            "from_reading": prev["reading"], "to_reading": cur["reading"],
            "kwh": delta, "register_rollover_applied": rolled,
        })

    stalled = [d for d in read_deltas if d["kwh"] == 0]
    rollovers = [d for d in read_deltas if d["register_rollover_applied"]]

    estimated = [b for b in bills if b["basis"] == "ESTIMATE"]
    actual = [b for b in bills if b["basis"] == "ACTUAL_READ"]
    est_runs = []
    run = []
    for b in bills:
        if b["basis"] == "ESTIMATE":
            run.append(b["month"])
        elif run:
            est_runs.append(run)
            run = []
    if run:
        est_runs.append(run)

    est_reconciliation = []
    for months in est_runs:
        first, last = months[0], months[-1]
        billed = sum(b["billed_kwh"] for b in bills if b["month"] in months)
        before = [r for r in reads if r["date"][:7] < first]
        after = [r for r in reads if r["date"][:7] > last]
        entry = {"months": months, "billed_kwh": billed}
        if before and after:
            span_start, span_end = before[-1], after[0]
            span_kwh = round(span_end["reading"] - span_start["reading"], 1)
            if span_kwh < 0:
                span_kwh = round(span_end["reading"] + 100000 - span_start["reading"], 1)
            billed_in_span = sum(
                b["billed_kwh"] for b in bills
                if span_start["date"][:7] < b["month"] <= span_end["date"][:7]
            )
            entry.update({
                "bracketing_reads": {"from": span_start, "to": span_end},
                "actual_kwh_across_span": span_kwh,
                "billed_kwh_across_span": billed_in_span,
                "difference_kwh": round(billed_in_span - span_kwh, 1),
                "direction": "OVERBILLED" if billed_in_span > span_kwh else "UNDERBILLED",
            })
        else:
            entry["bracketing_reads"] = None
            entry["note"] = "no actual read on both sides of this estimate run"
        est_reconciliation.append(entry)

    monthly = [b["billed_kwh"] for b in bills]
    baseline_window = monthly[:5] or monthly
    recent_window = monthly[-5:] or monthly
    med_base = median(baseline_window) if baseline_window else 0
    med_recent = median(recent_window) if recent_window else 0
    drop_pct = None
    if med_base:
        drop_pct = round((med_base - med_recent) / med_base * 100, 1)

    rate_check = []
    table = load_tariff_table()
    a = case["account"]
    correct_rate = table.get(f"{a['tariff_class']}|{a['service_band_on_record']}")
    for b in bills:
        expected = round(b["billed_kwh"] * b["rate_applied_ngn_per_kwh"], 2)
        if abs(expected - b["amount_ngn"]) > 0.5:
            rate_check.append({"month": b["month"], "invoice_no": b["invoice_no"],
                               "amount_ngn": b["amount_ngn"], "kwh_times_rate": expected})
    wrong_rate_months = [
        {"month": b["month"], "rate_applied": b["rate_applied_ngn_per_kwh"],
         "rate_on_record": correct_rate}
        for b in bills
        if correct_rate is not None and abs(b["rate_applied_ngn_per_kwh"] - correct_rate) > 0.01
    ]

    read_months = sorted({r["date"][:7] for r in reads})
    billed_months = sorted(by_month)
    unbilled_months = [m for m in read_months if m not in billed_months and m >= min(billed_months or ["9999"])]

    return {
        "billed_months": billed_months,
        "months_with_reads": read_months,
        "months_with_a_read_but_no_invoice": unbilled_months,
        "duplicate_invoice_months": duplicates,
        "estimated_month_count": len(estimated),
        "actual_read_month_count": len(actual),
        "estimate_run_reconciliation": est_reconciliation,
        "read_deltas": read_deltas,
        "zero_delta_periods": stalled,
        "register_rollovers": rollovers,
        "median_kwh_first_5_months": med_base,
        "median_kwh_last_5_months": med_recent,
        "consumption_drop_pct": drop_pct,
        "tariff_rate_on_record": correct_rate,
        "months_billed_at_a_rate_other_than_record": wrong_rate_months,
        "invoice_amount_arithmetic_mismatches": rate_check,
        "total_billed_ngn": round(sum(b["amount_ngn"] for b in bills), 2),
        "total_paid_ngn": round(sum(p["amount_ngn"] for p in case["payments"]), 2),
        "outstanding_arrears_ngn": case["account"]["outstanding_arrears_ngn"],
    }


REGISTRY = {
    "get_account_summary": get_account_summary,
    "get_billing_history": get_billing_history,
    "get_meter_reads": get_meter_reads,
    "get_payments": get_payments,
    "get_field_notes": get_field_notes,
    "lookup_tariff": lookup_tariff,
    "compute_consumption_stats": compute_consumption_stats,
}

SCHEMAS = [
    {
        "name": "get_account_summary",
        "description": "Account identity, tariff class, the band on record, the band actually used for "
                       "billing, meter type, arrears and the customer complaint.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_billing_history",
        "description": "Every invoice raised on the account: month, invoice number, billed kWh, rate applied, "
                       "amount and whether the month was an actual read or an estimate.",
        "input_schema": {
            "type": "object",
            "properties": {"months": {"type": "array", "items": {"type": "string"},
                                      "description": "Optional YYYY-MM filter."}},
        },
    },
    {
        "name": "get_meter_reads",
        "description": "Every meter reading on file with its date and source.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_payments",
        "description": "Payments received on the account with dates, amounts and references.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_field_notes",
        "description": "Notes written by read teams, marketing staff and auditors who visited the premises. "
                       "These carry the physical facts the numbers cannot show.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "lookup_tariff",
        "description": "The approved rate in naira per kWh for a tariff class and band. Call with no "
                       "arguments to get the whole table.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tariff_class": {"type": "string"},
                "band": {"type": "string"},
            },
        },
    },
    {
        "name": "compute_consumption_stats",
        "description": "Reconciles reads against invoices and returns the derived figures: read deltas, "
                       "register rollovers, stalled periods, estimate run reconciliation against bracketing "
                       "reads, duplicate invoices, months with a read but no invoice, rate mismatches and "
                       "the consumption trend. Use this instead of doing the arithmetic yourself.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def run_tool(name, case, arguments):
    if name not in REGISTRY:
        return {"error": f"unknown tool {name}", "available": sorted(REGISTRY)}
    try:
        return REGISTRY[name](case, **(arguments or {}))
    except TypeError as exc:
        return {"error": f"bad arguments for {name}: {exc}"}
