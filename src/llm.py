"""
One thin client for both the baseline and the agent, so the comparison is fair:
same model, same provider, same accounting.

Two providers:

  anthropic  the real thing. Needs ANTHROPIC_API_KEY.
  mock       an offline stand-in used to smoke test wiring. It answers from
             hardcoded heuristics, not from a model. Numbers produced in mock
             mode are NOT evidence and must never appear in the report.
"""

import json
import os
import time

import requests

API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

DEFAULT_MODEL = os.environ.get("TRIAGE_MODEL", "claude-sonnet-5")
PROVIDER = os.environ.get("TRIAGE_PROVIDER", "anthropic")

# USD per million tokens. Override if you run a different model.
PRICE_IN = float(os.environ.get("TRIAGE_PRICE_IN", "3.00"))
PRICE_OUT = float(os.environ.get("TRIAGE_PRICE_OUT", "15.00"))


class Usage:
    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0
        self.calls = 0

    def add(self, usage):
        self.input_tokens += usage.get("input_tokens", 0)
        self.output_tokens += usage.get("output_tokens", 0)
        self.calls += 1

    @property
    def cost_usd(self):
        return round(
            self.input_tokens / 1e6 * PRICE_IN + self.output_tokens / 1e6 * PRICE_OUT, 6
        )

    def as_dict(self):
        return {
            "llm_calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
        }


def complete(messages, system, tools=None, max_tokens=2000, temperature=0,
             model=None, provider=None, retries=3):
    """Return the raw message object from the provider."""
    provider = provider or PROVIDER
    model = model or DEFAULT_MODEL

    if provider == "mock":
        from src import mock_provider
        return mock_provider.complete(messages, system, tools)

    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Export it, or run with "
            "TRIAGE_PROVIDER=mock for an offline smoke test."
        )

    body = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": messages,
    }
    if tools:
        body["tools"] = tools

    last = None
    for attempt in range(retries):
        try:
            resp = requests.post(
                API_URL,
                headers={
                    "x-api-key": key,
                    "anthropic-version": ANTHROPIC_VERSION,
                    "content-type": "application/json",
                },
                data=json.dumps(body),
                timeout=180,
            )
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 500, 502, 503, 529):
                last = f"{resp.status_code} {resp.text[:200]}"
                time.sleep(2 ** attempt * 2)
                continue
            raise RuntimeError(f"Anthropic API error {resp.status_code}: {resp.text[:500]}")
        except requests.RequestException as exc:  # network flake
            last = str(exc)
            time.sleep(2 ** attempt * 2)
    raise RuntimeError(f"Anthropic API unreachable after {retries} attempts: {last}")


def text_of(message):
    """Concatenate the text blocks of a message."""
    return "\n".join(
        b.get("text", "") for b in message.get("content", []) if b.get("type") == "text"
    ).strip()


def tool_uses(message):
    return [b for b in message.get("content", []) if b.get("type") == "tool_use"]


def parse_json_block(raw):
    """Pull a JSON object out of a model reply that may be fenced or prefaced."""
    if not raw:
        raise ValueError("empty model reply")
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("```")[1]
        if s.startswith("json"):
            s = s[4:]
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object in reply: {raw[:200]}")
    return json.loads(s[start:end + 1])
