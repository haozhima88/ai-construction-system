# Extraction Rules - A.1.1 Stage 1

## Scope

Stage 1 is limited to A.1.1 土石方工程 directory-level extraction, page registry creation, and boundary confirmation.

Stage 1 must not:

- Extract A1-1-* quota item detail candidates.
- Generate `standard_cost_item_reference` detail records.
- Write to any database.
- Modify migrations, existing importer/normalizer/validator/review pipeline, `cost_items`, `knowledge_review_records`, or `internal_price_library` logic.
- Mark anything as `approved`.

## Page Numbering

- `source_page` uses `pdf_page`.
- `pdf_page` is the PDF physical page number, 1-based.
- `pdf_page_index` is the programmatic page index, 0-based.
- `book_page` is the printed page number inside the source book.
- In the A.1.1 range, `book_page = pdf_page - 40` is broadly observed, but extraction must retain `evidence_text_sample` and must not rely only on the formula.

## Knowledge Governance

- PDF extraction results cannot be treated as final enterprise `standard_name` values.
- Directory-level extraction does not generate reference items.
- Stage 2 is the first stage allowed to extract `source_code` values from quota tables.
- All future candidate records must remain `pending` until human review.
- AI/rule results are suggestions only and must preserve traceability.

## Code Distinction

- Quota item numbers such as `A1-1-*` are future Stage 2 `source_code` values.
- Resource codes such as `00010010`, `990123010`, or other `990...` values are labor/material/machine resource codes and must not be treated as `source_code`.

## Known PDF Risks

- Unit glyph issues such as `` / `\ue000` are not repaired in Stage 1; they are only registered as risks for Stage 2.
- Blank or no-text pages must be recorded as parse issues rather than silently skipped.
- Divider/title pages near section boundaries must be kept as boundary QA notes.
