# Meter anomaly triage

**An agent that adjudicates disputed electricity bills, shows its working, and drafts the
letter a customer care officer can sign.**

Submission for the micro1 Agentic Workflows Hackathon.

---

## Who has this problem

A revenue billing officer at an electricity distribution company. A customer walks into the
office or sends a message on WhatsApp saying the bill is wrong. Somebody has to decide, from
the account record, whether the customer is right, what the correct figure is, who must
approve the correction, and what to write back.

At a mid-sized distribution company this queue runs to hundreds of disputes a month, and the
officer working it is not a data analyst. They have a spreadsheet export, a meter reading
register, a payment register and a folder of field visit notes.

## What bottleneck makes it worth solving

Every dispute needs the same reconciliation, and it is fiddly rather than hard:

- Match twelve months of invoices against the meter readings that should justify them.
- Find the runs of estimated months and check them against the actual reads either side.
- Check the rate on every invoice against the band the account is actually on.
- Spot the duplicate invoice, the month that was never billed, the payment that never posted.
- Read the field notes, because a consumption collapse means one thing when the meter seal is
  broken and something completely different when the building is empty.

Done properly this is twenty to forty minutes per case. Done under pressure it collapses into
a judgement call, and the two failure modes are expensive in opposite directions. Wave a case
through and the company loses recoverable revenue. Raise a theft case against a customer whose
premises was simply vacant and the company creates a dispute it will lose, at a regulator that
publishes complaint statistics.

The output also has to be a letter, in plain language, that a named officer signs. A
disposition code alone does not close a case.

## What the agent does

One case in, one adjudication out:

```
complaint + account record
        ↓
  analyst agent  ──tools──►  account summary · billing history · meter reads ·
        │                    payments · field notes · tariff table ·
        │                    compute_consumption_stats
        ↓
  verifier pass  ──►  checks each figure against the tool results and the policy,
        │             returns issues; the analyst gets one corrective round
        ↓
  writer pass  ──►  drafts the customer letter from the verified finding
        ↓
  disposition · adjustment with its arithmetic · evidence list ·
  approval role · letter for signature
```

Nothing is posted. Every case ends queued for a named human role, and the amount decides which
role (`config/policy.md`).

### Why these pieces

- **Tools, not a paste.** The record is thirteen invoices, thirteen reads and a payment
  register. Pasted into a prompt it becomes a wall of numbers the model skims. Behind tools it
  becomes something the model pulls deliberately, and the trajectory shows what it looked at.
- **One tool does the arithmetic.** `compute_consumption_stats` reconciles reads against
  invoices, brackets each estimate run, handles register rollover, and finds duplicates,
  unbilled months and rate mismatches. The model reads figures instead of producing them.
- **The policy is a skill, not a prompt.** `config/policy.md` holds the disposition taxonomy,
  the decision rules, the adjustment arithmetic and the approval thresholds. It is loaded as
  instructions and it is the thing a billing supervisor would edit.
- **A verifier, because the analyst is confident when it is wrong.** The verifier's job is
  narrow and enumerated: figures with no source, arithmetic that does not follow, a bypass
  finding with no physical indicator, an estimate run reconciled without bracketing reads.
- **A separate writer, because the letter is the deliverable.** The analyst writes like an
  analyst. A separate pass with only the verified finding and the customer's own words in
  front of it writes something a person can sign.

## What existed before, what was built here

Built for this hackathon: everything in `src/`, `evals/`, `data/`, `config/` and `app/`.

Not built here: Python 3.11+, `requests`, `streamlit`, `pandas`, and the Anthropic Messages
API. No agent framework is used; the tool loop is about sixty lines in `src/agent.py` because
a framework would have hidden the part the judges need to read.

## The data

Twelve synthetic cases in `data/cases/`, generated deterministically by
`data/generate_cases.py`. No real customer, account, meter or feeder data appears anywhere in
this repository. Names, account numbers and feeders are invented; the tariff table is
synthetic. The adjudicated answer for each case, with its rationale, is in
`data/ground_truth.json`.

The set covers nine dispositions and is deliberately unbalanced the way a real queue is:
three cases have nothing wrong with them.

**The hard case is CASE-12.** A guest house drops from ~760 kWh a month to under 12. On the
numbers it is indistinguishable from CASE-05, which is a genuine bypass suspicion. The only
thing separating them is the field notes: CASE-12 has three visits recording a padlocked
building under renovation and an intact seal matching the installation record, while CASE-05
has new load commissioned in the same month consumption collapsed and an unsealed junction box
beside the meter board. Any system that triages on the consumption drop alone gets one of
these two wrong.

## Baseline

`src/baseline.py`. One direct prompt with basic instructions: the whole case record pasted in,
the same output schema requested, no tools, no policy, no checking. Same model, same
temperature, same cases, same scoring function as the agent.

The agent has tools the baseline does not; that is the difference under test. Both are given
the identical underlying record, so neither sees information the other cannot.

## How it is evaluated

Primary metric: **disposition accuracy**, because the disposition is the decision the officer
has to get right and everything downstream follows from it.

Supporting: action accuracy, adjustment within 2% of the correct naira figure, evidence
coverage (did the run consult the tools holding the deciding evidence), and whether the letter
is usable. Cost and wall time come from the token accounting in `src/llm.py`.

What good looks like for this user, set before running: **at least 10 of 12 dispositions
correct, no false theft accusation on CASE-12, and every naira figure traceable to a tool
result.** A system that scores well on accuracy but invents a figure has failed.

```
METRIC                    SIMPLE BASELINE           AGENT SOLUTION (v4)
                          run1     run2    avg       run1     run2    avg      CHANGE (avg)
Disposition accuracy      1.000    1.000   1.000     0.917    0.750   0.833    -0.167
Adjustment within 2%      0.583    0.667   0.625     0.917    0.833   0.875    +0.250
Evidence coverage         0.00     0.00    0.00      1.00     1.00    1.00     +1.00
Memo usable rate          0.75     0.75    0.75      1.00     0.833   0.917    +0.167
Review time per case (s)  14.7 (n=3, review only)             72.3 (n=3, review only)  +57.6
Manual triage (from scratch, no AI)                            not yet measured  config/time_study.json
Wall time per case (s)    12.29    12.98   12.6      132.63   58.36   95.5     +82.8
Cost per case (USD)       0.0164   0.0166  0.0165    0.1106   0.1055  0.108    +0.091 (~6.5x)
```

Two independent real runs, `claude-sonnet-4-5-20250929`, temperature 0, 12 cases each
(`results/run1/`, `results/run2/`, 2026-08-29 and 2026-08-30, two different API keys —
`claude-sonnet-5` itself rejects `temperature=0` on both, so the model string differs from
`.env.example`'s default; it is recorded in every result and trajectory file).

**On disposition accuracy the baseline beat v4 on both full 12-case sweeps (12/12 vs 11/12,
then 12/12 vs 9/12).** Rerunning was meant to check whether that was noise, per REPRODUCE.md's
own advice to rerun when a difference looks marginal. On the full-sweep metric it held up. On
the specific case driving most of it, CASE-05, the picture is more nuanced: **v4 got CASE-05
wrong on both full sweeps, and right on a third, separate real execution of the same case**
run afterward (`trajectories/agent-v4-CASE-05-v4-run3-app.jsonl`) — 2 wrong out of 3 real
executions, not a deterministic 100%. On the two runs where it failed, the verifier produced
nearly word-for-word the same wrong objection to the physical evidence
(`trajectories/agent-v4-CASE-05-v4.jsonl` vs `-run2`); on the one where it succeeded, the
verifier raised an unrelated objection (an arrears-figure inconsistency) and never challenged
the bypass evidence at all. That is a real, recurring failure mode at roughly this rate, not a
one-off — but it is a probability, not a guarantee. See the changelog and hot take below.

`config/time_study.json` holds the human timings. Review time (checking a finished output
before signing it) is measured on 3 of 12 cases: 14.7s average for the baseline's output,
72.3s for v4's — about 5x longer, largely because v4's letters are longer and its evidence
list is worth actually checking against the tools it cites. `manual_triage_minutes_per_case`
— a person working a case from the raw record with no AI at all, the number behind this
project's "20-40 minutes" bottleneck claim — has not been measured yet; see the file's
`method` field for exactly what has and hasn't been timed.

## Improvement changelog

Each row is a variant you can rerun on its own: `python -m evals.run_eval --arm v2`.

| Stage | What was tried and why | Evidence | Decision / learning |
|---|---|---|---|
| **Baseline** | One direct prompt with the full record pasted in. The obvious first thing to try. | `results/baseline.json` | 12/12 dispositions correct against a Sonnet-4.5-class model — the raw model is a stronger reader of a pasted record than expected. But adjustment accuracy was only 7/12 (0.583) and evidence coverage is 0 by construction: there is nothing to check a baseline figure against, so a plausible-looking wrong number and a right one are indistinguishable from the output alone. |
| **v1 tool loop** | Put the record behind seven tools, including one (`compute_consumption_stats`) that does the reconciliation arithmetic, after seeing the baseline invent figures with no traceable source. | `results/v1.json` | Adjustment accuracy jumped to 1.0 and evidence coverage to 1.0 — every number now traces to a tool call. But disposition accuracy *dropped* to 0.833 (10/12): missed CASE-08 (`PAYMENT_NOT_POSTED` → called `NO_ANOMALY`) and CASE-11 (`FAULTY_METER` → called `ESTIMATION_OVERBILLING`). Tools alone give the model correct numbers; they don't tell it what the company does about those numbers. |
| **v2 policy skill** | Loaded `config/policy.md` as instructions: taxonomy, decision rules, adjustment formulas, approval thresholds — the missing piece v1 exposed. | `results/v2.json` | Disposition accuracy back to 1.0 (12/12), and every other metric (action, adjustment, evidence, memo) also hit 1.0. **This is the strongest single arm of the five in this run** — a clean sweep, at less than half v4's cost per case. |
| **v3 verifier** | Added a checking pass with an enumerated list of failure modes and one corrective round back to the analyst, to catch the case where the analyst is confident and wrong. | `results/v3.json` | Disposition fell back to 0.917 (11/12, missed CASE-08 again). The verifier's own corrective JSON failed to parse on 2/12 cases (CASE-04, CASE-11) — the harness fell back to the analyst's pre-correction finding in both, which happened to already be right, so the accuracy number flatters the verifier here rather than proving it worked. Cost per case roughly doubled v2's (0.119 vs 0.059) for no accuracy gain in this run. |
| **v4 memo writer** | Split the customer letter into its own pass with only the verified finding and the customer's own words, so the letter reads like something a person wrote to a person, not an analyst's case notes. | `results/run1/v4.json`, `results/run2/v4.json` | Memo usability stayed strong (1.0, then 0.833) and the letters read as intended. But disposition was 0.917 (11/12) on the first sweep and 0.75 (9/12) on the second, and **CASE-05 accounts for the recurring part of it**. The analyst's first pass correctly called `METER_BYPASS_SUSPECTED` on all three real executions of this case, citing the unsealed junction box exactly as ground truth does. On two of the three, the verifier pushed back with nearly the same wrong objection ("this describes cable routing, not evidence of tampering") and the analyst deferred, flipping to `NO_ANOMALY`. On the third, the verifier objected to something else entirely and the correct disposition survived. Rerunning was meant to test whether the first miss was noise — running a third time showed it's not deterministic either way: a roughly 2-in-3 failure rate on this case, driven by whether the verifier happens to target the physical evidence. Wall time per case ran 2-4x v2's, and cost nearly doubled. |
| **Final** | v4, kept as the submitted architecture. | `python -m evals.run_eval --compare` | Not because it scored highest — v2 did, on both full sweeps — but because the deliverable is a signed letter, not a disposition code, and v4 is the only arm that produces one from a verified finding. The honest reading: v4's verifier catches some things v1/v2 would miss, but on CASE-05 specifically it has about a 2-in-3 chance of talking the analyst out of a correct, evidenced bypass call. That is a real, recurring defect in the verifier's handling of physical evidence, not a coincidence — see the hot take below for the fix that has not been built yet. |

> Numbers above come from two independent full 12-case sweeps against
> `claude-sonnet-4-5-20250929` (`TRIAGE_PROVIDER=anthropic`, temperature 0, 2026-08-29 and
> 2026-08-30, different API keys), plus a third standalone execution of CASE-05 run afterward
> to check whether its failure was deterministic. It isn't — not the mock provider in any of
> the three. `results/run1/` and `results/run2/` hold the full per-arm output for baseline and
> v4 from each sweep; `results/baseline.json` and `results/v4.json` at the top level are the
> most recent (run2). Per REPRODUCE.md, temperature-0 output is not bit-for-bit reproducible;
> CASE-05 failed on 2 of 3 real executions, which is a rate worth flagging, not a guarantee.

## Expected failure mode and the hot take

The failure mode this workflow was originally built around: an agent given a strong numeric
signal stops looking for the reason, and theft is the story that fits a consumption cliff. In
all three real executions, **v4 got that specific trap right** — CASE-12's consumption
collapse is correctly called `NO_ANOMALY` because the field notes describe a padlocked
building, not a tampered meter.

The failure that actually happened is the mirror image of the one the project was built to
catch, and it happened on 2 of 3 independent real executions of the same case, across two
different days and API keys: **on CASE-05, the analyst was right every time, and the verifier
talked it out of the right answer twice out of three.** The analyst's first pass correctly
flagged `METER_BYPASS_SUSPECTED` in all three executions, citing the unsealed junction box
beside the meter board — the exact evidence `data/ground_truth.json` cites for the same call.
The verifier's job is to catch unsupported claims. On two executions it raised essentially the
same objection ("this describes cable routing, not evidence of tampering") that is wrong per
the ground truth, the analyst deferred rather than re-checked the field note against the
objection, and the case flipped to `NO_ANOMALY`. On the third execution, the verifier objected
to something else instead — an arrears-figure inconsistency — never touched the bypass
evidence, and the correct disposition survived intact. Full exchange in
`trajectories/agent-v4-CASE-05-v4.jsonl` (failed), `-run2.jsonl` (failed, argument nearly
verbatim), and `-run3-app.jsonl` (succeeded, different objection). This was checked
specifically because REPRODUCE.md warns that a single-case difference might be noise — a
second run confirmed the failure, and a third showed it isn't a certainty either: it's a
roughly two-in-three chance, tied to whether the verifier's attention happens to land on the
physical evidence at all.

The hot take: **a second pass is not automatically a safer pass — it is a second place a wrong
call can be introduced, and it will be trusted more than the first because it looks like
scrutiny.** A verifier that can overrule a correct finding with an unverified claim of its own
is a single point of failure wearing a checker's badge, and on this case it does so more often
than not. The fix is not removing the verifier — v3/v4 still catch things v1/v2 would miss on
other cases, and the overall architecture is kept for that reason. The fix is giving the
verifier the same discipline demanded of the analyst: an objection to physical evidence needs
its own citation, not just confidence, and a bypass disposition specifically should not be
downgraded on a verifier objection without a second, independent check of the field note it is
disputing. That check does not exist yet in `config/policy.md` or the verifier prompt — it is
the next thing to build, shown necessary by a roughly two-in-three real-execution failure
rate, not a demonstrated fix.

## Ground rules

- Tools and libraries used per their terms; no scraped or licensed data.
- Nothing consequential is executed. The agent proposes an adjustment and a letter; both are
  queued for a named human role, and no adjustment is posted anywhere.
- A qualified human reviewer is part of every path, and the amount decides which one.
- All data is synthetic and generated by a script in this repository.
- No credentials in the repository. `ANTHROPIC_API_KEY` comes from the environment;
  `.env` is gitignored.
- Every number in the report traces to a file in `results/` and a trajectory in
  `trajectories/`.

## Repository map

```
config/policy.md          the adjudication policy, loaded as the agent's skill
config/time_study.json    human timings; review time measured (n=3), manual triage still null
data/generate_cases.py    deterministic synthetic case generator
data/cases/               twelve cases
data/ground_truth.json    adjudicated answer and rationale per case
src/llm.py                provider layer, retries, token and cost accounting
src/tools.py              seven tools, including the reconciliation tool
src/agent.py              analyst loop, verifier, writer; variants v1 to v4
src/baseline.py           the one-prompt baseline
src/mock_provider.py      offline stand-in for smoke tests, not a model
src/trajectory.py         JSONL trajectory logging
evals/run_eval.py         run an arm over all cases, score it, save it
evals/score.py            the scoring rules, shared by every arm
app/streamlit_app.py      demo shell over the same functions
results/                  per-arm results and summaries (baseline.json/v4.json = latest run)
results/run1/, run2/     baseline+v4 results from each of the two real runs, kept for the
                          CASE-05 reproducibility comparison in the changelog and hot take
trajectories/             curated representative set: one case across all five arms
                          (CASE-02), a clean pass, CASE-05's three real executions (2 failed,
                          1 succeeded — `-run2`/`-run3-app` suffixes), and CASE-12
trajectories/archive/     the full ~120-file set from both sweeps, kept but out of the way
```

See `REPRODUCE.md` to run it from a clean machine.
