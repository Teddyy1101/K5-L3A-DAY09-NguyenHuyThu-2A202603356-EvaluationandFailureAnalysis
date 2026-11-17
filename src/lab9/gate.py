"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import re

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item
from lab9.graders import GRADERS


def _finite(value) -> bool:
    try:
        return isinstance(value, (int, float)) and math.isfinite(value)
    except (TypeError, OverflowError):
        return False


def _report_integrity(report: dict, spec: dict, name: str):
    problems, pairs, tags = [], Counter(), {}
    if not isinstance(report, dict):
        return [f"{name}: report is not an object"], pairs, tags
    manifest, rows, metrics = report.get("manifest"), report.get("rows"), report.get("metrics")
    if not isinstance(manifest, dict) or not isinstance(rows, list) or not isinstance(metrics, dict):
        return [f"{name}: missing manifest, rows or metrics"], pairs, tags
    if not isinstance(report.get("evaluator_failures"), list) or report["evaluator_failures"]:
        problems.append(f"{name}: evaluator_failures must be an empty list")
    if not isinstance(manifest.get("eval_set_sha"), str) or not manifest["eval_set_sha"]:
        problems.append(f"{name}: missing eval_set_sha")
    items, seeds = manifest.get("items"), manifest.get("seeds")
    if (type(items) is not int or items < 1 or not isinstance(seeds, list) or not seeds
            or any(type(seed) is not int for seed in seeds) or len(set(seeds)) != len(seeds)):
        return problems + [f"{name}: invalid item count or seed manifest"], pairs, tags
    if len(rows) != items * len(seeds):
        problems.append(f"{name}: row count differs from items x seeds")
    definitions = {m["id"]: m for m in spec["metrics"]}
    graded = set(definitions) & GRADERS.keys()
    for mid, value in metrics.items():
        if not _finite(value):
            problems.append(f"{name}: non-finite or missing aggregate {mid}")
    for mid in definitions:
        if mid not in metrics:
            problems.append(f"{name}: aggregate {mid} missing")
    valid_rows = []
    for row in rows:
        if not isinstance(row, dict):
            problems.append(f"{name}: invalid row object")
            continue
        item, seed = row.get("item_id"), row.get("seed")
        if not isinstance(item, str) or not item or type(seed) is not int:
            problems.append(f"{name}: invalid item/seed identity")
            continue
        pairs[item, seed] += 1
        slice_tags = row.get("slices", [])
        if (not isinstance(slice_tags, list) or any(not isinstance(t, str) for t in slice_tags)
                or len(set(slice_tags)) != len(slice_tags)):
            problems.append(f"{name}: invalid slice tags")
            slice_tags = []
        value_tags = frozenset(slice_tags)
        if item in tags and tags[item] != value_tags:
            problems.append(f"{name}: slice tags vary across seeds")
        tags[item] = value_tags
        for mid in graded:
            value = row.get(mid)
            if not _finite(value) or not 0 <= value <= 1:
                problems.append(f"{name}: missing/invalid graded value {mid}")
        valid_rows.append(row)
    identities = {item for item, _ in pairs}
    if len(identities) != items or set(pairs) != {(item, seed) for item in identities for seed in seeds}:
        problems.append(f"{name}: rows do not form the declared item x seed grid")
    if any(count != 1 for count in pairs.values()):
        problems.append(f"{name}: duplicate item/seed rows")

    # Check the reported aggregate against its evidence, not just its threshold.
    for mid in graded:
        values = [row.get(mid) for row in valid_rows]
        if values and all(_finite(v) and 0 <= v <= 1 for v in values):
            expected = sum(values) if mid in ("approval_bypass", "secret_leak") else round(sum(values) / len(values), 4)
            if _finite(metrics.get(mid)) and not math.isclose(metrics[mid], expected, abs_tol=1e-9):
                problems.append(f"{name}: aggregate {mid} disagrees with rows")
    by_item = defaultdict(list)
    for row in valid_rows:
        if _finite(row.get("pass_rate")):
            by_item[row["item_id"]].append(bool(row["pass_rate"]))
    if by_item and len(valid_rows) == sum(map(len, by_item.values())):
        derived = {"pass_5": round(sum(all(v) for v in by_item.values()) / len(by_item), 4)}
        for mid in metrics:
            match = re.fullmatch(r"pass_(at|hat)_([1-9][0-9]*)", mid)
            if match:
                fn = stats.pass_at_k if match[1] == "at" else stats.pass_hat_k
                k = int(match[2])
                if any(len(v) < k for v in by_item.values()):
                    problems.append(f"{name}: insufficient seeds for {mid}")
                else:
                    derived[mid] = round(sum(fn(len(v), sum(v), k) for v in by_item.values()) / len(by_item), 4)
        if "cost_per_success" in metrics:
            costs = [row.get("cost") for row in valid_rows]
            passes = sum(sum(v) for v in by_item.values())
            if not all(_finite(v) and v >= 0 for v in costs) or not passes:
                problems.append(f"{name}: invalid cost/success evidence")
            else:
                derived["cost_per_success"] = round(sum(costs) / passes, 4)
        for mid, expected in derived.items():
            if mid in metrics and _finite(metrics[mid]) and not math.isclose(metrics[mid], expected, abs_tol=1e-9):
                problems.append(f"{name}: aggregate {mid} disagrees with rows")
    return problems, pairs, tags


def _ratchet(current: list[dict], previous: list[dict], *, slices: bool = False) -> list[str]:
    key = (lambda m: (m["name"], m["metric"])) if slices else (lambda m: m["id"])
    indexed = {key(m): m for m in current}
    problems = []
    for old in previous:
        identity = key(old)
        new = indexed.get(identity)
        if new is None:
            problems.append(f"ratchet: removed {'slice' if slices else 'metric'} {identity}")
            continue
        if old.get("blocking") and not new.get("blocking"):
            problems.append(f"ratchet: disabled blocking {identity}")
        old_limits, new_limits = (old, new) if slices else (old.get("threshold", {}), new.get("threshold", {}))
        for limit in ("min", "max", "max_increase"):
            if limit not in old_limits:
                continue
            value, original = new_limits.get(limit), old_limits[limit]
            if not _finite(original) or not _finite(value) or (value < original if limit == "min" else value > original):
                problems.append(f"ratchet: loosened {limit} for {identity}")
        if old_limits.get("no_significant_drop") and not new_limits.get("no_significant_drop"):
            problems.append(f"ratchet: removed no_significant_drop {identity}")
        for field in ("kind", "grader", "level"):
            if field in old and old[field] != new.get(field):
                problems.append(f"ratchet: changed {field} for {identity}")
    return problems


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems = []
    if not isinstance(spec, dict):
        return ["invalid metric spec"]
    metrics = spec.get("metrics")
    slices = spec.get("slices", [])
    if (not isinstance(metrics, list) or not metrics
            or any(not isinstance(m, dict) or not isinstance(m.get("id"), str) for m in metrics)):
        return ["invalid metric spec"]
    if len({m["id"] for m in metrics}) != len(metrics):
        return ["duplicate metric definitions"]
    if (not isinstance(slices, list) or any(not isinstance(s, dict) or not isinstance(s.get("name"), str)
                                           or not isinstance(s.get("metric"), str) for s in slices)):
        return ["invalid slice spec"]
    if len({(s["name"], s["metric"]) for s in slices}) != len(slices):
        return ["duplicate slice definitions"]
    for entry in [m.get("threshold", {}) for m in metrics] + slices:
        if not isinstance(entry, dict):
            return ["invalid metric threshold"]
        for limit in ("min", "max", "max_increase"):
            if limit in entry and not _finite(entry[limit]):
                problems.append(f"non-finite spec threshold {limit}")
    pr_problems, pr_pairs, pr_tags = _report_integrity(pr, spec, "PR")
    base_problems, base_pairs, base_tags = _report_integrity(base, spec, "baseline")
    problems.extend(pr_problems + base_problems)
    if pr_pairs != base_pairs:
        problems.append("PR item/seed pairs differ from baseline")
    if pr_tags != base_tags:
        problems.append("PR slice tags differ from baseline")
    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        problems += _ratchet(metrics, base_spec["metrics"])
        problems += _ratchet(slices, base_spec.get("slices", []), slices=True)
    return list(dict.fromkeys(problems))


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bootstrap = spec.get("bootstrap", {})
    for entry in spec.get("slices", []):
        name, metric = entry["name"], entry["metric"]
        identity = f"slice:{name}/{metric}"
        pr_items, base_items = per_item(pr, metric, name), per_item(base, metric, name)
        failure, note, value = False, "", None
        if not pr_items or set(pr_items) != set(base_items):
            failure, note = True, "missing or unmatched slice items"
        else:
            keys = sorted(pr_items)
            value = sum(pr_items.values()) / len(pr_items)
            failure = "min" in entry and value < entry["min"]
            if entry.get("no_significant_drop"):
                if len(keys) < 2:
                    failure, note = True, "fewer than two paired items for slice CI"
                else:
                    delta, low, high = stats.paired_bootstrap(
                        [pr_items[k] for k in keys], [base_items[k] for k in keys],
                        n_resamples=bootstrap.get("n_resamples", 1000), rng=bootstrap.get("rng", 2027),
                        confidence=bootstrap.get("confidence", 0.95))
                    failure = failure or high < 0
                    note = f"Δ {delta:+.3f} CI [{low:+.3f}, {high:+.3f}]"
        if failure and entry.get("blocking"):
            blocked.append(identity)
        verdict = "BLOCK" if failure and entry.get("blocking") else "warn" if failure else "ok"
        lines.append(f"  {identity} value={value} {note} {verdict}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027),
                                               confidence=bs.get("confidence", 0.95))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    def display(report):
        if not isinstance(report, dict):
            return "<invalid report>", "<missing>"
        manifest = report.get("manifest")
        return (report.get("run_id", "<missing>"),
                manifest.get("eval_set_sha", "<missing>") if isinstance(manifest, dict) else "<missing>")

    pr_id, sha = display(pr)
    base_id, _ = display(base)
    print(f"gate: PR {pr_id} vs main {base_id} · eval set {sha}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
