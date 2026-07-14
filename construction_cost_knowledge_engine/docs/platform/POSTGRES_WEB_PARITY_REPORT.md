# PostgreSQL Web Parity Report

## Result

The PostgreSQL review backend preserves the RC1 entity surface: 472 bills, 3700 quotas, 24981 resource rows, and 1882 candidate Mapping edges. The six legacy SQLite Draft rows and seven Audit rows are present in PostgreSQL with exact legacy Draft/Audit keys. SQLite remains frozen and read-only.

The workbench reads Candidate Mapping and reference entities without modification and writes only tenant Draft/Review/Audit overlays. `approved_count` remains zero.

## Behavioral Parity

- Bill tree, detail, Mapping overlay, quota detail, structured rules, evidence, and PDF endpoints are available.
- Copy, Move, Exclude, Restore, and Review state use PostgreSQL transactions, CSRF, RBAC, row versions, and idempotency.
- Viewer, editor, reviewer, approver, and administrator policies match the locked RBAC catalog.
- Resource amount source priority, blank preservation, Decimal arithmetic, and cost reconciliation are explicit.
- A01, A02, and A03 PDF previews pass desktop and mobile ResizeObserver checks.
- The SQLite fallback has no write route.

## Known Review Evidence

Cost reconciliation status is evidence rather than source correction. Rows classified as unpriced, rounding-only, category-explained, or mismatch remain unchanged and are surfaced for cost-engineer review. NAS HTTPS and secure-cookie deployment remain outside this local stage.
