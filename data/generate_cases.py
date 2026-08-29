"""
Build the synthetic evaluation set for the meter anomaly triage workflow.

Every case is fabricated. No real customer, account, meter or feeder data is
used anywhere in this project (ground rule 07). Running this file twice
produces byte-identical output.

    python data/generate_cases.py
"""

import calendar
import json
import os
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
CASE_DIR = os.path.join(HERE, "cases")

# Synthetic tariff table. Rates are NGN per kWh, keyed by (tariff_class, band).
TARIFF_TABLE = {
    ("R1", "C"): 32.50,
    ("R2", "A"): 209.50,
    ("R2", "B"): 63.00,
    ("R2", "C"): 51.20,
    ("R2", "D"): 43.30,
    ("C1", "A"): 225.00,
    ("C1", "B"): 68.40,
    ("C1", "C"): 55.00,
    ("D1", "A"): 240.00,
}

MONTHS = [
    "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12",
    "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06",
]


def month_end(m):
    y, mo = (int(x) for x in m.split("-"))
    return date(y, mo, calendar.monthrange(y, mo)[1]).isoformat()


def build(case_id, account, kwh, basis, rate_used, opening_read, field_notes,
          complaint, payments=None, overrides=None, meter_reads=None):
    """Assemble a case from a monthly kWh series."""
    overrides = overrides or {}
    bills, reads = [], []
    reading = opening_read
    reads.append({"date": "2025-06-30", "reading": round(reading, 1), "source": "FIELD"})
    for i, m in enumerate(MONTHS):
        used = kwh[i]
        reading += used
        b = basis[i]
        amount = round(used * rate_used[i], 2)
        entry = {
            "month": m,
            "invoice_no": f"{case_id}-INV-{i + 1:02d}",
            "billed_kwh": used,
            "rate_applied_ngn_per_kwh": rate_used[i],
            "amount_ngn": amount,
            "basis": b,
        }
        if m in overrides.get("bill_patch", {}):
            entry.update(overrides["bill_patch"][m])
        bills.append(entry)
        if b == "ACTUAL_READ":
            reads.append({"date": month_end(m), "reading": round(reading, 1), "source": "FIELD"})

    if meter_reads is not None:
        reads = meter_reads
    for extra in overrides.get("extra_bills", []):
        bills.append(extra)
    for drop in overrides.get("drop_months", []):
        bills = [b for b in bills if b["month"] != drop]

    return {
        "case_id": case_id,
        "opened_on": "2026-07-06",
        "account": account,
        "billing_history": bills,
        "meter_reads": reads,
        "payments": payments or [],
        "field_notes": field_notes,
        "complaint": complaint,
        "tariff_reference": "SYNTHETIC-TARIFF-2026",
    }


def acct(no, name, cls, band, meter_type="POSTPAID_METERED", feeder="Synthetic Feeder 11kV",
         billed_band=None, arrears=0.0):
    return {
        "account_no": no,
        "customer_name": name,
        "tariff_class": cls,
        "service_band_on_record": band,
        "band_used_for_billing": billed_band or band,
        "meter_type": meter_type,
        "feeder": feeder,
        "connection_date": "2019-03-11",
        "outstanding_arrears_ngn": arrears,
    }


def flat(v, n=12):
    return [v] * n


CASES = []
GT = {}


def add(case, gt):
    CASES.append(case)
    GT[case["case_id"]] = gt


# 01 - clean account, genuine seasonal increase
r = TARIFF_TABLE[("R2", "C")]
add(
    build(
        "CASE-01",
        acct("SYN-1001", "Halima Bala", "R2", "C"),
        kwh=[210, 205, 198, 221, 240, 268, 302, 315, 288, 244, 219, 214],
        basis=flat("ACTUAL_READ"),
        rate_used=flat(r),
        opening_read=4120.0,
        field_notes=["2026-03-02 marketing visit: 3-bedroom flat, two split AC units installed January 2026."],
        complaint={"date": "2026-03-09", "channel": "WhatsApp",
                   "text": "My bill jumped from about 12,000 to over 16,000. Nothing changed in my house."},
        payments=[{"date": f"{m}-15", "amount_ngn": 12000.0, "reference": f"PAY-01-{i}"} for i, m in enumerate(MONTHS)],
    ),
    {"disposition": "NO_ANOMALY", "action": "NO_ACTION", "adjustment_ngn": 0,
     "required_tools": ["get_billing_history", "get_meter_reads", "compute_consumption_stats"],
     "rationale": "Every month is on an actual read, read deltas match billed kWh, and the rate applied "
                  "matches the R2/C tariff. The increase tracks the two AC units installed in January."},
)

# 02 - long estimate run, then an actual read proving over-billing
r = TARIFF_TABLE[("R2", "B")]
kwh_02 = [180, 176, 420, 430, 445, 425, 440, 435, 168, 172, 175, 170]
basis_02 = ["ACTUAL_READ", "ACTUAL_READ"] + ["ESTIMATE"] * 6 + ["ACTUAL_READ"] * 4
reads_02 = [
    {"date": "2025-06-30", "reading": 8890.0, "source": "FIELD"},
    {"date": "2025-07-31", "reading": 9070.0, "source": "FIELD"},
    {"date": "2025-08-31", "reading": 9246.0, "source": "FIELD"},
    {"date": "2026-02-28", "reading": 10502.0, "source": "FIELD"},
    {"date": "2026-03-31", "reading": 10670.0, "source": "FIELD"},
    {"date": "2026-04-30", "reading": 10842.0, "source": "FIELD"},
    {"date": "2026-05-31", "reading": 11017.0, "source": "FIELD"},
    {"date": "2026-06-30", "reading": 11187.0, "source": "FIELD"},
]
add(
    build(
        "CASE-02",
        acct("SYN-1002", "Ibrahim Sadiq", "R2", "B", arrears=214800.0),
        kwh=kwh_02, basis=basis_02, rate_used=flat(r), opening_read=8890.0,
        field_notes=["2026-02-28 read team: premises accessible, meter healthy, cumulative reading 10502."],
        complaint={"date": "2026-04-11", "channel": "Customer care desk",
                   "text": "For months nobody came to read my meter and the bills kept climbing. Now they say I owe over 200,000."},
        payments=[{"date": "2025-08-14", "amount_ngn": 22000.0, "reference": "PAY-02-1"},
                  {"date": "2025-11-19", "amount_ngn": 25000.0, "reference": "PAY-02-2"}],
        meter_reads=reads_02,
    ),
    {"disposition": "ESTIMATION_OVERBILLING", "action": "CREDIT_ADJUSTMENT", "adjustment_ngn": 84357.0,
     "required_tools": ["get_billing_history", "get_meter_reads", "compute_consumption_stats"],
     "rationale": "Six consecutive estimated months (Sep 2025 to Feb 2026) billed 2595 kWh, but the actual reads "
                  "either side of the estimate run (9246 to 10502) show only 1256 kWh was consumed. The 1339 kWh "
                  "difference must be credited at the R2/B rate of 63.00."},
)

# 03 - billed on the wrong band
add(
    build(
        "CASE-03",
        acct("SYN-1003", "Zainab Traders", "C1", "C", meter_type="POSTPAID_METERED",
             feeder="Synthetic Feeder 33kV", billed_band="B"),
        kwh=[640, 655, 610, 668, 702, 690, 715, 688, 640, 652, 630, 645],
        basis=flat("ACTUAL_READ"),
        rate_used=flat(TARIFF_TABLE[("C1", "B")]),
        opening_read=21400.0,
        field_notes=[
            "2026-02-18 feeder audit: supply availability on this feeder averaged 9.4 hours per day over the quarter.",
            "2026-02-18 audit note: accounts on this feeder are to be billed on Band C.",
        ],
        complaint={"date": "2026-05-04", "channel": "Email",
                   "text": "We are told we are a Band B customer but we hardly get light for ten hours a day."},
        payments=[{"date": f"{m}-20", "amount_ngn": 44000.0, "reference": f"PAY-03-{i}"} for i, m in enumerate(MONTHS)],
    ),
    {"disposition": "TARIFF_BAND_MISCLASSIFICATION", "action": "CREDIT_ADJUSTMENT", "adjustment_ngn": 106329.0,
     "required_tools": ["get_billing_history", "lookup_tariff", "get_field_notes"],
     "rationale": "The account is on record as C1/Band C and the feeder audit confirms 9.4 hours daily supply, "
                  "but all twelve months were billed at the Band B rate of 68.40 instead of 55.00. The 13.40 "
                  "per kWh overcharge across 7935 kWh must be credited."},
)

# 04 - stalled meter on an occupied premises
kwh_04 = [0, 0, 0, 0, 310, 305, 298, 312, 300, 295, 308, 301]
basis_04 = ["ACTUAL_READ"] * 4 + ["ESTIMATE"] * 8
reads_04 = [
    {"date": "2025-06-30", "reading": 15330.0, "source": "FIELD"},
    {"date": "2025-07-31", "reading": 15330.0, "source": "FIELD"},
    {"date": "2025-08-31", "reading": 15330.0, "source": "FIELD"},
    {"date": "2025-09-30", "reading": 15330.0, "source": "FIELD"},
    {"date": "2025-10-31", "reading": 15330.0, "source": "FIELD"},
]
add(
    build(
        "CASE-04",
        acct("SYN-1004", "Rahma Bakery", "C1", "B"),
        kwh=kwh_04, basis=basis_04, rate_used=flat(TARIFF_TABLE[("C1", "B")]), opening_read=15330.0,
        field_notes=[
            "2025-10-31 read team: reading unchanged at 15330 for the fourth consecutive month.",
            "2025-10-31 read team: bakery operating daily, two ovens and a chest freezer running during visit.",
        ],
        complaint={"date": "2025-11-02", "channel": "Field report",
                   "text": "Reader escalated: meter display static across four visits although the premises is busy."},
        payments=[{"date": "2026-01-16", "amount_ngn": 20000.0, "reference": "PAY-04-1"}],
    ),
    {"disposition": "FAULTY_METER", "action": "METER_REPLACEMENT", "adjustment_ngn": 0,
     "required_tools": ["get_meter_reads", "get_field_notes", "compute_consumption_stats"],
     "rationale": "The register held at 15330 across four consecutive field reads while the field team recorded "
                  "ovens and a freezer running. The meter has stalled and must be replaced; the estimated months "
                  "stand until a healthy meter establishes a real baseline."},
)

# 05 - genuine bypass suspicion: load went up, recorded consumption collapsed
kwh_05 = [880, 905, 869, 891, 902, 140, 132, 128, 145, 138, 130, 141]
add(
    build(
        "CASE-05",
        acct("SYN-1005", "Gwarzo Block Industry", "C1", "A"),
        kwh=kwh_05, basis=flat("ACTUAL_READ"), rate_used=flat(TARIFF_TABLE[("C1", "A")]),
        opening_read=64200.0,
        field_notes=[
            "2026-01-20 marketing visit: block moulding machine and a new 15HP borehole pump commissioned in December 2025.",
            "2026-01-20 visit: yard active, eight staff on site, production running six days a week.",
            "2026-04-02 audit: service cable enters the premises through an unsealed junction box beside the meter board.",
        ],
        complaint={"date": "2026-04-02", "channel": "Revenue protection referral",
                   "text": "Referred by revenue protection after a routine feeder loss review."},
        payments=[{"date": f"{m}-10", "amount_ngn": 40000.0, "reference": f"PAY-05-{i}"} for i, m in enumerate(MONTHS)],
    ),
    {"disposition": "METER_BYPASS_SUSPECTED", "action": "FIELD_INSPECTION", "adjustment_ngn": 0,
     "required_tools": ["get_billing_history", "compute_consumption_stats", "get_field_notes"],
     "rationale": "Recorded consumption fell about 85 percent from December 2025 while the field record shows new "
                  "load commissioned in the same month and an unsealed junction box beside the meter board. This "
                  "warrants a joint inspection; no adjustment may be raised before the inspection report."},
)

# 06 - three months never billed
add(
    build(
        "CASE-06",
        acct("SYN-1006", "Aminu Yusuf", "R2", "C"),
        kwh=[260, 255, 248, 266, 271, 259, 263, 258, 249, 262, 254, 260],
        basis=flat("ACTUAL_READ"), rate_used=flat(TARIFF_TABLE[("R2", "C")]), opening_read=3050.0,
        field_notes=["2026-06-30 billing audit: account absent from the October, November and December 2025 billing runs."],
        complaint={"date": "2026-07-01", "channel": "Internal audit",
                   "text": "Audit flagged a gap between the read register and the billing register for this account."},
        payments=[],
        overrides={"drop_months": ["2025-10", "2025-11", "2025-12"]},
    ),
    {"disposition": "UNBILLED_PERIOD", "action": "DEBIT_ADJUSTMENT", "adjustment_ngn": 40755.2,
     "required_tools": ["get_billing_history", "get_meter_reads", "compute_consumption_stats"],
     "rationale": "Reads exist for October to December 2025 but no invoice was raised. The 786 kWh recorded in "
                  "those months is billable at the R2/C rate. Because the omission is the utility's, the debit "
                  "should be raised transparently and offered on an instalment plan."},
)

# 07 - duplicate invoice in one month
dup = {
    "month": "2026-02",
    "invoice_no": "CASE-07-INV-08B",
    "billed_kwh": 340,
    "rate_applied_ngn_per_kwh": TARIFF_TABLE[("R2", "B")],
    "amount_ngn": round(340 * TARIFF_TABLE[("R2", "B")], 2),
    "basis": "ACTUAL_READ",
}
add(
    build(
        "CASE-07",
        acct("SYN-1007", "Grace Okon", "R2", "B", arrears=21420.0),
        kwh=[318, 322, 305, 330, 344, 336, 328, 340, 316, 325, 319, 331],
        basis=flat("ACTUAL_READ"), rate_used=flat(TARIFF_TABLE[("R2", "B")]), opening_read=11870.0,
        field_notes=["2026-03-05 billing run note: February file reprocessed after a mid-run failure."],
        complaint={"date": "2026-03-07", "channel": "WhatsApp",
                   "text": "I received two bills for February with the same amount and my arrears went up."},
        payments=[{"date": "2026-02-20", "amount_ngn": 21420.0, "reference": "PAY-07-1"}],
        overrides={"extra_bills": [dup]},
    ),
    {"disposition": "DOUBLE_BILLING", "action": "CREDIT_ADJUSTMENT", "adjustment_ngn": 21420.0,
     "required_tools": ["get_billing_history"],
     "rationale": "Two invoices exist for February 2026 for the same 340 kWh, and the billing run note records a "
                  "reprocessed February file. The duplicate invoice must be reversed."},
)

# 08 - payment made but never posted
add(
    build(
        "CASE-08",
        acct("SYN-1008", "Musa Danladi", "R2", "C", arrears=48000.0),
        kwh=[230, 228, 240, 236, 244, 239, 231, 242, 227, 235, 238, 233],
        basis=flat("ACTUAL_READ"), rate_used=flat(TARIFF_TABLE[("R2", "C")]), opening_read=6600.0,
        field_notes=["2026-05-30 collections note: account listed for disconnection over unpaid arrears of 48,000."],
        complaint={"date": "2026-06-02", "channel": "Customer care desk",
                   "text": "I paid 48,000 at the bank in April and I have the teller receipt, but they still say I owe."},
        payments=[{"date": "2026-04-22", "amount_ngn": 48000.0, "reference": "PAY-08-BANK-4471"}],
    ),
    {"disposition": "PAYMENT_NOT_POSTED", "action": "POST_PAYMENT", "adjustment_ngn": 48000.0,
     "required_tools": ["get_payments", "get_billing_history"],
     "rationale": "A payment of 48,000 dated 22 April 2026 sits in the payment register while arrears still show "
                  "48,000 outstanding. The payment must be posted and the disconnection order withdrawn."},
)

# 09 - clean account, complaint driven by arrears not by consumption
add(
    build(
        "CASE-09",
        acct("SYN-1009", "Fatima Aliyu", "R1", "C"),
        kwh=[96, 92, 88, 101, 110, 118, 124, 121, 105, 99, 94, 97],
        basis=flat("ACTUAL_READ"), rate_used=flat(TARIFF_TABLE[("R1", "C")]), opening_read=1880.0,
        field_notes=["2026-04-14 marketing visit: single room apartment, fan, television and lighting only."],
        complaint={"date": "2026-04-15", "channel": "WhatsApp",
                   "text": "Why is my bill different every month? I use the same things every day."},
        payments=[{"date": f"{m}-25", "amount_ngn": 3400.0, "reference": f"PAY-09-{i}"} for i, m in enumerate(MONTHS)],
    ),
    {"disposition": "NO_ANOMALY", "action": "NO_ACTION", "adjustment_ngn": 0,
     "required_tools": ["get_billing_history", "get_meter_reads", "compute_consumption_stats"],
     "rationale": "All months are on actual reads, deltas reconcile with billed kWh and the rate is correct for "
                  "R1/C. Month to month variation is normal seasonal movement on a small load."},
)

# 10 - estimates below true consumption
kwh_10 = [520, 515, 300, 300, 300, 300, 528, 534, 519, 526, 531, 522]
basis_10 = ["ACTUAL_READ", "ACTUAL_READ"] + ["ESTIMATE"] * 4 + ["ACTUAL_READ"] * 6
reads_10 = [
    {"date": "2025-06-30", "reading": 30250.0, "source": "FIELD"},
    {"date": "2025-08-31", "reading": 31285.0, "source": "FIELD"},
    {"date": "2025-12-31", "reading": 33380.0, "source": "FIELD"},
    {"date": "2026-01-31", "reading": 33908.0, "source": "FIELD"},
    {"date": "2026-02-28", "reading": 34442.0, "source": "FIELD"},
    {"date": "2026-03-31", "reading": 34961.0, "source": "FIELD"},
    {"date": "2026-04-30", "reading": 35487.0, "source": "FIELD"},
    {"date": "2026-05-31", "reading": 36018.0, "source": "FIELD"},
    {"date": "2026-06-30", "reading": 36540.0, "source": "FIELD"},
]
add(
    build(
        "CASE-10",
        acct("SYN-1010", "Sabon Gari Cold Room", "C1", "B"),
        kwh=kwh_10, basis=basis_10, rate_used=flat(TARIFF_TABLE[("C1", "B")]), opening_read=30250.0,
        field_notes=["2025-12-31 read team: access restored after four months, cumulative reading 33380."],
        complaint={"date": "2026-01-08", "channel": "Internal audit",
                   "text": "Audit query on under-recovery for this account during the estimated period."},
        payments=[{"date": f"{m}-12", "amount_ngn": 30000.0, "reference": f"PAY-10-{i}"} for i, m in enumerate(MONTHS)],
        meter_reads=reads_10,
    ),
    {"disposition": "ESTIMATION_UNDERBILLING", "action": "DEBIT_ADJUSTMENT", "adjustment_ngn": 61218.0,
     "required_tools": ["get_billing_history", "get_meter_reads", "compute_consumption_stats"],
     "rationale": "The four estimated months billed 1200 kWh while the reads either side (31285 to 33380) show "
                  "2095 kWh consumed. The 895 kWh shortfall is recoverable, and the customer should be told how "
                  "the figure was derived and offered instalments."},
)

# 11 - register rollover misread as a huge month
kwh_11 = [430, 425, 418, 441, 436, 428, 99433, 415, 422, 430, 419, 427]
reads_11 = [
    {"date": "2025-06-30", "reading": 97100.0, "source": "FIELD"},
    {"date": "2025-07-31", "reading": 97530.0, "source": "FIELD"},
    {"date": "2025-08-31", "reading": 97955.0, "source": "FIELD"},
    {"date": "2025-09-30", "reading": 98373.0, "source": "FIELD"},
    {"date": "2025-10-31", "reading": 98814.0, "source": "FIELD"},
    {"date": "2025-11-30", "reading": 99250.0, "source": "FIELD"},
    {"date": "2025-12-31", "reading": 99678.0, "source": "FIELD"},
    {"date": "2026-01-31", "reading": 111.0, "source": "FIELD"},
    {"date": "2026-02-28", "reading": 526.0, "source": "FIELD"},
    {"date": "2026-03-31", "reading": 948.0, "source": "FIELD"},
    {"date": "2026-04-30", "reading": 1378.0, "source": "FIELD"},
    {"date": "2026-05-31", "reading": 1797.0, "source": "FIELD"},
    {"date": "2026-06-30", "reading": 2224.0, "source": "FIELD"},
]
add(
    build(
        "CASE-11",
        acct("SYN-1011", "Bello Hardware", "C1", "B", arrears=6801217.2),
        kwh=kwh_11, basis=flat("ACTUAL_READ"), rate_used=flat(TARIFF_TABLE[("C1", "B")]),
        opening_read=97100.0,
        field_notes=["2026-01-31 read team: five digit register, previous reading 99678, current reading 00111."],
        complaint={"date": "2026-02-03", "channel": "Customer care desk",
                   "text": "They have billed me almost seven million naira for one month. My shop cannot use that light in ten years."},
        payments=[{"date": f"{m}-18", "amount_ngn": 30000.0, "reference": f"PAY-11-{i}"} for i, m in enumerate(MONTHS)],
        meter_reads=reads_11,
    ),
    {"disposition": "FAULTY_METER", "action": "CREDIT_ADJUSTMENT", "adjustment_ngn": 6771600.0,
     "required_tools": ["get_meter_reads", "get_billing_history", "compute_consumption_stats"],
     "rationale": "The five digit register rolled over from 99678 to 00111, so January 2026 consumption is 433 kWh, "
                  "not 99433 kWh. The billing engine treated the rollover as a negative delta and issued a "
                  "6,801,217.20 naira invoice that must be reversed and reissued at 433 kWh."},
)

# 12 - challenging case: looks exactly like bypass, is actually a vacant premises
kwh_12 = [760, 742, 771, 755, 768, 90, 12, 9, 11, 8, 10, 9]
add(
    build(
        "CASE-12",
        acct("SYN-1012", "Tudun Wada Guest House", "C1", "B"),
        kwh=kwh_12, basis=flat("ACTUAL_READ"), rate_used=flat(TARIFF_TABLE[("C1", "B")]),
        opening_read=52800.0,
        field_notes=[
            "2025-12-05 marketing visit: guest house closed for renovation, generator set removed from the yard.",
            "2026-02-11 read team: premises padlocked, security man on site confirms building empty since December 2025.",
            "2026-02-11 read team: meter seal intact, seal number matches the installation record.",
            "2026-05-19 read team: renovation ongoing, only site lighting connected.",
        ],
        complaint={"date": "2026-06-01", "channel": "Revenue protection referral",
                   "text": "Flagged by the consumption drop rule for suspected energy theft."},
        payments=[{"date": "2026-03-14", "amount_ngn": 8000.0, "reference": "PAY-12-1"}],
    ),
    {"disposition": "NO_ANOMALY", "action": "NO_ACTION", "adjustment_ngn": 0,
     "required_tools": ["get_billing_history", "compute_consumption_stats", "get_field_notes"],
     "rationale": "Consumption collapsed in December 2025, but three independent field visits record the premises "
                  "closed for renovation with the meter seal intact and matching the installation record. The drop "
                  "is explained by vacancy, so no theft case should be raised.",
     "challenge_note": "This is the deliberate hard case. It matches the bypass pattern on the numbers alone and is "
                       "only resolved by reading the field notes, so it separates agents that look at evidence from "
                       "agents that pattern match on a consumption drop."},
)


def main():
    os.makedirs(CASE_DIR, exist_ok=True)
    for c in CASES:
        path = os.path.join(CASE_DIR, f"{c['case_id']}.json")
        with open(path, "w") as fh:
            json.dump(c, fh, indent=2, sort_keys=True)
    with open(os.path.join(HERE, "ground_truth.json"), "w") as fh:
        json.dump(GT, fh, indent=2, sort_keys=True)
    with open(os.path.join(HERE, "tariff_table.json"), "w") as fh:
        json.dump({f"{k[0]}|{k[1]}": v for k, v in TARIFF_TABLE.items()}, fh, indent=2, sort_keys=True)
    print(f"wrote {len(CASES)} cases to {CASE_DIR}")


if __name__ == "__main__":
    main()
