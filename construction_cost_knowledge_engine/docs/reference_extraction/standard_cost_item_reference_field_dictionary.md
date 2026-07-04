# standard_cost_item_reference Field Dictionary - Stage 2 / Stage 3 Plan

This dictionary describes planned fields for later Stage 2 / Stage 3 extraction. Stage 1 does not generate `standard_cost_item_reference` detail data.

| Field | Planned meaning | Stage 1 status |
|---|---|---|
| reference_id | Stable candidate ID for a future standard cost item reference row | Not generated |
| source_type | Source category, e.g. `provincial_quota_pdf` | Planned |
| source_name | Human-readable source name | Planned |
| source_file | Source PDF filename | Planned |
| source_file_hash | SHA256 hash of source PDF | Planned |
| source_page | PDF physical page number, 1-based | Planned |
| chapter_code | Chapter code, e.g. `A.1.1` | Planned |
| chapter_name | Chapter name, e.g. `土石方工程` | Planned |
| section_code | Section code, e.g. `A.1.1.1` | Planned |
| section_name | Section name, e.g. `土方工程` | Planned |
| item_group_name | Table/group heading around quota items | Stage 2 |
| source_code | Quota item number such as `A1-1-1`; not resource code | Stage 2 only |
| standard_name_candidate | Candidate name derived from PDF text; not final enterprise standard name | Stage 2 only |
| unit | Unit extracted from table or context | Stage 2 only |
| work_content | Work content text associated with the table/group | Stage 2 only |
| keywords | Search/matching keywords generated from candidate text | Stage 2/3 |
| aliases | Optional common alternate expressions | Stage 3 |
| feature_template | Optional structured feature template for review | Stage 3 |
| extraction_confidence | Extraction confidence for the candidate row | Stage 2/3 |
| review_status | Must default to `pending` for candidates | Stage 2/3 |
| reviewer | Human reviewer name | Empty until review |
| remark | Extraction notes, parse issues, or review guidance | Stage 2/3 |

## Required Later Controls

- PDF names are reference candidates only, never final approved enterprise `standard_name` values.
- Every candidate must preserve `source_file`, `source_file_hash`, and `source_page`.
- `review_status` must remain `pending` until human review.
- `internal_price_library` must not be generated directly from PDF extraction.
