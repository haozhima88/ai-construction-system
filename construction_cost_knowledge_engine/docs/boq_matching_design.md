# BOQ Matching Design

The v0.1 matcher is deterministic and does not call a large model.

Input shape:

```python
match_boq_line(conn, boq_name, boq_features, boq_unit) -> list[MatchCandidate]
```

Scoring:

- Name similarity: 55%
- Unit consistency: 20%
- Feature/token overlap: 15%
- Category hint: 10%

Candidates below `0.75` are marked `need_human_review = True`.

Returned fields include cost item ID, item name, normalized unit, labor/material/machine unit prices, total unit cost, score, reason, quality flags, and review marker.
