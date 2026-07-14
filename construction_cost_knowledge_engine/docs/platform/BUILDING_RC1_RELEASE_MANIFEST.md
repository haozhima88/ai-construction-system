# Building RC1 Release Manifest

Generated: `2026-07-13T13:49:50+08:00`  
Status: `platform_architecture_ready_for_database_implementation`

## Frozen Product Slices

| Slice | Identifier | Role |
|---|---|---|
| Reference | `BUILDING_A01_A03_REFERENCE_RC1` | Immutable GB/T 50854 bill baseline plus GD2018 A01/A02/A03 quota reference |
| Mapping | `BUILDING_A01_A03_MAPPING_RC1` | Immutable candidate mapping release; no approved semantics |
| Web | `WEB_REVIEW_RC1` | Reviewed UI/API source slice; Draft remains an external mutable overlay |

## Aggregate Hashes

| Hash group | SHA256 |
|---|---|
| Source | `508cfd3cd0d9443bf5bcaa9fc4656bdd029dc7b2919c7d1187f1b7b4e5706eba` |
| Parsed baseline | `6e8a335aa591b17bed156ee2a7dd26977c5cdb4a93350340092c049413bdbdc0` |
| Consolidated baseline | `c60ede039259a21884492a8f60d93a3e4c80bd238425e27260e40f817d5746b2` |
| Mapping reference | `8c537804f802529fd49c06b3f2222851fdd4fb8b39c482b53bd6f5ea79263af4` |
| Web main files | `6cbf4a22355a4681f9e9d90d106101a8000a8d584a89ae1ea68dab47b3aee19a` |

## Counts

- bill items: `472`
- context rules: `161`
- quota items: `3700`
- quota resources: `24981`
- mapping edges: `1882`
- current Draft/Audit/Review observations: `6/7/0`
- approved_count: `0`

## Versions

- parser provenance: `stageB_docx_extract_gb50854_full@8f83878e2e10;stage_gd2018_building_a01_full_parse@2f3508393196;stage_gd2018_building_volume_full_parse@3b549b589cc3;stage_gd2018_building_a01_a03_consolidated@0efa8d317a7b;stage_map_gb50854_to_gd2018_building_a_full@eea07c27af75`
- Web version: `WEB_REVIEW_RC1;ui=V0.1;readonly_schema=quota_building_readonly_v1`
- database schema: `quota_building_readonly_v1_prototype_only` (not the target PostgreSQL schema)
- Docker image: `not_built`
- Enterprise Price Release: `not_created`
- Enterprise Quota Release: `not_created`

The detailed file-level evidence is in `building_rc1_release_manifest.csv`. The mutable Draft database is observed for counts only and is not part of the immutable RC payload.
