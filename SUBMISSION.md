# Submission checklist

The brief asks for four things. Three are in this repository; the fourth is the video.

## 01 Solution code and improvement changelog
- [x] Full project, runnable from a clean environment
- [x] Agent instructions in the repository (`src/agent.py`, `config/policy.md`)
- [x] README naming the user, the bottleneck and why it matters
- [x] Improvement Changelog section with one row per variant
- [x] **Changelog evidence cells filled from real API runs** — `claude-sonnet-4-5-20250929`,
      2026-08-29, `results/{baseline,v1,v2,v3,v4}.json`. Note: `claude-sonnet-5` itself rejects
      `temperature=0` on this key, so the model differs from `.env.example`'s default; this is
      recorded in every result and trajectory.
- [x] Failure mode and hot take confirmed against your own numbers — rewritten around the real
      CASE-05 verifier over-correction, not the original speculative CASE-12 framing (v4 in
      fact got CASE-12 right on all three real executions)
- [x] **Reran per REPRODUCE.md's own advice ("run each arm twice if a difference looks
      marginal")** — baseline vs v4's disposition gap did not close on the two full sweeps
      (12/12 vs 11/12, then 12/12 vs 9/12). A third, standalone execution of CASE-05 was run
      afterward specifically to check whether *its* failure was deterministic: it wasn't — 2
      wrong out of 3 real executions, with the same wrong verifier objection on the two
      failures and a different, unrelated objection on the success. Written up in the README
      as a ~2-in-3 real-execution failure rate, not "always fails" — caught and corrected after
      an initial draft overstated it as fully reproducible off only two data points. Second and
      third runs used a different API key (identity-linked, required an
      `ANTHROPIC_WORKSPACE_ID` header — see `src/llm.py` and REPRODUCE.md).

## 02 Reproduction guide
- [x] `REPRODUCE.md`: clean setup, exact commands, expected output, versions, runtime, cost
- [x] Walk it yourself on a fresh machine or a fresh venv before submitting — done twice this
      session, on two different API keys. Two gaps found and fixed, both now documented in
      REPRODUCE.md's troubleshooting: `claude-sonnet-5` rejects `temperature=0`; an
      identity-linked key needs `ANTHROPIC_WORKSPACE_ID` set (`src/llm.py` sends it only when
      present, so a standard key is unaffected).

## 03 Solution video (up to 5 minutes)
Suggested running order:

1. **0:00–0:40 The problem.** Read CASE-02's complaint aloud. Six months of estimated bills,
   NGN 214,800 in arrears, a customer at the counter. Say who has to decide and how long it
   takes them today.
2. **0:40–1:20 The baseline.** Run `python -m src.baseline --case CASE-02`. Show the answer.
   Point at the figure it produced and ask where it came from.
3. **1:20–3:00 One real execution.** Run the agent on CASE-02 in the Streamlit shell. Show the
   tool calls arriving, the reconciliation figures, the verifier verdict, and the letter. Read
   two sentences of the letter out loud.
4. **3:00–4:00 The two hard cases.** CASE-12: show the consumption cliff, show that it looks
   exactly like CASE-05, then show the field notes deciding it correctly — and say v4 got this
   one right on all three real executions. Then CASE-05 itself: show the analyst getting it
   right first, the verifier's objection, and the flip to `NO_ANOMALY` — and say this failed on
   2 of 3 real executions with nearly the same wrong verifier reasoning both times, and on the
   third the verifier objected to something unrelated instead and the correct call survived.
   Frame it as a real, roughly two-in-three rate, not a guaranteed failure. This is the moment
   worth the airtime, more than the original plan gave it.
5. **4:00–4:40 The comparison.** `python -m evals.run_eval --compare`. Walk the changelog:
   which change moved the number most, and that v2, not the final v4, actually scored highest
   on raw accuracy — say why v4 is still the submission.
6. **4:40–5:00 The hot take.** One sentence, then stop.

Record the terminal at a readable font size. Do not narrate the code.

## 04 Agent trajectories
- [x] JSONL per run in `trajectories/`: instructions, model turns, every tool call with
      arguments and full response, verifier verdicts, retries, approval checkpoint
- [x] Trimmed to representative real ones: CASE-02 across all five arms (the through-line),
      a clean pass (CASE-07), CASE-05's three real executions (2 failed, 1 succeeded), and
      CASE-12. The full set from both sweeps is preserved in `trajectories/archive/`, not
      deleted.

## Before you submit
- [x] `make clean && make all` with a real key — done twice (two full sweeps, two keys), plus
      one standalone third execution of CASE-05
- [x] Fill the metric table and the changelog in `README.md` from `results/` — filled from both
      sweeps, with CASE-05's ~2-in-3 failure rate called out explicitly (not overstated as
      deterministic)
- [x] Fill `config/time_study.json` with timings you actually measured — `review_baseline_output`
      (14.7s avg) and `review_agent_output` (72.3s avg) filled from 3 timed cases
- [ ] `manual_triage_minutes_per_case` still needed — working one case from the raw record by
      hand, no AI, timed
- [ ] Confirm no `.env` and no key anywhere in the diff: `git grep -i "sk-ant"` — re-check after
      the second key was added, since it's a different key than the one checked before
- [ ] Re-read the README as if you were the billing supervisor, not the author
- [ ] Record the solution video (script above, updated for the CASE-05 finding)
- [ ] Push the latest commit (results/run2, restored trajectories, llm.py workspace-id support,
      updated README/SUBMISSION.md) — the last push predates this rerun
