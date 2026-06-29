from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cost_engine.db import connect
from cost_engine.reports.import_report import write_import_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a privacy-safe import report.")
    parser.add_argument("--db", required=True, help="SQLite database path")
    parser.add_argument("--output", required=True, help="Markdown report output path")
    args = parser.parse_args()

    with connect(args.db) as conn:
        write_import_report(conn, args.output)
    print(f"wrote report: {args.output}")


if __name__ == "__main__":
    main()
