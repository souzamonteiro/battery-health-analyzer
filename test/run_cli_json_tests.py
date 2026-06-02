#!/usr/bin/env python3
"""Run batch regression tests for battery_bdf_analyzer_console.py JSON output.

For each `*.bdf.csv` file in this directory, this script:
1. Runs the CLI analyzer with `--json`.
2. Compares the generated JSON against the corresponding `*.test` file.
3. Prints a per-case status and a final summary report.

Exit code:
- 0: all tests passed
- 1: one or more tests failed
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = Path(__file__).resolve().parent
ANALYZER = ROOT / "battery_bdf_analyzer_console.py"
PLOTS_DIR = TEST_DIR / "plots"


@dataclass
class CaseResult:
    name: str
    passed: bool
    reason: str = ""


def _normalize_json(value: Any) -> Any:
    """Normalize JSON structure for stable semantic comparison."""
    if isinstance(value, dict):
        return {k: _normalize_json(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [_normalize_json(v) for v in value]
    return value


def _normalize_report_paths(value: Any) -> Any:
    """Normalize path-like fields that can vary by execution environment."""
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if key == "saved_plots" and isinstance(item, list):
                normalized[key] = [Path(str(plot_path)).name for plot_path in item]
            else:
                normalized[key] = _normalize_report_paths(item)
        return normalized
    if isinstance(value, list):
        return [_normalize_report_paths(item) for item in value]
    return value


def run_single_case(input_file: Path) -> CaseResult:
    """Execute analyzer and compare generated JSON with expected `.test` file."""
    name = input_file.name
    if name.endswith(".bdf.csv"):
        stem = name[:-len(".bdf.csv")]
    else:
        stem = input_file.stem
    generated_json = TEST_DIR / f"{stem}.json"
    expected_test = TEST_DIR / f"{stem}.test"

    if not expected_test.exists():
        return CaseResult(stem, False, f"Missing expected file: {expected_test.name}")

    cmd = [
        sys.executable,
        str(ANALYZER),
        str(input_file),
        "--json",
        "--outdir",
        str(PLOTS_DIR),
        "--eol",
        "70",
    ]

    try:
        completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except Exception as exc:
        return CaseResult(stem, False, f"Failed to execute analyzer: {exc}")

    if completed.returncode != 0:
        details = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
        return CaseResult(stem, False, f"Analyzer failed: {details}")

    if not generated_json.exists():
        return CaseResult(stem, False, f"Generated JSON not found: {generated_json.name}")

    try:
        with open(generated_json, "r", encoding="utf-8") as fh:
            got = json.load(fh)
        with open(expected_test, "r", encoding="utf-8") as fh:
            expected = json.load(fh)
    except Exception as exc:
        return CaseResult(stem, False, f"JSON parse error: {exc}")

    got_normalized = _normalize_json(_normalize_report_paths(got))
    expected_normalized = _normalize_json(_normalize_report_paths(expected))

    if got_normalized != expected_normalized:
        return CaseResult(stem, False, "JSON mismatch with expected .test baseline")

    return CaseResult(stem, True)


def main() -> int:
    """Run all test cases and print a consolidated report."""
    cases = sorted(TEST_DIR.glob("case_*.bdf.csv"))
    if not cases:
        print("No test cases found (expected files like case_1.bdf.csv).")
        return 1

    print("=" * 72)
    print("BDF CONSOLE JSON REGRESSION TEST REPORT")
    print("=" * 72)
    print(f"Analyzer: {ANALYZER}")
    print(f"Test directory: {TEST_DIR}")
    print(f"Cases discovered: {len(cases)}")
    print()

    results: list[CaseResult] = []
    for case in cases:
        result = run_single_case(case)
        results.append(result)
        status = "PASS" if result.passed else "FAIL"
        if result.reason:
            print(f"[{status}] {result.name}: {result.reason}")
        else:
            print(f"[{status}] {result.name}")

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    print()
    print("-" * 72)
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print("-" * 72)

    if failed:
        print("Result: FAILED")
        return 1

    print("Result: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
