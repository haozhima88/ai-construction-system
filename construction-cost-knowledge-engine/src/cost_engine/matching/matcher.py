from __future__ import annotations

import json
import sqlite3

from cost_engine.matching.scoring import text_similarity, token_overlap, unit_score
from cost_engine.schemas import MatchCandidate


def match_boq_line(
    conn: sqlite3.Connection,
    boq_name: str,
    boq_features: str = "",
    boq_unit: str = "",
    category_hint: str = "",
    threshold: float = 0.75,
    limit: int = 5,
) -> list[MatchCandidate]:
    rows = conn.execute(
        """
        SELECT
            ci.id,
            ci.item_name,
            ci.normalized_item_name,
            ci.quality_flags,
            COALESCE(ud.normalized_unit, '') AS unit,
            COALESCE(MAX(CASE WHEN cpc.component_type = 'labor' THEN cpc.unit_price END), 0) AS labor_unit_price,
            COALESCE(MAX(CASE WHEN cpc.component_type = 'material' THEN cpc.unit_price END), 0) AS material_unit_price,
            COALESCE(MAX(CASE WHEN cpc.component_type = 'machine' THEN cpc.unit_price END), 0) AS machine_unit_price,
            COALESCE(cc1.category_name, '') || ' ' || COALESCE(cc2.category_name, '') AS categories
        FROM cost_items ci
        LEFT JOIN unit_dictionary ud ON ud.id = ci.unit_id
        LEFT JOIN cost_categories cc1 ON cc1.id = ci.category_level_1_id
        LEFT JOIN cost_categories cc2 ON cc2.id = ci.category_level_2_id
        LEFT JOIN cost_price_components cpc ON cpc.cost_item_id = ci.id
        WHERE ci.item_status = 'active'
        GROUP BY ci.id
        """
    ).fetchall()
    candidates: list[MatchCandidate] = []
    for row in rows:
        name_score = text_similarity(boq_name, row["normalized_item_name"])
        unit_match = unit_score(boq_unit, row["unit"])
        feature_score = token_overlap(boq_features, row["item_name"] + " " + row["categories"])
        category_score = text_similarity(category_hint, row["categories"]) if category_hint else 0.0
        score = name_score * 0.55 + unit_match * 0.20 + feature_score * 0.15 + category_score * 0.10
        flags = json.loads(row["quality_flags"] or "[]")
        total = float(row["labor_unit_price"] + row["material_unit_price"] + row["machine_unit_price"])
        reason = (
            f"name={name_score:.2f}; unit={unit_match:.2f}; "
            f"features={feature_score:.2f}; category={category_score:.2f}"
        )
        candidates.append(
            MatchCandidate(
                cost_item_id=int(row["id"]),
                item_name=row["item_name"],
                unit=row["unit"],
                labor_unit_price=float(row["labor_unit_price"]),
                material_unit_price=float(row["material_unit_price"]),
                machine_unit_price=float(row["machine_unit_price"]),
                total_unit_cost=total,
                match_score=round(score, 4),
                match_reason=reason,
                quality_flags=flags,
                need_human_review=score < threshold,
            )
        )
    candidates.sort(key=lambda candidate: candidate.match_score, reverse=True)
    return candidates[:limit]


def log_match(
    conn: sqlite3.Connection,
    boq_line_id: str,
    boq_item_name: str,
    boq_unit: str,
    candidate: MatchCandidate | None,
) -> None:
    conn.execute(
        """
        INSERT INTO boq_match_logs
        (boq_line_id, boq_item_name, boq_unit, matched_cost_item_id, match_score, match_reason, need_human_review, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            boq_line_id,
            boq_item_name,
            boq_unit,
            candidate.cost_item_id if candidate else None,
            candidate.match_score if candidate else None,
            candidate.match_reason if candidate else "no candidate",
            1 if (candidate is None or candidate.need_human_review) else 0,
        ),
    )
    conn.commit()
