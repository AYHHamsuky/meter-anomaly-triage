"""
The meter anomaly triage agent.

Four variants, so every row of the improvement changelog can be rerun on its own:

    v1  tool loop only          the analyst can pull the record but has no policy
    v2  v1 + policy skill       the adjudication rules are loaded as instructions
    v3  v2 + verifier           a second pass checks the finding against the rules,
                                one retry with the issues fed back
    v4  v3 + memo writer        a separate writing pass drafts the customer letter
                                from the verified finding (this is the final system)

    python -m src.agent --case CASE-02 --variant v4
"""

import argparse
import json
import os
import time

from src import llm, tools
from src.trajectory import Trajectory

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POLICY = open(os.path.join(ROOT, "config", "policy.md")).read()

MAX_TOOL_TURNS = 10

ANALYST_BASE = """You are a revenue billing analyst at an electricity distribution company. \
You adjudicate disputed accounts.

You cannot see the account record directly. Pull what you need with the tools. \
Do the arithmetic with compute_consumption_stats rather than in your head, and treat its \
figures as the record.

Work the case, then give your finding. Every figure you state must come from a tool result."""

ANALYST_POLICY = ANALYST_BASE + """

Apply this policy. It decides the disposition, the arithmetic and who approves the outcome.

<policy>
{policy}
</policy>"""

FINDING_SCHEMA = """When you have enough evidence, stop calling tools and reply with only a JSON object:

{
  "disposition": one of ["NO_ANOMALY","ESTIMATION_OVERBILLING","ESTIMATION_UNDERBILLING","TARIFF_BAND_MISCLASSIFICATION","FAULTY_METER","METER_BYPASS_SUSPECTED","UNBILLED_PERIOD","DOUBLE_BILLING","PAYMENT_NOT_POSTED"],
  "recommended_action": one of ["NO_ACTION","CREDIT_ADJUSTMENT","DEBIT_ADJUSTMENT","METER_REPLACEMENT","FIELD_INSPECTION","POST_PAYMENT"],
  "adjustment_ngn": number, 0 if none,
  "adjustment_direction": one of ["CREDIT_CUSTOMER","DEBIT_CUSTOMER","NONE"],
  "adjustment_working": "the arithmetic in one line, or empty",
  "confidence": one of ["HIGH","MEDIUM","LOW"],
  "evidence": [{"claim": "...", "source": "tool name and the field it came from"}],
  "open_questions": ["..."],
  "approval_role": "the role that must approve this",
  "customer_memo": "the message to send to the customer"
}"""

VERIFIER_SYSTEM = """You check a colleague's adjudication of a disputed electricity account \
before it goes to a supervisor. You are not re-deciding the case. You are looking for the \
specific ways this goes wrong:

- a figure in the finding that does not appear in any tool result
- arithmetic that does not follow from the figures cited
- a bypass or theft finding with no physical indicator in the field notes
- a consumption drop treated as an answer when the field notes explain it
- an estimate run reconciled without reads on both sides of it
- a negative read delta treated as anything other than a register rollover
- a disposition the policy does not support, or an approval role that does not match the amount

Reply with only:
{"approved": true|false, "issues": ["..."]}

Approve when the finding holds up. Do not invent issues."""

WRITER_SYSTEM = """You write to electricity customers on behalf of the customer care unit of a \
distribution company. A billing analyst has finished a case and you write the letter that goes out \
over a named officer's signature.

Write it the way a competent person writes: address what the customer actually complained about, \
say what was found and how it was worked out, give the figures, say what happens next and by when, \
and say who they can reach. Plain language. No headings. No bullet lists unless figures genuinely \
need them. Do not thank them for their patience, do not apologise twice, do not pad. Naira amounts \
as NGN with thousand separators. Six to twelve sentences.

Reply with only the letter text."""


def _finding_from(text):
    return llm.parse_json_block(text)


def run(case_id, variant="v4", model=None, provider=None, tag=None):
    case = tools.load_case(case_id)
    traj = Trajectory("agent", case_id, variant, model or llm.DEFAULT_MODEL, tag=tag)
    usage = llm.Usage()
    t0 = time.time()

    use_policy = variant in ("v2", "v3", "v4")
    use_verifier = variant in ("v3", "v4")
    use_writer = variant == "v4"

    system = (ANALYST_POLICY.format(policy=POLICY) if use_policy else ANALYST_BASE)
    system += "\n\n" + FINDING_SCHEMA

    first_user = (
        f"Case {case_id} has been referred for adjudication. "
        f"Account {case['account']['account_no']}, opened {case['opened_on']}. "
        "Pull the record and work the case."
    )
    traj.instructions(system, first_user)

    messages = [{"role": "user", "content": first_user}]
    called = []
    finding, error = None, None

    for turn in range(MAX_TOOL_TURNS):
        msg = llm.complete(messages, system, tools=tools.SCHEMAS,
                           max_tokens=3000, model=model, provider=provider)
        traj.model_turn(msg)
        usage.add(msg.get("usage", {}))
        messages.append({"role": "assistant", "content": msg["content"]})

        uses = llm.tool_uses(msg)
        if not uses:
            try:
                finding = _finding_from(llm.text_of(msg))
            except Exception as exc:
                error = f"unparseable finding: {exc}"
            break

        results = []
        for u in uses:
            out = tools.run_tool(u["name"], case, u.get("input"))
            called.append(u["name"])
            traj.tool_call(u["name"], u.get("input"), out, ok="error" not in out)
            results.append({
                "type": "tool_result",
                "tool_use_id": u["id"],
                "content": json.dumps(out, default=str),
            })
        messages.append({"role": "user", "content": results})
    else:
        error = f"tool loop hit {MAX_TOOL_TURNS} turns without a finding"

    verifier_rounds = 0
    verifier_issues = []
    if use_verifier and finding:
        for _ in range(1):  # one retry, by design
            check_user = (
                "Tool results the analyst received:\n"
                f"{json.dumps([{'tool': c} for c in called])}\n\n"
                "Full record the analyst could see, for checking figures:\n"
                f"{json.dumps(tools.compute_consumption_stats(case), default=str)}\n\n"
                "Field notes:\n"
                f"{json.dumps(case['field_notes'])}\n\n"
                "The finding:\n"
                f"{json.dumps(finding, indent=2, default=str)}\n\n"
                f"Policy:\n<policy>\n{POLICY}\n</policy>"
            )
            vmsg = llm.complete([{"role": "user", "content": check_user}], VERIFIER_SYSTEM,
                                max_tokens=1200, model=model, provider=provider)
            traj.model_turn(vmsg)
            usage.add(vmsg.get("usage", {}))
            verifier_rounds += 1
            try:
                verdict = llm.parse_json_block(llm.text_of(vmsg))
            except Exception as exc:
                traj.checkpoint("verifier_unparseable", str(exc))
                break
            traj.checkpoint("verifier_verdict", verdict)
            if verdict.get("approved"):
                break
            verifier_issues = verdict.get("issues", [])
            messages.append({
                "role": "user",
                "content": ("A reviewer returned this finding with issues:\n"
                            f"{json.dumps(verifier_issues, indent=2)}\n\n"
                            "Pull anything else you need, then give the corrected finding "
                            "in the same JSON format."),
            })
            for _ in range(4):
                msg = llm.complete(messages, system, tools=tools.SCHEMAS,
                                   max_tokens=3000, model=model, provider=provider)
                traj.model_turn(msg)
                usage.add(msg.get("usage", {}))
                messages.append({"role": "assistant", "content": msg["content"]})
                uses = llm.tool_uses(msg)
                if not uses:
                    try:
                        finding = _finding_from(llm.text_of(msg))
                    except Exception as exc:
                        error = f"unparseable corrected finding: {exc}"
                    break
                results = []
                for u in uses:
                    out = tools.run_tool(u["name"], case, u.get("input"))
                    called.append(u["name"])
                    traj.tool_call(u["name"], u.get("input"), out, ok="error" not in out)
                    results.append({"type": "tool_result", "tool_use_id": u["id"],
                                    "content": json.dumps(out, default=str)})
                messages.append({"role": "user", "content": results})

    if use_writer and finding:
        write_user = (
            f"Case reference: {case_id}\n"
            f"The customer wrote in on {case['complaint']['date']} via "
            f"{case['complaint']['channel']}:\n\"{case['complaint']['text']}\"\n\n"
            f"Customer name: {case['account']['customer_name']}\n"
            f"Account number: {case['account']['account_no']}\n\n"
            "The finding:\n"
            f"{json.dumps({k: v for k, v in finding.items() if k != 'customer_memo'}, indent=2, default=str)}\n\n"
            "Write the letter."
        )
        wmsg = llm.complete([{"role": "user", "content": write_user}], WRITER_SYSTEM,
                            max_tokens=1200, model=model, provider=provider)
        traj.model_turn(wmsg)
        usage.add(wmsg.get("usage", {}))
        letter = llm.text_of(wmsg).strip()
        if letter:
            finding["customer_memo"] = letter
        traj.checkpoint("memo_drafted", {"chars": len(letter)})

    if finding:
        finding.setdefault("approval_role", "Billing Supervisor")
        traj.checkpoint("human_approval_required", {
            "role": finding.get("approval_role"),
            "note": "No adjustment is posted by this system. The memo and the adjustment "
                    "are queued for the named role to approve.",
        })

    out = {
        "case_id": case_id,
        "variant": variant,
        "finding": finding or {},
        "error": error,
        "tools_called": called,
        "verifier_rounds": verifier_rounds,
        "verifier_issues": verifier_issues,
        "wall_seconds": round(time.time() - t0, 2),
        "usage": usage.as_dict(),
        "trajectory": traj.path,
    }
    traj.finish(out["finding"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--variant", default="v4", choices=["v1", "v2", "v3", "v4"])
    ap.add_argument("--model")
    ap.add_argument("--provider")
    args = ap.parse_args()
    print(json.dumps(run(args.case, args.variant, args.model, args.provider), indent=2))


if __name__ == "__main__":
    main()
