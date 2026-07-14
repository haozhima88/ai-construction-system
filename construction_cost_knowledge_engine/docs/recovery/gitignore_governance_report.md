# Gitignore Governance Report

## 1. Task Scope

Fix the ignore governance issue where `construction_cost_knowledge_engine/docs/reference_extraction/reference_artifact_manifest.csv` was hidden by `.gitignore`, while keeping private artifacts under `construction_cost_knowledge_engine/data/private/` ignored.

This task did not write databases, modify migrations, modify schemas, change `src/cost_engine` runtime flow, generate approved records, generate `internal_price_library`, import seed data, use mock SQLite, modify `data/private`, or continue MAP-A111-QA1.

## 2. Original Ignore Issue

`git check-ignore -v` showed:

```text
construction_cost_knowledge_engine/.gitignore:13:*.csv construction_cost_knowledge_engine/docs/reference_extraction/reference_artifact_manifest.csv
```

The subproject-level global `*.csv` rule correctly protected generated CSV data by default, but it was too broad for governance artifacts. `reference_artifact_manifest.csv` is a manifest that records row counts and SHA256 values for private artifacts and should be tracked.

`data/private/` was ignored by the root `.gitignore`, which is correct and should remain unchanged.

## 3. Rules Changed

Updated `construction_cost_knowledge_engine/.gitignore` by adding explicit allow rules:

```gitignore
!docs/recovery/*.md
!docs/reference_extraction/*.md
!docs/reference_extraction/*.csv
```

The existing private/generated-data ignore rules remain:

```gitignore
data/private/*
*.db
*.sqlite
*.sqlite3
*.csv
```

## 4. Files That Should Be Trackable

- `construction_cost_knowledge_engine/docs/reference_extraction/CURRENT_REFERENCE_PIPELINE_STATE.md`
- `construction_cost_knowledge_engine/docs/reference_extraction/REFERENCE_ARTIFACT_MANIFEST.md`
- `construction_cost_knowledge_engine/docs/reference_extraction/reference_artifact_manifest.csv`
- `construction_cost_knowledge_engine/docs/recovery/*.md`

## 5. Files That Must Remain Ignored

- `construction_cost_knowledge_engine/data/private/`
- `construction_cost_knowledge_engine/data/private/reference_extraction/runs/`
- `construction_cost_knowledge_engine/data/private/reference_extraction/source_excels/`
- `construction_cost_knowledge_engine/data/private/reference_extraction/source_standards/`
- mock SQLite artifacts
- seed CSV artifacts that are not source of truth
- generated CSV files outside approved governance doc locations

Mock SQLite and seed CSV artifacts remain prohibited as source of truth.

## 6. Verification

Expected verification after this change:

- `reference_artifact_manifest.csv` should no longer appear with `!!` in `git status --short --ignored`.
- `construction_cost_knowledge_engine/data/private/` should still appear ignored.
- `docs/recovery/*.md` should be visible to Git.
- `docs/reference_extraction/*.md` and `docs/reference_extraction/*.csv` should be visible to Git.

## 7. Recommendation

Track governance manifests and recovery/current-state Markdown documents in Git. Keep private source files, extracted private runs, mock SQLite, seed CSV, and generated real-data artifacts ignored unless a future governance decision explicitly whitelists a specific non-private manifest.
