# Azure SQL–Fabric Lakehouse Schema Comparison

## 1. Comparison scope

| Field | Azure SQL source | Fabric Lakehouse target |
|---|---|---|
| System | {{azure_system}} | {{fabric_system}} |
| Database / Workspace | {{azure_database}} | {{fabric_workspace}} |
| Schema / Namespace | {{azure_schema}} | {{fabric_namespace}} |
| Table | {{azure_table}} | {{fabric_table}} |
| Metadata retrieved | {{azure_retrieved_at}} | {{fabric_retrieved_at}} |

## 2. Summary

| Metric | Count |
|---|---:|
| Azure SQL columns | {{azure_column_count}} |
| Fabric columns | {{fabric_column_count}} |
| Exact matches | {{match_count}} |
| Compatible type mappings | {{compatible_count}} |
| Schema mismatches | {{mismatch_count}} |
| Missing in Fabric | {{missing_in_fabric_count}} |
| Extra in Fabric | {{extra_in_fabric_count}} |
| Unknown / not available | {{unknown_count}} |
| Informational order differences | {{order_difference_count}} |
| **Overall status** | **{{overall_status}}** |

## 3. Column-by-column comparison

| Column | Azure SQL type | Fabric type | Nullability | Length / precision / scale | Status | Details |
|---|---|---|---|---|---|---|
| {{column_name}} | {{azure_type}} | {{fabric_type}} | {{nullability}} | {{attributes}} | {{status}} | {{details}} |

## 4. Missing and additional columns

| Column | Finding | Details |
|---|---|---|
| {{column_name}} | {{finding}} | {{details}} |

## 5. Keys and constraints

| Property | Azure SQL | Fabric | Result | Notes |
|---|---|---|---|---|
| Primary key | {{azure_pk}} | {{fabric_pk}} | {{pk_status}} | {{pk_notes}} |
| Foreign keys | {{azure_fk}} | {{fabric_fk}} | {{fk_status}} | {{fk_notes}} |

If either side does not expose key metadata, state `NOT AVAILABLE`; do not infer absence.

## 6. Warnings and limitations

| Issue | Impact / next step |
|---|---|
| {{issue}} | {{next_step}} |

## 7. Recommended follow-up

| Priority | Finding | Recommended action |
|---|---|---|
| {{priority}} | {{finding}} | {{action}} |

## Result interpretation

- `MATCH`: metadata is sufficient and the checked schema properties match.
- `COMPATIBLE`: different representations are mapped to a known broad type family; review listed caveats.
- `MISMATCH`: schema properties differ in a potentially substantive way.
- `MISSING IN FABRIC`: a source column has no target counterpart.
- `EXTRA IN FABRIC`: a target column has no source counterpart.
- `UNKNOWN` / `NOT AVAILABLE`: evidence is insufficient to classify that property.
- Overall `INCOMPLETE`: either endpoint's required schema metadata could not be retrieved.
