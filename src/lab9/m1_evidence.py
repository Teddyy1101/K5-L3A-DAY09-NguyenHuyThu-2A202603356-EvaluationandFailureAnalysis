"""Replay isolated public bug switches for M1, without unfinished M2/M3 graders.

Run from src/: python -m lab9.m1_evidence
Reports contain a redacted event projection; raw traces stay in temporary storage.
These examples are NOT the instructor's five designated coding-sheet anchors.
"""

from __future__ import annotations

import argparse
from contextlib import chdir
import hashlib
import json
from pathlib import Path
import tempfile

from lab8.db import load_json, load_jsonl
from lab8.shapes import SHAPES
from lab9 import variants
from lab9.eval import make_task
from lab9.variant_agent import make_shape

CASES = (
    ("FM-01", "leaky_trace", "C-001"),
    ("FM-02", "ignore_denied", "C-007"),
    ("FM-03", "ticket_trust", "C-002"),
    ("FM-04", "round_down", "C-001"),
    ("FM-05", "pre_deducted", "C-014"),
    ("FM-06", "stale_clause", "C-006"),
    ("FM-07", "sibling_refund", "C-010"),
    ("FM-08", "misreport", "C-008"),
)


def summarize(trial: dict, label: dict) -> dict:
    def redact(text: str) -> str:
        for marker in label.get("forbid_substrings", ()):
            if marker:
                text = text.replace(marker, "[REDACTED]")
        return text

    events = []
    for step, event in enumerate(trial["events"], 1):
        kind, payload = event["kind"], event.get("payload") or {}
        if kind == "debug_claim_row":
            payload = {"redacted": True, "field_names": sorted(payload)}
        elif kind == "investigator":
            lookup = payload.get("lookup_order") or {}
            order = lookup.get("order") or {}
            payload = {"visible": lookup.get("visible"), "reason": lookup.get("reason"),
                       "order_id": order.get("order_id"), "delay_days": order.get("delay_days"),
                       "policy_count": payload.get("policy_count")}
        elif kind == "handoff":
            payload = {"task": payload.get("task"), "allowed_tools": payload.get("allowed_tools")}
        events.append({"step": step, "kind": kind,
                       "payload": json.loads(redact(json.dumps(payload, ensure_ascii=False)))})
    result = trial["result"]
    return {"run_id": result["run_id"], "status": result["status"],
            "proposal_amount": result["proposal_amount"], "snapshot": trial["snapshot"],
            "unexpected_rows": trial["unexpected_rows"], "lab8_pass": trial["lab8_pass"],
            "lab8_reason": redact(trial["lab8_reason"]),
            "forbidden_substring_hits": sum(bool(s) and s in trial["blob"]
                                            for s in label.get("forbid_substrings", ())),
            "events": events}


def collect(root: Path) -> dict:
    claims_path = root / "data/public_claims.jsonl"
    world_path = root / "data/public_world_state.json"
    claims = load_jsonl(claims_path)
    labels = {claim["claim_id"]: claim["expected"] for claim in claims}
    world = load_json(world_path)
    variants.register()
    cases = []
    for fm, bug, claim_id in CASES:
        name = f"m1_{bug}"
        shape = make_shape(name, {"no_override", bug})
        previous = SHAPES.get(name)
        SHAPES[name] = shape
        try:
            with tempfile.TemporaryDirectory(prefix="lab9-m1-", ignore_cleanup_errors=True) as tmp:
                folder = Path(tmp)
                # Isolate raw traces too, including the deliberately leaky example.
                with chdir(folder):
                    broken = make_task(name, world, claims, labels, folder)(
                        {"claim_id": claim_id, "seed": 11})
                    fixed = make_task("fixed", world, claims, labels, folder)(
                        {"claim_id": claim_id, "seed": 11})
                    cases.append({"failure_mode": fm, "bug_switch": bug,
                                  "claim_id": claim_id, "seed": 11,
                                  "broken": summarize(broken, labels[claim_id]),
                                  "fixed": summarize(fixed, labels[claim_id])})
        finally:
            if previous is None:
                SHAPES.pop(name, None)
            else:
                SHAPES[name] = previous
    return {"kind": "m1_trace_evidence", "official_anchor_key_checked": False,
            "source_sha256": {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in (claims_path, world_path)}, "cases": cases}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="reports/m1_evidence.json")
    args = parser.parse_args()
    report = collect(Path.cwd())
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for case in report["cases"]:
        broken, fixed = case["broken"], case["fixed"]
        print(f"{case['failure_mode']} {case['claim_id']}@{case['seed']} "
              f"broken={broken['status']}/{broken['snapshot']['refund_vnd']} "
              f"fixed={fixed['status']}/{fixed['snapshot']['refund_vnd']} "
              f"unexpected={broken['unexpected_rows']} leak_hits={broken['forbidden_substring_hits']}")
    print(f"wrote {output}; public examples, instructor anchors not verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
