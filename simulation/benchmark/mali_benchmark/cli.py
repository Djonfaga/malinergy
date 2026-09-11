"""Command line entry point: ``mali-benchmark``."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .capability import hand_written_work, matrix, scores
from .compare import compare, provenance
from .effort import access_table, effort_table
from .findings import by_confidence, headline
from .findings import table as findings_table


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mali-benchmark",
        description="Compare the five simulation environments on the Malian system",
    )
    parser.add_argument("--output", default="results")
    parser.add_argument(
        "--sections",
        default="capability,effort,findings,compare",
        help="comma separated: capability, effort, findings, compare, all",
    )
    args = parser.parse_args(argv)

    requested = {s.strip() for s in args.sections.split(",")}
    if "all" in requested:
        requested = {"capability", "effort", "findings", "compare"}
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    lines = ["# Five tools, one system", ""]

    if "capability" in requested:
        print("Capability matrix")
        frame = matrix()
        frame.to_csv(out / "capability_matrix.csv", index=False)
        score = scores()
        print(score.to_string(index=False))
        score.to_csv(out / "capability_scores.csv", index=False)
        hand = hand_written_work()
        hand.to_csv(out / "hand_written_work.csv", index=False)
        lines += ["## Capability matrix", "", _table(frame.drop(columns=["evidence"])), ""]
        lines += ["### Weighted summary", "", _table(score), ""]
        lines += ["### What each tool made us write", "", _table(hand), ""]

    if "effort" in requested:
        print("\nEffort")
        frame = effort_table()
        print(frame.to_string(index=False))
        frame.to_csv(out / "effort.csv", index=False)
        access = access_table()
        access.to_csv(out / "access.csv", index=False)
        lines += ["## Effort", "", _table(frame), ""]
        lines += ["### What it takes to run each tool", "", _table(access), ""]

    if "findings" in requested:
        print("\nFindings")
        frame = findings_table()
        frame.to_csv(out / "findings.csv", index=False)
        print(frame[["area", "finding", "value"]].to_string(index=False))
        lines += ["## Findings", "",
                  _table(frame[["area", "finding", "value", "branch", "confidence"]]), ""]
        lines += ["### By confidence", "", _table(by_confidence()), ""]
        headline_frame = headline()
        headline_frame.to_csv(out / "headline_findings.csv", index=False)

    if "compare" in requested:
        print("\nNumerical comparison")
        result = compare()
        for tool, present in result.available.items():
            print(f"  {tool:<22} {'ran' if present else 'not run'}")
        for note in result.notes:
            print(f"  - {note}")
        if not result.table.empty:
            result.table.to_csv(out / "tool_results.csv", index=False)
        if not result.differences.empty:
            print()
            print(result.differences.to_string(index=False))
            result.differences.to_csv(out / "differences.csv", index=False)
            lines += ["## Numerical comparison", "", _table(result.differences), ""]
        else:
            lines += ["## Numerical comparison", "",
                      "Only one steady-state tool produced results on this machine, "
                      "so no cross-tool numerical comparison was possible.", ""]
        prov = provenance()
        prov.to_csv(out / "provenance.csv", index=False)
        lines += ["### How each tool was verified", "", _table(prov), ""]
        lines += [f"- {note}" for note in result.notes] + [""]

    report = out / "report.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nreport -> {report}")
    return 0


def _table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_no rows_"
    headers = [str(c) for c in frame.columns]
    rows = [
        [f"{v:,.4g}" if isinstance(v, float) else ("-" if pd.isna(v) else str(v)) for v in record]
        for record in frame.itertuples(index=False, name=None)
    ]
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


if __name__ == "__main__":
    raise SystemExit(main())
