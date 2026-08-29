"""
A thin shell over the same code the CLI and the eval harness run. Nothing is
computed here that is not computed there. It exists so the workflow can be shown
to a person, and so the demo video has something to point at.

    streamlit run app/streamlit_app.py
"""

import json
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evals import score as scoring  # noqa: E402
from src import agent, baseline, llm, tools  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(page_title="Meter anomaly triage", layout="wide")

st.markdown(
    """
    <style>
      .stApp { font-size: 0.95rem; }
      .caselabel { font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
                   letter-spacing: .04em; color: #5b6470; font-size: .78rem;
                   text-transform: uppercase; }
      .verdict { font-size: 1.35rem; font-weight: 650; line-height: 1.25; }
      .memo { background: #f7f7f5; border-left: 3px solid #2f3b47; padding: 1rem 1.15rem;
              white-space: pre-wrap; line-height: 1.55; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Meter anomaly triage")
st.caption(
    "A disputed electricity account goes in. A disposition, a traceable adjustment and a "
    "letter a customer care officer can sign come out. Nothing is posted to a billing system."
)

truth = scoring.load_ground_truth()
case_ids = tools.all_case_ids()

with st.sidebar:
    st.subheader("Run")
    case_id = st.selectbox("Case", case_ids)
    variant = st.selectbox("Agent variant", ["v4", "v3", "v2", "v1"], index=0)
    provider = st.selectbox("Provider", ["anthropic", "mock"],
                            index=0 if llm.PROVIDER == "anthropic" else 1)
    show_truth = st.checkbox("Show the adjudicated answer", value=False)
    st.caption("mock runs offline from hardcoded rules. Use it to check wiring, never to "
               "produce numbers for the report.")

case = tools.load_case(case_id)
acct = case["account"]

left, right = st.columns([1, 1])
with left:
    st.markdown('<div class="caselabel">The complaint</div>', unsafe_allow_html=True)
    st.write(f"**{acct['customer_name']}** · {acct['account_no']} · "
             f"{acct['tariff_class']}/{acct['service_band_on_record']} · {acct['meter_type']}")
    st.write(f"_{case['complaint']['date']} via {case['complaint']['channel']}_")
    st.info(case["complaint"]["text"])
with right:
    st.markdown('<div class="caselabel">On the account</div>', unsafe_allow_html=True)
    st.write(f"Invoices on file: {len(case['billing_history'])}  ·  "
             f"Meter reads: {len(case['meter_reads'])}  ·  "
             f"Payments: {len(case['payments'])}")
    st.write(f"Arrears carried: NGN {acct['outstanding_arrears_ngn']:,.2f}")
    with st.expander("Field notes"):
        for n in case["field_notes"]:
            st.write("– " + n)

if show_truth:
    t = truth[case_id]
    st.warning(f"Adjudicated: **{t['disposition']}** → {t['action']} · "
               f"NGN {t['adjustment_ngn']:,.2f}\n\n{t['rationale']}")

col_a, col_b = st.columns(2)
run_base = col_a.button("Run the baseline", use_container_width=True)
run_agent = col_b.button(f"Run the agent ({variant})", type="primary", use_container_width=True)


def render(result, title):
    f = result.get("finding") or {}
    st.markdown(f"### {title}")
    if result.get("error"):
        st.error(result["error"])
    st.markdown(
        f'<div class="verdict">{f.get("disposition", "—")}</div>'
        f'<div class="caselabel">{f.get("recommended_action", "—")} · '
        f'NGN {float(f.get("adjustment_ngn") or 0):,.2f} · '
        f'{f.get("adjustment_direction", "NONE")}</div>',
        unsafe_allow_html=True,
    )
    if f.get("adjustment_working"):
        st.caption(f["adjustment_working"])

    s = scoring.score_case(result, truth[result["case_id"]])
    m1, m2, m3 = st.columns(3)
    m1.metric("Disposition", "correct" if s["disposition_correct"] else "wrong")
    m2.metric("Adjustment", "in tolerance" if s["adjustment_ok"] else "off")
    m3.metric("Cost", f"${s['cost_usd']:.4f}")

    if f.get("evidence"):
        with st.expander("Evidence the analyst cited", expanded=False):
            for e in f["evidence"]:
                st.write(f"– {e.get('claim')}  \n  _{e.get('source')}_")
    if f.get("open_questions"):
        with st.expander("Open questions"):
            for q in f["open_questions"]:
                st.write("– " + q)

    st.markdown('<div class="caselabel">Letter for signature</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="memo">{f.get("customer_memo", "")}</div>', unsafe_allow_html=True)
    st.caption(f"Queued for approval by: {f.get('approval_role', '—')}. "
               "This system proposes; it does not post.")

    if result.get("tools_called"):
        st.markdown('<div class="caselabel">Trajectory</div>', unsafe_allow_html=True)
        st.write(" → ".join(result["tools_called"]))
    if result.get("trajectory") and os.path.exists(result["trajectory"]):
        with open(result["trajectory"]) as fh:
            lines = [json.loads(x) for x in fh]
        with st.expander(f"Full trajectory ({len(lines)} events)"):
            st.json(lines)


if run_base:
    with st.spinner("Running the baseline..."):
        st.session_state["baseline"] = baseline.run(case_id, provider=provider, tag="app")
if run_agent:
    with st.spinner(f"Running {variant}..."):
        st.session_state["agent"] = agent.run(case_id, variant=variant, provider=provider, tag="app")

out_a, out_b = st.columns(2)
with out_a:
    if st.session_state.get("baseline", {}).get("case_id") == case_id:
        render(st.session_state["baseline"], "Baseline · one direct prompt")
with out_b:
    if st.session_state.get("agent", {}).get("case_id") == case_id:
        render(st.session_state["agent"], f"Agent · {variant}")

res_path = os.path.join(ROOT, "results")
saved = [f for f in sorted(os.listdir(res_path)) if f.endswith(".json")] if os.path.isdir(res_path) else []
if saved:
    st.divider()
    st.markdown('<div class="caselabel">Saved evaluation runs</div>', unsafe_allow_html=True)
    rows = []
    for f in saved:
        with open(os.path.join(res_path, f)) as fh:
            rows.append(json.load(fh)["summary"])
    st.dataframe(rows, use_container_width=True, hide_index=True)
