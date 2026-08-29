# About the files in this folder

Each `<arm>.json` holds the summary, the per-case scores and the raw findings for one
evaluation arm.

The files currently committed were produced with `TRIAGE_PROVIDER=mock`, the offline
stand-in in `src/mock_provider.py`. It is not a model. It answers from hardcoded rules,
and its baseline path is deliberately naive so the pipeline's branches all get exercised.

**Mock results are a smoke test. They are not evidence and must not be quoted.**

Run `make clean` and then `make all` with a real API key before submitting anything.
