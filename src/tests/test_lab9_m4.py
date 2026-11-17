"""M4: paired uncertainty, release decisions and baseline contract."""

import copy
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.student


def test_bootstrap_pairs_each_item_and_preserves_inputs():
    from lab9.stats import paired_bootstrap

    base = [100.0, 300.0, 900.0, 1200.0]
    pr = [v - 1.0 for v in base]
    original = pr.copy(), base.copy()
    # An unpaired bootstrap would have large variance from the common offsets.
    assert paired_bootstrap(pr, base) == (-1.0, -1.0, -1.0)
    assert (pr, base) == original


def test_bootstrap_is_repeatable_with_fixed_seed():
    from lab9.stats import paired_bootstrap

    args = ([1.0, 0.8, 0.2, 0.6], [0.2, 0.9, 0.4, 1.0])
    assert paired_bootstrap(*args, rng=19) == paired_bootstrap(*args, rng=19)


@pytest.mark.parametrize("a,b", [([], []), ([1], [1]), ([1, 0], [1]),
                                 ([[1, 0]], [[1, 0]]), ([1, float("nan")], [1, 0]),
                                 ([1, 0], [1, float("inf")])])
def test_bootstrap_rejects_invalid_samples(a, b):
    from lab9.stats import paired_bootstrap

    with pytest.raises(ValueError):
        paired_bootstrap(a, b)


@pytest.mark.parametrize("n_resamples", [0, -1, 1.5, True])
def test_bootstrap_rejects_invalid_resample_count(n_resamples):
    from lab9.stats import paired_bootstrap

    with pytest.raises(ValueError):
        paired_bootstrap([1, 0], [0, 1], n_resamples=n_resamples)


@pytest.mark.parametrize("confidence", [0, 1, float("nan"), float("inf")])
def test_bootstrap_rejects_invalid_confidence(confidence):
    from lab9.stats import paired_bootstrap

    with pytest.raises(ValueError):
        paired_bootstrap([1, 0], [0, 1], confidence=confidence)


def report(value=1.0, *, safety=0):
    return {"run_id": "test", "shape": "swarm", "evaluator_failures": [],
            "manifest": {"eval_set_sha": "same", "items": 3, "seeds": [11, 22]},
            "metrics": {"pass_rate": value, "secret_leak": safety, "diagnostic": 0.5},
            "rows": [{"item_id": f"E-{i}", "seed": seed, "pass_rate": value,
                      "secret_leak": bool(safety and i == 0 and seed == 11)}
                     for i in range(3) for seed in (11, 22)]}


def spec():
    return {"bootstrap": {"n_resamples": 1000, "rng": 2027, "confidence": 0.95},
            "metrics": [
                {"id": "pass_rate", "threshold": {"min": 0.8, "no_significant_drop": True}, "blocking": True},
                {"id": "secret_leak", "threshold": {"max": 0}, "blocking": True},
                {"id": "diagnostic", "threshold": {"min": 0.95}, "blocking": False}]}


def test_gate_blocks_paired_drop_even_above_floor():
    from lab9.gate import check

    blocked, lines = check(report(0.9), report(1.0), spec())
    assert blocked == ["pass_rate"]
    assert any("CI [-0.100, -0.100]" in line for line in lines)


def test_gate_accepts_same_report_and_only_warns_for_diagnostic():
    from lab9.gate import check

    blocked, lines = check(report(), report(), spec())
    assert blocked == []
    assert any("diagnostic" in line and "warn" in line for line in lines)


def test_gate_blocks_any_safety_violation_and_mismatched_eval_set():
    from lab9.gate import check

    assert check(report(safety=1), report(), spec())[0] == ["secret_leak"]
    other = report()
    other["manifest"]["eval_set_sha"] = "different"
    assert check(other, report(), spec())[0] == ["eval_set_sha"]


def test_gate_passes_configured_confidence_to_bootstrap(monkeypatch):
    from lab9 import gate

    seen = []

    def bootstrap(a, b, **kwargs):
        seen.append(kwargs)
        return 0.0, 0.0, 0.0

    monkeypatch.setattr(gate.stats, "paired_bootstrap", bootstrap)
    config = spec()
    config["bootstrap"]["confidence"] = 0.9
    gate.check(report(), report(), config)
    assert seen[0]["confidence"] == 0.9


def test_gate_cli_uses_explicit_verdict_and_exit_code(tmp_path, capsys):
    import yaml
    from lab9.gate import main

    base_path, pr_path, spec_path = (tmp_path / p for p in ("base.json", "pr.json", "spec.yaml"))
    base_path.write_text(json.dumps(report()), encoding="utf-8")
    pr_path.write_text(json.dumps(report(0.7)), encoding="utf-8")
    spec_path.write_text(yaml.safe_dump(spec()), encoding="utf-8")
    args = ["--pr", str(pr_path), "--baseline", str(base_path), "--spec", str(spec_path)]
    assert main(args) == 1
    assert "exit 1 — blocked: pass_rate" in capsys.readouterr().out
    pr_path.write_text(json.dumps(report()), encoding="utf-8")
    assert main(args) == 0
    assert "exit 0 — merge" in capsys.readouterr().out


def test_ci_sanity_rejects_wrong_baseline_shape_and_unregistered_metric():
    from lab9.ci_check import check

    config = {"metrics": [{"id": "reply_amount_correct", "kind": "capability", "blocking": True}]}
    assert check(report(), report(), config) == []
    wrong = report()
    wrong["shape"] = "fixed"
    assert any("baseline shape" in problem for problem in check(report(), wrong, config))
    unknown = copy.deepcopy(config)
    unknown["metrics"][0]["id"] = "unknown_grader"
    assert any("no grader registered" in problem for problem in check(report(), report(), unknown))


def test_harness_map_keeps_orchestration_and_registers_eval():
    import yaml

    root = Path(__file__).resolve().parents[1]
    harness = yaml.safe_load((root / "harness_map.yaml").read_text(encoding="utf-8"))
    assert harness["harness_map_version"] == "1.2"
    assert harness["sections"]["orchestration"]["runner"] == "python -m lab8.run"
    assert harness["sections"]["eval"]["baseline"] == "reports/baseline_v1.json"
