# Billing dispute adjudication policy

This is the working rule set a revenue billing officer applies to a disputed
account. It is synthetic and written for this exercise; it is modelled on the
shape of a distribution company's internal procedure, not copied from one.

## Dispositions

Exactly one disposition per case.

| Disposition | Use when |
|---|---|
| `NO_ANOMALY` | Reads reconcile with invoices, the rate matches the band on record, and any movement in consumption has an explanation in the record. |
| `ESTIMATION_OVERBILLING` | A run of estimated months billed more kWh than the actual reads bracketing that run can account for. |
| `ESTIMATION_UNDERBILLING` | A run of estimated months billed less kWh than the bracketing reads account for. |
| `TARIFF_BAND_MISCLASSIFICATION` | Invoices were raised at a rate other than the approved rate for the tariff class and band on record. |
| `FAULTY_METER` | The register is stalled, has rolled over, or otherwise cannot be reconciled with the physical load on the premises. |
| `METER_BYPASS_SUSPECTED` | Recorded consumption falls away while the record shows load that should still be drawing energy, and there is a physical indicator of interference. |
| `UNBILLED_PERIOD` | A month has a meter read but no invoice. |
| `DOUBLE_BILLING` | Two or more invoices exist for the same month and the same consumption. |
| `PAYMENT_NOT_POSTED` | A payment on the register has not been reflected in arrears. |

## Decision rules

1. **Read the field notes before deciding anything about consumption.** A drop in
   consumption is a question, not an answer. Vacancy, closure, seasonal shutdown
   and load removal all look identical to bypass in the numbers alone.
2. **A bypass finding needs a physical indicator**, not just a numeric drop:
   a broken or mismatched seal, an unsealed junction box, a tampered board, an
   observed direct connection. An intact seal that matches the installation
   record is evidence against bypass.
3. **Never reconcile an estimate run without reads on both sides of it.** If the
   run is not bracketed, say so and request a read rather than guessing.
4. **A negative read delta on a five digit register is a rollover**, not a
   credit and not a reversal. Recompute as `(current + 100000) - previous`.
5. **A stalled register on an occupied premises is a faulty meter**, and the
   remedy is replacement. Do not raise a theft case on a stalled meter alone.
6. **Check the rate on every invoice against the band on record**, not only on
   the disputed month.
7. **Recovery from the customer is capped at three months** of back-billing where
   the omission or the under-estimate is the utility's. State the cap when it
   applies and offer an instalment plan.

## Adjustment arithmetic

- Estimation error: `(billed kWh across the span − actual kWh across the span) × approved rate`.
- Band misclassification: `total kWh × (rate applied − approved rate)`.
- Rollover: reverse the invoice and reissue at the corrected kWh; the adjustment
  is the difference between the two amounts.
- Duplicate invoice: reverse the later invoice in full.
- Unposted payment: post the payment; the adjustment equals the payment.
- Bypass suspicion: **no adjustment before the inspection report**.

Round to two decimals. Show the arithmetic in the memo.

## Approval and escalation

Nothing here is posted automatically. Every case produces a recommendation for a
named human role:

- Adjustments up to NGN 100,000: Billing Supervisor.
- Adjustments above NGN 100,000: Revenue Assurance Manager.
- Any bypass or theft suspicion: joint inspection by Revenue Protection and the
  Customer Care Unit, with the customer invited to be present.
- Any disconnection order touched by the case is suspended until the case closes.

## The memo

The memo is what the customer care officer sends. It is signed by a person, so it
reads like a person wrote it: no headings that restate the obvious, no filler,
every figure traceable to a source in the record, and plain language about what
happens next and by when.
