from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def build_import_report(conn: sqlite3.Connection) -> str:
    batch = conn.execute(
        "SELECT * FROM source_import_batches ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if not batch:
        return "# Import Report\n\nNo import batches found.\n"

    quality_rows = conn.execute(
        "SELECT quality_flags, source_row_no FROM cost_items WHERE source_batch_id = ?",
        (batch["id"],),
    ).fetchall()
    counts: dict[str, int] = {}
    review_rows: list[int] = []
    for row in quality_rows:
        flags = json.loads(row["quality_flags"] or "[]")
        if flags:
            review_rows.append(int(row["source_row_no"]))
        for flag in flags:
            counts[flag] = counts.get(flag, 0) + 1

    component_count = conn.execute(
        "SELECT COUNT(*) FROM cost_price_components WHERE source_batch_id = ?",
        (batch["id"],),
    ).fetchone()[0]
    category_count = conn.execute("SELECT COUNT(*) FROM cost_categories").fetchone()[0]
    unit_count = conn.execute("SELECT COUNT(*) FROM unit_dictionary").fetchone()[0]

    lines = [
        "# Import Report",
        "",
        f"- Import time: {batch['imported_at']}",
        f"- Source file: {batch['source_file_name']}",
        f"- Source file SHA256: {batch['source_file_hash']}",
        f"- Sheet: {batch['source_sheet_name'] or ''}",
        f"- Raw valid rows: {batch['row_count'] or 0}",
        f"- Imported cost items: {batch['success_count'] or 0}",
        f"- Price components: {component_count}",
        f"- Categories: {category_count}",
        f"- Units: {unit_count}",
        "",
        "## Quality Issue Counts",
        "",
    ]
    if counts:
        lines.extend(f"- {flag}: {count}" for flag, count in sorted(counts.items()))
    else:
        lines.append("- None")
    lines.extend(["", "## Rows Needing Manual Review", ""])
    if review_rows:
        lines.append(", ".join(str(row_no) for row_no in sorted(set(review_rows))))
    else:
        lines.append("None")
    lines.append("")
    return "\n".join(lines)


def write_import_report(conn: sqlite3.Connection, output_path: str | Path) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_import_report(conn), encoding="utf-8")
