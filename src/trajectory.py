"""
Append-only trajectory log. One JSONL file per run, so a judge can follow an
agent from its instructions to its final memo without reading the code.
"""

import json
import os
import time
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRAJ_DIR = os.path.join(ROOT, "trajectories")


class Trajectory:
    def __init__(self, run_kind, case_id, variant, model, tag=None):
        os.makedirs(TRAJ_DIR, exist_ok=True)
        self.run_id = f"{run_kind}-{variant}-{case_id}-{tag or uuid.uuid4().hex[:6]}"
        self.path = os.path.join(TRAJ_DIR, f"{self.run_id}.jsonl")
        self.t0 = time.time()
        self._fh = open(self.path, "w")
        self.event("run_started", {
            "run_kind": run_kind, "case_id": case_id, "variant": variant, "model": model,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })

    def event(self, kind, payload):
        rec = {"t": round(time.time() - self.t0, 3), "event": kind, **payload}
        self._fh.write(json.dumps(rec, default=str) + "\n")
        self._fh.flush()
        return rec

    def instructions(self, system, first_user):
        self.event("agent_instructions", {"system": system, "first_user_message": first_user})

    def model_turn(self, message):
        self.event("model_turn", {
            "stop_reason": message.get("stop_reason"),
            "content": message.get("content"),
            "usage": message.get("usage", {}),
        })

    def tool_call(self, name, arguments, result, ok=True):
        self.event("tool_call", {"tool": name, "arguments": arguments, "ok": ok,
                                 "result": result})

    def checkpoint(self, name, detail):
        self.event("checkpoint", {"name": name, "detail": detail})

    def finish(self, outcome):
        self.event("run_finished", {"outcome": outcome,
                                    "wall_seconds": round(time.time() - self.t0, 2)})
        self._fh.close()
        return self.path
