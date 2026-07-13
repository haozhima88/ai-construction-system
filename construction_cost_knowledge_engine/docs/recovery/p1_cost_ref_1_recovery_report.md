# P1-COST-REF-1 Recovery Report

## 1. Incident Summary

The previous `P1-COST-REF-1` task drifted away from the current reference extraction and mapping candidate route. It introduced a database MVP path: migration changes, a schema dataclass, seed CSV import, mock SQLite storage, preview scripts, and a seed-focused test.

That direction is premature for the current project state. The active project route is still file-based reference extraction, candidate generation, mapping candidate review, and manual QA packaging. Database modeling and seed import should not continue before the A.1.1 mapping candidates have completed manual QA.

## 2. Current Correct Pipeline State

- GB/T 50854 bill reference full extraction complete.
- GD2018 A.1.1 quota candidate complete.
- MAP-A111-0 mapping candidate complete.
- Next stage is MAP-A111-QA1 manual QA pack.

Source of truth should remain the candidate CSV outputs under `construction_cost_knowledge_engine/data/private/reference_extraction/runs/`, not mock seed CSV or mock SQLite.

During this recovery audit, the current checkout did not contain `construction_cost_knowledge_engine/data/private/reference_extraction/runs/`; no private reference extraction outputs were modified.

## 3. Files Modified by P1-COST-REF-1

Tracked files modified:

- `construction_cost_knowledge_engine/migrations/001_init_cost_engine.sql`
- `construction_cost_knowledge_engine/src/cost_engine/schemas.py`

Untracked or ignored artifacts produced by the drifted task:

- `construction_cost_knowledge_engine/data/mock/standard_cost_item_reference_A111_seed.csv`
- `construction_cost_knowledge_engine/data/mock/standard_cost_reference_mvp.sqlite`
- `construction_cost_knowledge_engine/scripts/import_standard_reference_seed.py`
- `construction_cost_knowledge_engine/scripts/preview_standard_reference.py`
- `construction_cost_knowledge_engine/tests/test_standard_reference_seed.py`
- `construction_cost_knowledge_engine/docs/reference_extraction/standard_cost_item_reference_mvp.md`

Audit findings:

- `001_init_cost_engine.sql` contains a new `standard_cost_item_reference` table and related indexes.
- `schemas.py` contains a new `StandardCostItemReference` dataclass.
- The seed CSV existed before archive and contained 43 rows.
- The mock SQLite existed before archive and contained 43 rows in `standard_cost_item_reference`.
- The mock SQLite contained 0 rows in `internal_price_library`, 0 rows in `cost_items`, and 0 rows in `knowledge_review_records`.

## 4. Risk Assessment

- Migration and schema changes are premature because the current route has not entered database integration.
- The 43-row seed is a mock MVP sample and is not the current truth for GD2018 A.1.1.
- The SQLite file is mock-only and must not be treated as a project source of truth.
- Continuing the DB route now could fork the knowledge pipeline away from the completed reference extraction and mapping candidate assets.
- The correct next work should resume from MAP-A111-QA1, not from seed import or schema expansion.

## 5. Recommended Action

Recommended tracked rollback commands, pending user confirmation:

```powershell
git checkout -- construction_cost_knowledge_engine/migrations/001_init_cost_engine.sql
git checkout -- construction_cost_knowledge_engine/src/cost_engine/schemas.py
```

Archive completed in this recovery turn:

- `construction_cost_knowledge_engine/docs/reference_extraction/standard_cost_item_reference_mvp.md` moved to `construction_cost_knowledge_engine/docs/archive/p1_cost_ref_1/standard_cost_item_reference_mvp.md`
- `construction_cost_knowledge_engine/scripts/import_standard_reference_seed.py` moved to `construction_cost_knowledge_engine/scripts/archive/p1_cost_ref_1/import_standard_reference_seed.py`
- `construction_cost_knowledge_engine/scripts/preview_standard_reference.py` moved to `construction_cost_knowledge_engine/scripts/archive/p1_cost_ref_1/preview_standard_reference.py`
- `construction_cost_knowledge_engine/tests/test_standard_reference_seed.py` moved to `construction_cost_knowledge_engine/tests/archive/p1_cost_ref_1/test_standard_reference_seed.py`
- `construction_cost_knowledge_engine/data/mock/standard_cost_item_reference_A111_seed.csv` moved to `construction_cost_knowledge_engine/data/mock/archive/p1_cost_ref_1/standard_cost_item_reference_A111_seed.csv`
- `construction_cost_knowledge_engine/data/mock/standard_cost_reference_mvp.sqlite` moved to `construction_cost_knowledge_engine/data/mock/archive/p1_cost_ref_1/standard_cost_reference_mvp.sqlite`

Continue with `MAP-A111-QA1`: generate the manual QA pack for A.1.1 quota-to-bill mapping candidates.

## 6. Do Not Use List

The following artifacts must not be used as current mainline inputs:

- `standard_cost_reference_mvp.sqlite`
- `standard_cost_item_reference_A111_seed.csv`
- `import_standard_reference_seed.py`
- `preview_standard_reference.py`

They are archived for traceability only.

## 7. Recovery Status

Archive status: completed for the allowed P1-COST-REF-1 artifacts.

Tracked rollback status: not executed. User confirmation is still required before reverting:

- `construction_cost_knowledge_engine/migrations/001_init_cost_engine.sql`
- `construction_cost_knowledge_engine/src/cost_engine/schemas.py`

No database writes, seed imports, new mappings, approvals, `internal_price_library` generation, full-book parsing, or `data/private` deletions were performed in this recovery turn.
