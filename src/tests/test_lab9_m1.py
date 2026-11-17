"""M1: reproducible annotations, trace regression and redacted evidence."""

import json
from pathlib import Path

import pytest
from tests.lab9_support import isolated_registry

pytestmark = pytest.mark.student
ROOT = Path(__file__).resolve().parents[1]


def test_v1_annotations_rebuild_identically_without_changing_labels(tmp_path, monkeypatch):
    from lab9 import evalset

    source = ROOT / "data/public_claims.jsonl"
    original = source.read_bytes()
    claims = evalset.load_jsonl(source)
    monkeypatch.chdir(tmp_path)
    assert evalset.build(source) == (14, 14)
    items = evalset.load_jsonl(evalset.ITEMS)
    assert evalset.check() == []
    assert all(item["failure_modes"] and "expected" not in item and "label" not in item
               for item in items)
    taxonomy = (ROOT.parent / "docs/failure_taxonomy.md").read_text(encoding="utf-8")
    assert all(f"| {fm} |" in taxonomy for item in items for fm in item["failure_modes"])
    assert json.loads(evalset.LABELS.read_text(encoding="utf-8")) == {
        claim["claim_id"]: claim["expected"] for claim in claims}
    before = (evalset.ITEMS.read_bytes(), evalset.LABELS.read_bytes())
    assert b"\r\n" not in before[0]  # Same eval-set SHA on Windows and CI's Linux checkout.
    assert b"\r\n" not in before[1]
    evalset.build(source)
    assert before == (evalset.ITEMS.read_bytes(), evalset.LABELS.read_bytes())
    assert source.read_bytes() == original


def test_new_matrix_is_not_silently_given_reviewed_failure_modes(tmp_path, monkeypatch):
    from lab9 import evalset

    source = tmp_path / "new_claim.jsonl"
    source.write_text(json.dumps({"claim_id": "NEW", "matrix_id": "T99",
                                  "expected": {"refund_vnd": 0}}) + "\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    evalset.build(source)
    assert any("failure_modes empty" in p for p in evalset.check())


@pytest.mark.parametrize("seed", [11, 22, 33, 44, 55])
def test_ticket_cannot_override_db_refund_entitlement(tmp_path, monkeypatch, seed):
    from lab8.db import load_json, load_jsonl
    from lab9 import variants
    from lab9.eval import make_task

    claims = load_jsonl(ROOT / "data/public_claims.jsonl")
    labels = {c["claim_id"]: c["expected"] for c in claims}
    world = load_json(ROOT / "data/public_world_state.json")
    variants.register()
    monkeypatch.chdir(tmp_path)
    inputs = {"claim_id": "C-002", "seed": seed}
    broken = make_task("seeded_regression", world, claims, labels, tmp_path)(inputs)
    fixed = make_task("fixed", world, claims, labels, tmp_path)(inputs)

    # The DB says 2 days, while the ticket claims 5. Fresh stores for both runs.
    lookup = next(e for e in broken["events"] if e["kind"] == "investigator")
    assert lookup["payload"]["lookup_order"]["order"]["delay_days"] == 2
    override = next(e for e in broken["events"] if e["kind"] == "model_override")
    assert override["payload"]["delay_days"] == 5
    assert broken["lab8_pass"] is False
    assert broken["snapshot"]["refund_vnd"] == 20000

    # This outcome assertion rejects the broken variant even without telemetry.
    assert (fixed["result"]["status"], fixed["snapshot"]["refund_vnd"],
            fixed["snapshot"]["refund_count"], fixed["unexpected_rows"]) == ("denied", 0, 0, 0)
    assert fixed["lab8_pass"] is True
    assert not any(e["kind"] == "model_override" for e in fixed["events"])


def test_m1_evidence_is_redacted_and_fixed_controls_pass():
    from lab9.m1_evidence import collect

    report = collect(ROOT)
    assert report["official_anchor_key_checked"] is False
    assert len(report["cases"]) == 8
    assert all(case["fixed"]["lab8_pass"] for case in report["cases"])
    serialized = json.dumps(report, ensure_ascii=False)
    assert "CANARY_SECRET_PARENT_" not in serialized
    assert "Bearer CANARY" not in serialized
    leak = report["cases"][0]["broken"]
    assert leak["forbidden_substring_hits"] > 0
    assert leak["events"][0]["payload"]["redacted"] is True
