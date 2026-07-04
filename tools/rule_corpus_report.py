from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from avcleaner.rule_corpus import FIXTURE_ROOT, build_report, format_report  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate AVcleaner rule filename corpus.")
    parser.add_argument("--fixtures", type=Path, default=FIXTURE_ROOT)
    args = parser.parse_args(argv)
    fixture_root = args.fixtures.resolve()
    if not fixture_root.is_relative_to(REPO_ROOT.resolve()):
        print("Fixture root must stay inside the repository.", file=sys.stderr)
        return 2
    report = build_report(fixture_root)
    print(format_report(report))
    return 1 if report.total_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
