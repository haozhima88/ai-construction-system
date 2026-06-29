# PROJECT_CONTEXT

## Project Root

E:\workspace\01_Projects\ai-construction-system

## Subproject Root

E:\workspace\01_Projects\ai-construction-system\construction_cost_knowledge_engine

## Current Phase

Construction Cost Knowledge Engine V0.1

## Source of Truth

The source of truth for the current data model is:

docs/Cost数据库模型_V0_1.md

Do not use Temp files.

## Current Goal

Update the cost knowledge engine according to the V0.1 data model.

## Files To Update

- construction_cost_knowledge_engine/migrations/001_init_cost_engine.sql
- construction_cost_knowledge_engine/docs/data_model.md
- construction_cost_knowledge_engine/src/cost_engine/
- construction_cost_knowledge_engine/tests/

## Rules

- Keep raw Excel rows traceable.
- Do not commit private Excel files.
- Do not expose real price data in tests, README, logs, or docs.
- Output generated database files only to data/private/.
- Use SQLite for this subproject.
- Keep functions small and testable.