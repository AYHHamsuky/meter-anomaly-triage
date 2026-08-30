# Reproduction guide

Written for someone starting from a clean machine with nothing installed but Python.

## 1. Environment

Python 3.11 or newer. Verified on 3.12.3, Ubuntu 24.04.

```bash
git clone <repository-url>
cd meter-anomaly-triage
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Pinned versions: `requests==2.32.3`, `streamlit==1.39.0`, `pandas==2.2.3`.
No other services, databases or accounts are needed.

## 2. Credentials

```bash
cp .env.example .env      # then edit it, or just export the variables
export ANTHROPIC_API_KEY=sk-ant-...
export TRIAGE_PROVIDER=anthropic
export TRIAGE_MODEL=claude-sonnet-5        # any model your key can reach
```

If `TRIAGE_MODEL` is not available to your key, set it to one that is. The model string is
recorded in every result file and every trajectory, so a different model is visible in the
output rather than hidden.

Cost accounting uses `TRIAGE_PRICE_IN` and `TRIAGE_PRICE_OUT` (USD per million tokens,
defaulting to 3.00 and 15.00). Set them to your model's real prices or the cost column will be
wrong.

## 3. Data

```bash
python data/generate_cases.py
```

Writes twelve cases to `data/cases/`, plus `data/ground_truth.json` and
`data/tariff_table.json`. Deterministic: run it twice and the files are identical. All data is
synthetic.

## 4. Check the wiring without spending anything

```bash
make smoke
```

This runs the baseline and v4 arms against the offline mock provider. It exercises the tool
loop, the verifier branch and the writer branch, and it should finish in under a second with
no network access. **Mock numbers are a smoke test, not evidence.** Delete them before a real
run:

```bash
make clean
```

## 5. Run one case

```bash
python -m src.baseline --case CASE-02
python -m src.agent --case CASE-02 --variant v4
```

Each prints the finding as JSON and writes a trajectory to `trajectories/`.

CASE-12 is the interesting one to watch: it looks like energy theft and is not.

## 6. Run the full evaluation

```bash
python -m evals.run_eval --arm baseline
python -m evals.run_eval --arm v1
python -m evals.run_eval --arm v2
python -m evals.run_eval --arm v3
python -m evals.run_eval --arm v4
python -m evals.run_eval --compare
```

or `make all`.

Each arm writes `results/<arm>.json` containing the summary, the per-case scores and the raw
findings. `--compare` prints the table across every arm already saved.

**Expected output.** `--compare` prints one row per arm with disposition accuracy, action
accuracy, adjustment accuracy, evidence coverage, memo usability, cost per case and seconds
per case. Twelve cases per arm.

**Runtime and cost.** Twelve cases per arm. The baseline is one model call per case; v4 is
roughly four to seven calls per case depending on how many tools the analyst pulls and whether
the verifier sends anything back. On a Sonnet-class model expect single-digit minutes and well
under one US dollar for the full five-arm sweep. The exact figures for your run are in the
`usage` block of each result file, and `cost_per_case_usd` in each summary.

**Determinism.** Temperature is 0, but model responses are not bit-for-bit reproducible. The
scoring, the cases and the ground truth are fully deterministic. Expect the accuracy figures
to move by a case or so between runs; run each arm twice if a difference looks marginal.

## 7. The demo shell

```bash
streamlit run app/streamlit_app.py
```

Pick a case, run the baseline and the agent side by side, read the letter, open the full
trajectory. It calls exactly the same functions as the CLI.

## 8. Where to look afterwards

- `results/*.json` — summaries, per-case scores, raw findings.
- `trajectories/*.jsonl` — one line per event: instructions, model turns, every tool call with
  its arguments and full response, verifier verdicts, the human approval checkpoint.
- `data/ground_truth.json` — the adjudicated answer and the reasoning behind it, so you can
  disagree with the scoring rather than take it on trust.

## Troubleshooting

- `ANTHROPIC_API_KEY is not set` — export it, or run with `TRIAGE_PROVIDER=mock`.
- `Anthropic API error 404` — the model string is not available to your key. Change
  `TRIAGE_MODEL`.
- `Anthropic API error 400: anthropic-workspace-id is required when authenticating with an
  identity-linked API key` — some keys (identity-linked / SSO-issued) require the request to
  name the workspace it acts in. Set `ANTHROPIC_WORKSPACE_ID` in `.env` to that workspace's id
  (found on console.anthropic.com under the workspace's settings); `src/llm.py` sends it as the
  `anthropic-workspace-id` header only when the variable is set, so a standard key is unaffected.
- `Anthropic API error 400: temperature is deprecated for this model` — some model snapshots
  (observed on `claude-sonnet-5`) accept only `temperature=1` or an omitted `temperature` field,
  rejecting the pinned `temperature=0`. This is a per-snapshot API restriction, not a bug in
  this repo. Pin `TRIAGE_MODEL` to a snapshot that accepts `temperature=0` instead (e.g.
  `claude-sonnet-4-5-20250929`); the model string is recorded in every result and trajectory
  either way.
- `unparseable finding` in a result — the model wrapped its JSON in prose. It is recorded as an
  error and scored as a miss rather than silently retried.
- Import errors — run commands from the repository root; the modules are imported as
  `src.*` and `evals.*`.
