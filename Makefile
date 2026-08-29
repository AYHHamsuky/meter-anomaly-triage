.PHONY: setup data smoke baseline v1 v2 v3 v4 all compare clean app

setup:
	pip install -r requirements.txt

data:
	python data/generate_cases.py

smoke:
	TRIAGE_PROVIDER=mock python -m evals.run_eval --arm baseline
	TRIAGE_PROVIDER=mock python -m evals.run_eval --arm v4
	python -m evals.run_eval --compare

baseline:
	python -m evals.run_eval --arm baseline
v1:
	python -m evals.run_eval --arm v1
v2:
	python -m evals.run_eval --arm v2
v3:
	python -m evals.run_eval --arm v3
v4:
	python -m evals.run_eval --arm v4

all: baseline v1 v2 v3 v4 compare

compare:
	python -m evals.run_eval --compare

app:
	streamlit run app/streamlit_app.py

clean:
	rm -f results/*.json trajectories/*.jsonl
