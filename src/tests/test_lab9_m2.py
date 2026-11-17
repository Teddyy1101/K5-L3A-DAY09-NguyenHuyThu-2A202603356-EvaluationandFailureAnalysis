"""M2 edge cases and judge acceptance decisions, independent of M4 bootstrap."""

import csv
import math
from pathlib import Path

import pytest

pytestmark = pytest.mark.student
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("human,judge,expected", [
    (["PASS", "FAIL", "FAIL", "PASS"], ["PASS", "FAIL", "PASS", "FAIL"],
     {"tp": 1, "fp": 1, "fn": 1, "tn": 1}),
    (["FAIL", "PASS"], ["PASS", "PASS"], {"tp": 0, "fp": 0, "fn": 1, "tn": 1}),
])
def test_confusion_has_fail_as_positive(human, judge, expected):
    from lab9.stats import confusion

    assert confusion(human, judge) == expected


@pytest.mark.parametrize("human,judge", [([], []), (["PASS"], []), (["UNKNOWN"], ["PASS"])])
def test_confusion_rejects_bad_samples(human, judge):
    from lab9.stats import confusion

    with pytest.raises(ValueError):
        confusion(human, judge)


def test_precision_and_recall_are_zero_without_positive_samples():
    from lab9.stats import precision_recall

    assert precision_recall(["PASS", "PASS"], ["PASS", "PASS"]) == (0.0, 0.0)
    assert precision_recall(["FAIL", "PASS"], ["PASS", "PASS"]) == (0.0, 0.0)


def test_kappa_perfect_agreement_and_perfect_disagreement():
    from lab9.stats import cohen_kappa

    assert cohen_kappa(["PASS", "FAIL"], ["PASS", "FAIL"]) == 1.0
    assert cohen_kappa(["PASS", "FAIL"], ["FAIL", "PASS"]) == -1.0


@pytest.mark.parametrize("label", ["PASS", "FAIL"])
def test_kappa_is_undefined_for_identical_constant_labels(label):
    from lab9.stats import cohen_kappa

    with pytest.raises(ValueError):
        cohen_kappa([label] * 3, [label] * 3)


@pytest.mark.parametrize("observed,sensitivity,specificity,expected", [
    (0.28, 0.8, 66 / 70, 0.3), (0.0, 0.8, 0.9, 0.0), (1.0, 0.8, 0.9, 1.0),
])
def test_rogan_gladen_corrects_and_clips(observed, sensitivity, specificity, expected):
    from lab9.stats import rogan_gladen

    assert rogan_gladen(observed, sensitivity, specificity) == pytest.approx(expected)


@pytest.mark.parametrize("rates", [(0.5, 0.5, 0.5), (float("nan"), 0.8, 0.9),
                                   (0.5, float("inf"), 0.9), (0.5, -0.1, 0.9), (1.1, 0.8, 0.9)])
def test_rogan_gladen_rejects_undefined_or_invalid_rates(rates):
    from lab9.stats import rogan_gladen

    with pytest.raises(ValueError):
        rogan_gladen(*rates)


def test_public_calibration_accepts_tone_and_rejects_helpful():
    from lab9.judge import calibrate

    tone = calibrate(ROOT / "data/eval/judge_tone_public.csv")
    helpful = calibrate(ROOT / "data/eval/judge_helpful_public.csv")
    assert tone["passed"] is True
    assert helpful["passed"] is False
    assert len(tone["disagreements"]) >= 5


def test_constant_judge_fails_cleanly_without_fake_correction(tmp_path):
    from lab9.judge import calibrate, main

    sample = tmp_path / "constant.csv"
    with sample.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=["item_id", "reply", "human", "judge"])
        writer.writeheader()
        for i in range(3):
            writer.writerow({"item_id": str(i), "reply": "ok", "human": "PASS", "judge": "PASS"})
    result = calibrate(sample)
    assert result["passed"] is False
    assert math.isnan(result["kappa"])
    assert result["corrected_fail_rate"] is None
    assert "undefined" in result["correction_error"]
    assert main(["--csv", str(sample)]) == 1


@pytest.mark.parametrize("metric,value", [("kappa", 0.5996), ("precision", 0.7996), ("recall", 0.6996)])
def test_rounding_cannot_turn_a_failed_floor_into_a_pass(monkeypatch, metric, value):
    from lab9 import judge

    raw = {"kappa": 0.9, "precision": 0.9, "recall": 0.9, metric: value}
    monkeypatch.setattr(judge.stats, "cohen_kappa", lambda *args: raw["kappa"])
    monkeypatch.setattr(judge.stats, "precision_recall", lambda *args: (raw["precision"], raw["recall"]))
    result = judge.calibrate(ROOT / "data/eval/judge_tone_public.csv")
    assert result[metric] == judge.FLOORS[metric]
    assert result["passed"] is False
