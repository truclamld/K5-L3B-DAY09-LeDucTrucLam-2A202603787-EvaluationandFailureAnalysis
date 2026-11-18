"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item


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
    problems: list[str] = []

    def finite_number(value: object) -> bool:
        # bool is an int subclass, but is not a meaningful aggregate metric.
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

    manifest = pr.get("manifest") or {}
    base_manifest = base.get("manifest") or {}
    rows = pr.get("rows")
    base_rows = base.get("rows")
    metrics = pr.get("metrics")

    if not isinstance(rows, list):
        problems.append("rows is missing or is not a list")
        rows = []
    if not isinstance(base_rows, list):
        problems.append("baseline rows is missing or is not a list")
        base_rows = []
    if not isinstance(metrics, dict):
        problems.append("metrics is missing or is not an object")
        metrics = {}

    for metric_id, value in metrics.items():
        if not finite_number(value):
            problems.append(f"metric {metric_id} is not finite")

    items, seeds = manifest.get("items"), manifest.get("seeds")
    if not isinstance(items, int) or isinstance(items, bool) or items < 0 or not isinstance(seeds, list):
        problems.append("manifest items/seeds are invalid")
    elif len(rows) != items * len(seeds):
        problems.append(f"row count {len(rows)} != manifest items × seeds ({items} × {len(seeds)})")

    def row_keys(source: list) -> tuple[set[tuple[object, object]], bool]:
        keys: set[tuple[object, object]] = set()
        valid = True
        for index, row in enumerate(source):
            if not isinstance(row, dict) or row.get("item_id") is None or row.get("seed") is None:
                problems.append(f"row {index} has no valid item_id/seed")
                valid = False
                continue
            key = (row["item_id"], row["seed"])
            if key in keys:
                problems.append(f"duplicate row for item_id/seed {key!r}")
                valid = False
            keys.add(key)
        return keys, valid

    pr_keys, _ = row_keys(rows)
    base_keys, _ = row_keys(base_rows)
    if pr_keys != base_keys:
        problems.append("(item_id, seed) rows differ from baseline")

    failures = pr.get("evaluator_failures")
    if failures:
        problems.append("evaluator_failures is non-empty")

    # Only per-row grader outputs are checked here. Aggregate-only metrics such as
    # pass_hat_5 and system summaries do not have a value on each row.
    row_fields = {k for r in rows if isinstance(r, dict) for k in r}
    row_metric_ids = {
        m.get("id") for m in spec.get("metrics", [])
        if isinstance(m, dict) and m.get("id") and
        (m.get("id") in row_fields or
         (m.get("level") != "system" and not str(m.get("id")).startswith(("pass_hat_", "pass_at_"))))
    }
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        for metric_id in row_metric_ids:
            if metric_id not in row or row[metric_id] is None:
                problems.append(f"row {index} has missing graded metric {metric_id}")

    # Slice membership is part of the evaluated evidence. Compare by identity after
    # checking the row sets so relabelling cannot hide a regression from a slice.
    base_by_key = {(r.get("item_id"), r.get("seed")): r for r in base_rows if isinstance(r, dict)}
    for row in rows:
        if not isinstance(row, dict) or (row.get("item_id"), row.get("seed")) not in base_by_key:
            continue
        key = (row.get("item_id"), row.get("seed"))
        tags = row.get("slices") or []
        base_tags = base_by_key[key].get("slices") or []
        if not isinstance(tags, list) or not isinstance(base_tags, list) or set(tags) != set(base_tags):
            problems.append(f"slice tags differ from baseline for {key!r}")

    if base_spec is not None:
        # Ratcheting applies only within an eval-set version; changing the eval set
        # requires a newly reviewed baseline/spec pair.
        if spec.get("eval_set_version") == base_spec.get("eval_set_version"):
            def compare_rules(current: list, previous: list, label: str) -> None:
                old_by_id = {x.get("id"): x for x in previous if isinstance(x, dict) and x.get("id")}
                new_by_id = {x.get("id"): x for x in current if isinstance(x, dict) and x.get("id")}
                for mid, old in old_by_id.items():
                    new = new_by_id.get(mid)
                    if new is None:
                        problems.append(f"{label} {mid} was removed")
                        continue
                    if old.get("blocking") and not new.get("blocking"):
                        problems.append(f"{label} {mid} is no longer blocking")
                    old_th = old.get("threshold") or ({k: old[k] for k in ("min", "max", "max_increase", "no_significant_drop") if k in old})
                    new_th = new.get("threshold") or ({k: new[k] for k in ("min", "max", "max_increase", "no_significant_drop") if k in new})
                    if "max" in old_th and ("max" not in new_th or new_th["max"] > old_th["max"]):
                        problems.append(f"{label} {mid} max threshold was loosened")
                    if "min" in old_th and ("min" not in new_th or new_th["min"] < old_th["min"]):
                        problems.append(f"{label} {mid} min threshold was loosened")
                    if "max_increase" in old_th and ("max_increase" not in new_th or new_th["max_increase"] > old_th["max_increase"]):
                        problems.append(f"{label} {mid} max_increase threshold was loosened")
                    if old_th.get("no_significant_drop") and not new_th.get("no_significant_drop"):
                        problems.append(f"{label} {mid} no_significant_drop was removed")

            compare_rules(spec.get("metrics", []), base_spec.get("metrics", []), "metric")
            compare_rules(spec.get("slices", []), base_spec.get("slices", []), "slice")

    # Preserve order while keeping diagnostics readable if multiple checks find the
    # same underlying issue.
    return list(dict.fromkeys(problems))


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for rule in spec.get("slices", []):
        name, metric = rule["name"], rule["metric"]
        values = per_item(pr, metric, slice_name=name)
        baseline = per_item(base, metric, slice_name=name)
        val = sum(values.values()) / len(values) if values else None
        verdict, note = "ok", ""

        # A missing slice/metric cannot silently pass a blocking rule.
        if val is None:
            verdict = "missing"
        elif "min" in rule and val < rule["min"]:
            verdict = "fail"

        if rule.get("no_significant_drop") and val is not None:
            keys = sorted(set(values) & set(baseline))
            if not keys:
                verdict = "missing"
                note = "no paired baseline items"
            else:
                d, lo, hi = stats.paired_bootstrap(
                    [values[k] for k in keys], [baseline[k] for k in keys],
                    n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027),
                    confidence=bs.get("confidence", 0.95),
                )
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"

        if verdict != "ok" and rule.get("blocking"):
            blocked.append(f"slice:{name}/{metric}")
        label = {"ok": "ok", "missing": "MISSING"}.get(
            verdict, "BLOCK" if rule.get("blocking") else "warn")
        lines.append(f"  slice:{name}/{metric:<14} {val!s:<8} {json.dumps(rule):<40} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
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
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
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
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
