# Reference Extraction Scripts

This folder contains isolated scripts for standard cost item reference extraction pilots.

## Stage 1: A.1.1 Page Registry

Run from the repository root or directly with an explicit project root:

```powershell
python construction_cost_knowledge_engine/scripts/reference_extraction/stage1_locate_a111_pages.py
```

The Stage 1 script only performs directory-level extraction and page boundary registration for A.1.1 土石方工程. It does not extract A1-1-* quota item details, does not generate standard_cost_item_reference candidates, and does not write to any database.

Outputs are written to:

```text
construction_cost_knowledge_engine/data/private/reference_extraction/runs/A111_stage1/
construction_cost_knowledge_engine/docs/reference_extraction/stage1_page_registry_A111.md
```

`data/private` outputs are local run artifacts and should not be committed.
