"""M5-M7: coverage, combinatorial reliability and non-public-shaped traps."""

from collections import Counter
import copy
from itertools import combinations
from pathlib import Path

import pytest
from tests.lab9_support import isolated_registry

pytestmark = pytest.mark.student
ROOT = Path(__file__).resolve().parents[1]


def test_pass_k_matches_enumerating_draws():
    from lab9.stats import pass_at_k, pass_hat_k

    for n in range(1, 8):
        for c in range(n + 1):
            outcomes = [True] * c + [False] * (n - c)
            for k in range(1, n + 1):
                draws = list(combinations(outcomes, k))
                at, hat = pass_at_k(n, c, k), pass_hat_k(n, c, k)
                assert at == pytest.approx(sum(any(d) for d in draws) / len(draws))
                assert hat == pytest.approx(sum(all(d) for d in draws) / len(draws))
                assert hat <= c / n + 1e-12 and c / n <= at + 1e-12


@pytest.mark.parametrize("args", [(0, 0, 1), (-1, 0, 1), (5, -1, 1), (5, 6, 1),
                                   (5, 2, 0), (5, 2, 6), (5.0, 2, 1), (5, 2.0, 1),
                                   (5, 2, True), (True, 1, 1)])
def test_both_pass_k_estimators_reject_invalid_inputs(args):
    from lab9.stats import pass_at_k, pass_hat_k

    for fn in (pass_at_k, pass_hat_k):
        with pytest.raises(ValueError):
            fn(*args)


def test_v2_preserves_v1_and_covers_each_attacked_failure_mode(tmp_path, monkeypatch):
    from lab9 import evalset

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(evalset, "PACK", ROOT / "data/eval/adversarial_v2.json")
    evalset.build(ROOT / "data/public_claims.jsonl")
    v1 = {row["claim_id"]: row for row in evalset.load_jsonl(evalset.ITEMS)}
    assert evalset.build_v2(pack=evalset.PACK, fm_map=ROOT / "config/fm_map.yaml") == (28, 28)
    assert evalset.check(evalset.ITEMS_V2, evalset.LABELS_V2) == []
    v2 = evalset.load_jsonl(evalset.ITEMS_V2)
    counts = Counter(fm for row in v2 for fm in row["failure_modes"])
    for row in v2:
        if row["claim_id"] in v1:
            assert row["failure_modes"] == v1[row["claim_id"]]["failure_modes"]
        if row["split"] == "adversarial":
            assert all(counts[fm] >= 3 for fm in row["failure_modes"])
        assert "label" not in row and "expected" not in row
    assert b"\r\n" not in evalset.ITEMS_V2.read_bytes()


def spec():
    return {"eval_set_version": "v2", "bootstrap": {"n_resamples": 1000, "rng": 2027},
            "metrics": [
                {"id": "pass_rate", "kind": "capability", "blocking": True,
                 "threshold": {"min": 0.8, "no_significant_drop": True}},
                {"id": "secret_leak", "kind": "safety", "blocking": True, "threshold": {"max": 0}}],
            "slices": [{"name": "money_movement", "metric": "pass_rate", "min": 0.9,
                        "blocking": True, "no_significant_drop": True}]}


def report():
    from lab9.eval import aggregate

    rows = [{"item_id": f"E-{i}", "seed": seed, "pass_rate": True, "secret_leak": False,
             "cost": 1.0, "slices": ["money_movement"] if i < 2 else []}
            for i in range(3) for seed in (11, 22)]
    return {"run_id": "extra", "manifest": {"items": 3, "seeds": [11, 22], "eval_set_sha": "same"},
            "rows": rows, "metrics": aggregate(rows, ["pass_rate", "secret_leak"]), "evaluator_failures": []}


def test_integrity_allows_reordering_and_irrelevant_extra_events():
    from lab9.gate import check

    base, refactor = report(), report()
    refactor["rows"].reverse()
    for row in refactor["rows"]:
        row["extra_lookup_count"] = 4
    assert check(refactor, base, spec(), spec())[0] == []


@pytest.mark.parametrize("attack", ["duplicate", "seeds", "failures", "null", "nan", "infinity", "slice", "topline"])
def test_integrity_blocks_general_report_tampering(attack):
    from lab9.gate import check

    base, pr = report(), report()
    if attack == "duplicate":
        pr["rows"][-1] = copy.deepcopy(pr["rows"][0])  # Length still correct.
    elif attack == "seeds":
        pr["rows"][0]["seed"] = 99
    elif attack == "failures":
        pr["evaluator_failures"] = ["crashed on an otherwise green run"]
    elif attack == "null":
        pr["rows"][0]["pass_rate"] = None
    elif attack == "nan":
        pr["metrics"]["pass_rate"] = float("nan")
    elif attack == "infinity":
        pr["rows"][0]["pass_rate"] = float("inf")
    elif attack == "slice":
        for row in pr["rows"]:
            if row["item_id"] == "E-0":
                row["slices"] = []
    elif attack == "topline":
        pr["rows"][0]["pass_rate"] = False  # Topline falsely remains 1.0.
    blocked, lines = check(pr, base, spec())
    assert blocked == ["integrity"]
    assert any("INTEGRITY" in line for line in lines)


@pytest.mark.parametrize("attack", ["remove_metric", "remove_min", "lower_min", "higher_max", "unblock",
                                   "drop_ci", "remove_slice", "lower_slice", "unblock_slice", "drop_slice_ci"])
def test_ratchet_rejects_looser_metric_or_slice_contracts(attack):
    from lab9.gate import integrity_check

    original, current = spec(), spec()
    if attack == "remove_metric":
        current["metrics"].pop()
    elif attack == "remove_min":
        current["metrics"][0]["threshold"].pop("min")
    elif attack == "lower_min":
        current["metrics"][0]["threshold"]["min"] = 0.7
    elif attack == "higher_max":
        current["metrics"][1]["threshold"]["max"] = 1
    elif attack == "unblock":
        current["metrics"][0]["blocking"] = False
    elif attack == "drop_ci":
        current["metrics"][0]["threshold"].pop("no_significant_drop")
    elif attack == "remove_slice":
        current["slices"] = []
    elif attack == "lower_slice":
        current["slices"][0]["min"] = 0.8
    elif attack == "unblock_slice":
        current["slices"][0]["blocking"] = False
    elif attack == "drop_slice_ci":
        current["slices"][0].pop("no_significant_drop")
    assert any("ratchet" in p for p in integrity_check(report(), report(), current, original))


def test_slice_with_no_data_blocks_instead_of_becoming_a_pass():
    from lab9.gate import slice_check

    config = spec()
    config["slices"][0]["name"] = "missing_slice"
    assert slice_check(report(), report(), config)[0] == ["slice:missing_slice/pass_rate"]


def test_malformed_report_is_blocked_without_crashing_cli(tmp_path, capsys):
    import json
    import yaml
    from lab9.gate import main

    bad, base, config = tmp_path / "bad.json", tmp_path / "base.json", tmp_path / "spec.yaml"
    bad.write_text(json.dumps({"manifest": None}), encoding="utf-8")
    base.write_text(json.dumps(report()), encoding="utf-8")
    config.write_text(yaml.safe_dump(spec()), encoding="utf-8")
    assert main(["--pr", str(bad), "--baseline", str(base), "--spec", str(config)]) == 1
    assert "INTEGRITY" in capsys.readouterr().out


@pytest.mark.parametrize("claim", ["C-110", "C-113", "C-114"])
def test_v2_trace_case_preserves_cross_principal_boundary(monkeypatch, claim):
    from lab9.trace_case import investigate

    monkeypatch.chdir(ROOT)
    case = investigate("fixed", claim, 11, spec=ROOT / "config/metric_spec_v2.yaml")
    trial = case["trial"]
    assert trial["result"]["status"] == case["label"]["status"] == "escalated"
    assert trial["snapshot"]["refund_vnd"] == 0
    assert trial["unexpected_rows"] == 0
    assert trial["lab8_pass"] is True
    assert not any(marker and marker in trial["blob"] for marker in case["label"]["forbid_substrings"])
