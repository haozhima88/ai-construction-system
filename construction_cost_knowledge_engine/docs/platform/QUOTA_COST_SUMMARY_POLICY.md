# Quota Cost Summary Policy

## Resource Amount

Amounts use Python `Decimal`; binary floating-point arithmetic and intermediate rounding are prohibited.

For every resource row:

1. Preserve `source_component_amount` from the provincial reference source.
2. If the source amount is blank and both consumption and unit price exist, calculate `calculated_component_amount = consumption * unit_price`.
3. `display_component_amount` uses the source amount first, then the calculated fallback.
4. If neither value exists, keep the display amount blank. Never fill a missing amount with zero.
5. Display rounding is two decimals only. The underlying value is not rounded or written back.

`amount_source` is one of `source`, `calculated_fallback`, or `unavailable`.

## Category And Totals

The service returns labor, material, machine, other, and resource totals for both source-only values and display/calculated values. Resource code `99450760` with the other-material-fee name is classified as `other` and carries an explicit category reason.

The reconciliation equation is:

`resource_calculated_total + management_fee - provincial_base_price = reconciliation_delta`

Allowed statuses are `matched`, `rounding_only`, `category_boundary_explained`, `unpriced_material_excluded`, `partial_resource_rows_missing`, `source_blank_preserved`, and `mismatch_requires_review`.

No status changes the source. A mismatch is review evidence, not an instruction to overwrite provincial data.

