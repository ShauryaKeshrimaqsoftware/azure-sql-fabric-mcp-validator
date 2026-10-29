# Azure SQL–Fabric Lakehouse Schema Comparison

## Comparison scope

| Field | Azure SQL source | Fabric Lakehouse target |
|---|---|---|
| System | Azure SQL Database | Microsoft Fabric Lakehouse |
| Database / Workspace | SalesDb | Sales Analytics |
| Schema / Namespace | dbo | dbo |
| Table / Lakehouse | Customers | CuratedLakehouse / Customers |
| Metadata retrieved | 2026-10-29T08:00:00Z | 2026-10-29T08:02:00Z |

## Summary

| Metric | Count |
|---|---:|
| Azure SQL columns | 4 |
| Fabric columns | 5 |
| Match | 1 |
| Compatible | 0 |
| Mismatch | 3 |
| Missing In Fabric | 0 |
| Extra In Fabric | 1 |
| Unknown | 0 |
| Column order differences (informational) | 1 |
| **Overall status** | **DIFFERENCES FOUND** |

## Column-by-column comparison

| Column | Azure SQL type | Fabric type | Nullability | Length / precision / scale | Status | Details |
|---|---|---|---|---|---|---|
| CountryCode | — | string | NOT COMPARABLE | NOT COMPARABLE | EXTRA IN FABRIC | Column exists only in Fabric. |
| CreatedAt | datetime2 | timestamp | False / False | scale 7 vs 6 | MISMATCH | Date/time types map to a timestamp family; inspect precision/time semantics. Scale differs: Azure SQL=7, Fabric=6. |
| CreditLimit | decimal | decimal | True / True | precision 18 vs 10 | MISMATCH | Normalized data type names match. Precision differs: Azure SQL=18, Fabric=10. |
| CustomerId | int | int | False / False | No comparable length/precision/scale difference detected. | MATCH | Normalized data type names match. |
| CustomerName | varchar | string | False / True | Azure SQL length limit 100 is not exposed/enforced by Fabric metadata | MISMATCH | Compatible string representation; a source length limit may not be enforced by Fabric string. Nullable differs: Azure SQL=False, Fabric=True. |

## Missing and additional columns

### Columns removed in Fabric (Present in Azure SQL only / Missing in Fabric)

No columns removed in Fabric (all Azure SQL columns exist in Fabric).

### Columns present only in Fabric (Added in Fabric / Extra in Fabric)

| Column | Fabric type | Status | Details |
|---|---|---|---|
| CountryCode | string | EXTRA IN FABRIC | Column exists only in Fabric. |

## Column order differences

| Column | Azure SQL position | Fabric position |
|---|---:|---:|
| CreatedAt | 4 | 5 |

## Keys and constraints

| Property | Azure SQL | Fabric | Result | Notes |
|---|---|---|---|---|
| Primary key | ["CustomerId"] | NOT AVAILABLE | NOT AVAILABLE | One or both endpoints did not provide this metadata. |
| Foreign keys | [] | NOT AVAILABLE | NOT AVAILABLE | One or both endpoints did not provide this metadata. |

## Warnings and limitations

- This is a metadata comparison, not a row-data comparison.
- Type-family compatibility is not proof of lossless conversion.
- If type, nullability, length, precision, scale or key metadata was unavailable, results are partial.

## Suggested interpretation

- `MATCH`: retrieved comparable schema properties match.
- `COMPATIBLE`: different type representations are mapped to a known family; review caveats.
- `MISMATCH`: a substantive schema property differs.
- `MISSING IN FABRIC` / `EXTRA IN FABRIC`: the column exists on one side only.
- `UNKNOWN` / `NOT AVAILABLE`: metadata was insufficient.
- Overall `INCOMPLETE`: required metadata could not be reliably retrieved.
