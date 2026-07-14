# Standard Family Adapter Specification

## Purpose

A Family Adapter converts one standard family's source shape into the canonical Reference contract without changing domain rules. Adapter output remains candidate data until packaged in a validated Reference Release.

## Required Contract

| Section | Responsibility |
|---|---|
| `source_profile` | document roles, authority rules, editions, file types, hash policy, text/OCR capability, evidence locator policy |
| `code_pattern` | family/volume code grammar, normalization, validation, uniqueness, and reserved patterns |
| `table_recognizer` | headings, table signatures, continuation/merged-cell behavior, row boundaries, confidence, reject policy |
| `resource_category_profile` | labor/material/machine/other taxonomy, aliases, unit policy, code rules |
| `professional_extension` | profession-specific fields, rules, evidence, and UI labels without altering canonical core |
| `mapping_target` | compatible bill/quota families, edition constraints, routing classes, unit/semantic profiles |
| `web_display_profile` | read-only labels, columns, grouping, evidence views, filters, and fallback display behavior |

## Adapter Interface

An adapter package declares:

- stable `adapter_id`, semantic version, supported source editions, and parser implementation hash;
- JSON-schema-like input/output contracts and deterministic normalization rules;
- source role registry and `official_pdf_wins` or family-specific authority conflict rule;
- evidence completeness levels and explicit `pending_evidence_link` handling;
- diagnostics with severity, source locator, candidate ID, and no silent row invention;
- fixture/golden slices, expected counts/ranges, duplicate/orphan/code checks, and regression hashes;
- migration notes for canonical schema extensions and Web display compatibility.

Core domain fields cannot be redefined by an adapter. Profession-specific fields live in namespaced extension payloads until promoted through schema governance.

## Planned Families

| Future slice | Reference pairing | Adapter note |
|---|---|---|
| A04 | GD2018 construction machinery cost rules | price/resource support family; no parse in this stage |
| C | GD2018 installation + GB/T 50856 | multiple volumes and installation resource categories |
| D | GD2018 municipal + GB/T 50857 | municipal chapter/code and measure rules |
| E | GD2018 landscape + GB/T 50858 | landscape-specific resources and units |

Each slice receives its own source profile, run, integrity gate, Reference Release, Mapping Release, and release manifest. It does not append unversioned rows to Building RC1.

## Acceptance Gate

An adapter is eligible for a parse stage only after source authority roles, code grammar, table/evidence strategy, canonical field mapping, issue taxonomy, golden fixtures, protected-input hash guard, output run naming, and no-approval policy pass architecture review.

No A04, C, D, or E source is parsed in this architecture stage.

