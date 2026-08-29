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
      fact got CASE-12 right this run)

## 02 Reproduction guide
- [x] `REPRODUCE.md`: clean setup, exact commands, expected output, versions, runtime, cost
- [x] Walk it yourself on a fresh machine or a fresh venv before submitting — done this session,
      clean `.venv`, `pip install -r requirements.txt`, `data/generate_cases.py`, `make smoke`,
      then the real 5-arm sweep. One gap found and fixed: `claude-sonnet-5` rejects
      `temperature=0`; REPRODUCE.md should note this alongside the existing 404 troubleshooting
      entry.

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
4. **3:00–3:50 The hard case.** CASE-12. Show the consumption cliff, show that it looks exactly
   like CASE-05, then show the field notes deciding it. This is the moment worth the airtime.
5. **3:50–4:35 The comparison.** `python -m evals.run_eval --compare`. Walk the changelog:
   which change moved the number most, and the experiment you removed.
6. **4:35–5:00 The hot take.** One sentence, then stop.

Record the terminal at a readable font size. Do not narrate the code.

## 04 Agent trajectories
- [x] JSONL per run in `trajectories/`: instructions, model turns, every tool call with
      arguments and full response, verifier verdicts, retries, approval checkpoint
- [ ] Delete the mock trajectories (`make clean`) and keep representative real ones:
      one clean case, one where the verifier sent something back, and CASE-12

## Before you submit
- [ ] `make clean && make all` with a real key
- [ ] Fill the metric table and the changelog in `README.md` from `results/`
- [ ] Fill `config/time_study.json` with timings you actually measured
- [ ] Confirm no `.env` and no key anywhere in the diff: `git grep -i "sk-ant"`
- [ ] Re-read the README as if you were the billing supervisor, not the author
