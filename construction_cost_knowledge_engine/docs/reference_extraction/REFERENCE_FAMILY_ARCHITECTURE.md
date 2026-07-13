# Reference Family Architecture

Stage: `REFERENCE_FAMILY_FRAMEWORK_LOCK_1`

This document locks the source-family framework for national standards and GD2018 quota references. It establishes routing, six-layer data contracts, and the downstream entry plan. It does not parse A01/A02/A03 full data, does not execute Mapping, and does not modify Web business pages.

## Source Inventory

- National standard directory files: 4
- Current GB/T 50854 baseline file outside the national directory: 1
- GD2018 quota source files: 27
- Source/Baseline/Web mutation in this stage: no

## Standard Families

| family_id | family_type | standard_code | document_count | mapped_national_standard | routing_status |
| --- | --- | --- | --- | --- | --- |
| GB_BILL_BUILDING_DECORATION_2024 | national_bill_standard | GB/T 50854-2024 | 2 | self | ready |
| GB_BILL_INSTALLATION_2024 | national_bill_standard | GB/T 50856-2024 | 1 | self | ready |
| GB_BILL_MUNICIPAL_2024 | national_bill_standard | GB/T 50857-2024 | 1 | self | ready |
| GB_BILL_LANDSCAPE_2024 | national_bill_standard | GB/T 50858-2024 | 1 | self | ready |
| GD2018_A_BUILDING_DECORATION | provincial_quota_family | GD2018-A | 3 | GB/T 50854-2024 | locked |
| GD2018_A04_MACHINE_SHIFT_FEE_BASIS | provincial_fee_basis | GD2018-A04 | 1 | machine_shift_fee_basis | locked |
| GD2018_C_INSTALLATION | provincial_quota_family | GD2018-C | 15 | GB/T 50856-2024 | locked |
| GD2018_D_MUNICIPAL | provincial_quota_family | GD2018-D | 7 | GB/T 50857-2024 | locked |
| GD2018_E_LANDSCAPE | provincial_quota_family | GD2018-E | 1 | GB/T 50858-2024 | locked |

## Routing Matrix

| source_family | source_volume_pattern | target_standard_code | mapping_target_type | route_status | downstream_entry |
| --- | --- | --- | --- | --- | --- |
| GD2018_A_BUILDING_DECORATION | A01; A02; A03 | GB/T 50854-2024 | ordinary_bill_mapping | locked | GD2018_BUILDING_A_FULL_PARSE_1 -> MAP_GB50854_TO_GD2018_BUILDING_1 |
| GD2018_A04_MACHINE_SHIFT_FEE_BASIS | A04 | not ordinary bill standard | fee_basis_only | locked_out_of_ordinary_bill_mapping | Use only as fee/resource basis after quota parse governance is complete. |
| GD2018_C_INSTALLATION | C.* | GB/T 50856-2024 | ordinary_bill_mapping | locked | future installation family parse and mapping stage |
| GD2018_D_MUNICIPAL | D.* | GB/T 50857-2024 | ordinary_bill_mapping | locked | future municipal family parse and mapping stage |
| GD2018_E_LANDSCAPE | E | GB/T 50858-2024 | ordinary_bill_mapping | locked | future landscape family parse and mapping stage |

Routing lock:

- GD2018 A01/A02/A03 route to GB/T 50854-2024.
- GD2018 A series does not route to GB/T 50856-2024.
- GD2018 C series routes to GB/T 50856-2024.
- GD2018 D series routes to GB/T 50857-2024.
- GD2018 E routes to GB/T 50858-2024.
- GD2018 A04 is machine shift / fee basis and is outside ordinary bill mapping.

## Data Layer Contracts

| layer_id | layer_name | mutable | write_allowed | allowed_operations | forbidden_operations |
| --- | --- | --- | --- | --- | --- |
| L0 | Source Registry | no | framework scan may append new source registry rows only; no source file mutation | scan; checksum; page count; text-layer profiling; route registration | edit source PDFs/DOCX; normalize prices; parse full A01/A02/A03 quota tables |
| L1 | Evidence Baseline | no | new baseline run creates new immutable artifacts; Web writes are not allowed | read; cite; validate hash; derive immutable evidence in new run folders | overwrite baseline rows; back-write review decisions; write enterprise price or formal enterprise quota |
| L2 | Parsed Reference | controlled append only | parser stages may create new candidate runs; existing Source/Baseline cannot be edited | parse candidate; normalize codes; attach evidence; raise parse issues | mark final mapping; produce enterprise price library; write Web draft tables |
| L3 | Mapping Reference | controlled append only | mapping stages may create candidate artifacts in new private run folders | rank candidates; record confidence; emit issues; preserve all candidate status as pending | write to source candidate; overwrite baseline; turn Web draft action into canonical mapping without governed promotion |
| L4 | Review Draft | yes | Copy / Move / Exclude / Restore only; every write must audit | copy_link; move_link; exclude_link; restore_original; export draft; export audit | back-write source candidate; mutate L0/L1/L2/L3; create enterprise formal quota |
| L5 | Web Collaboration | limited | only Review Draft and Audit tables; no writes to Source Candidate | read tree/detail APIs; create draft edge action; audit export; smoke validation | write Source/Baseline/Parsed/Mapping Candidate; alter business pages in this stage |

Layer lock:

- L0 Source Registry and L1 Evidence Baseline are immutable.
- L2 Parsed Reference and L3 Mapping Reference are candidate/append-only until governed promotion.
- L4 Review Draft allows Copy, Move, Exclude, and Restore only, with audit.
- L5 Web Collaboration writes only Review Draft and Audit tables; Web drafts must not write back to Source Candidate.
- Enterprise price and formal enterprise quota are out of scope.

## A1.1 Golden Slice

| slice_id | quota_count | resource_count | rule_block_count | scope_link_count | mapping_relation_count | page_route | current_draft_count | current_audit_count | approved_count | registration_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GOLDEN_SLICE_GD2018_A111_V1 | 137 | 629 | 33 | 33 | 194 | /quota-a111 | 6 | 10 | 0 | registered_existing_golden_slice_no_mutation |

## Downstream Entry

The next execution entry for building/decorating is `GD2018_BUILDING_A_FULL_PARSE_1`, followed by `MAP_GB50854_TO_GD2018_BUILDING_1`, then `WEB_QUOTA_BUILDING_PROTOTYPE_1`. These stages are documented as plan only here.
