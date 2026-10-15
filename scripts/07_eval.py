#!/usr/bin/env python
"""Phase 7 evaluation CLI (06_EVAL_SPEC §10).

Runs the benchmark through the real runtime pipeline on a throwaway DB + key
directory (so it never touches production state), computes all metrics, writes
JSON + CSV, and prints a summary. No LLM, no network (ADR-013).
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from compliance_runtime.config.keys import set_keys_dir
from compliance_runtime.evaluation.report import render_text, write_csv, write_json
from compliance_runtime.evaluation.runner import EvaluationRunner
from compliance_runtime.interception.pipeline import build_pipeline
from compliance_runtime.policy.loader import load_policy_set

_MINI = "tests/fixtures/benchmark_mini.jsonl"
_DEFAULT_BENCHMARK = "data/eval/benchmark.jsonl"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the compliance-runtime eval.")
    parser.add_argument("--benchmark", default=_DEFAULT_BENCHMARK)
    parser.add_argument("--config", default="configs/runtime.yaml")
    parser.add_argument("--output-dir", default="results/evals")
    parser.add_argument("--mini", action="store_true",
                        help="use the 20-entry mini benchmark (skips composition)")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    benchmark = Path(_MINI if args.mini else args.benchmark)
    check_composition = not args.mini

    policy_dir = Path(args.config).parent / "policies"
    policy_set = load_policy_set(policy_dir)

    with tempfile.TemporaryDirectory() as tmp:
        set_keys_dir(tmp)
        try:
            pipeline, _ = build_pipeline(args.config, db_path=f"{tmp}/eval.db")
            runner = EvaluationRunner(pipeline, policy_set)
            report = runner.run(benchmark, check_composition=check_composition)
            pipeline.close()
        finally:
            set_keys_dir(None)

    print(render_text(report))

    out_dir = Path(args.output_dir)
    write_json(report, out_dir / f"{report.eval_id}.json")
    write_csv(report, out_dir / f"{report.eval_id}.csv")
    print(f"\nWrote {out_dir / (report.eval_id + '.json')}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # noqa: BLE001 - CLI surfaces a clean error
        print(f"eval failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
