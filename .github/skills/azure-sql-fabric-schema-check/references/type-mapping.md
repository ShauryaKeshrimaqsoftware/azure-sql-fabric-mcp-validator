# Type Mapping and Comparison Rules

The goal is to classify differences conservatively. A type-family mapping is a review aid, not a guarantee of lossless conversion.

## General rules

- Normalize case and insignificant spaces for type names.
- Exact same normalized type and comparable attributes => `MATCH`.
- Supported different type names in a known compatible family => `COMPATIBLE`, with explanation.
- Incompatible known families => `MISMATCH`.
- Missing/extra column => `MISSING IN FABRIC` / `EXTRA IN FABRIC`.
- If required metadata is absent, use `UNKNOWN` or `NOT AVAILABLE`; never call it a match.
- For decimal/numeric compare precision and scale when both sides expose them. If precision/scale is unverified on one side, mark as `UNKNOWN`.
- For string/binary types, compare max lengths when both sides report meaningful limits.
  - If Azure SQL has a bounded type and Fabric exposes unbounded `string`, report compatibility and note that the bound may not be enforced on Fabric.
  - If Azure SQL has an unbounded type and Fabric enforces a strict length bound, report `MISMATCH`.
  - For SQL Server `nvarchar`/`nchar`, byte length from `sys.columns` is normalized to character count ($bytes / 2$) before comparison.
- Nullability mismatch is a substantive difference if both values are known.
- Column-order changes are informational only by default.
- Compare primary/foreign keys only when both systems expose reliable metadata. Missing key metadata is not the same as known absence of keys. If composite key columns match but ordinals differ, mark `COMPATIBLE` rather than `MISMATCH`.

## Supported broad families

See `config/type-mapping.json`. Supported type pairings include:
- `bit` $\leftrightarrow$ `boolean`
- `bigint` $\leftrightarrow$ `long` / `bigint`
- `int` / `integer` $\leftrightarrow$ `int` / `integer`
- `smallint` $\leftrightarrow$ `short` / `smallint`
- `tinyint` $\rightarrow$ `short` / `int` (safely widened unsigned integer)
- `float` (SQL 64-bit) $\leftrightarrow$ `double` (Fabric 64-bit)
- `real` (SQL 32-bit) $\leftrightarrow$ `float` (Fabric 32-bit)
- `decimal` / `numeric` / `money` / `smallmoney` $\leftrightarrow$ `decimal` / `numeric`
- `varchar` / `nvarchar` / `char` / `nchar` / `text` / `xml` $\leftrightarrow$ `string` / `varchar`
- `uniqueidentifier` $\rightarrow$ `string` / `varchar` (string GUID representation)
- `date` $\leftrightarrow$ `date`
- `datetime` / `datetime2` / `smalldatetime` $\leftrightarrow$ `timestamp` / `datetime2`
- `time` $\leftrightarrow$ `time`
- `binary` / `varbinary` / `image` $\leftrightarrow$ `binary` / `varbinary`
- `geography` / `geometry` / `hierarchyid` $\rightarrow$ `string` / `binary`

## Important caveats

- **SQL Server `float` vs Fabric `float`**: SQL Server `float` defaults to 64-bit IEEE double precision, whereas Fabric/Spark `float` is 32-bit single precision. Flagged as `COMPATIBLE_WITH_PRECISION_CAVEAT`.
- **SQL Server `tinyint` vs Spark `byte`**: Unsigned SQL `tinyint` (0–255) has a different numeric range from signed Spark `byte` (-128–127); explicitly marked as `MISMATCH`. Widening to `short` or `int` is `COMPATIBLE`.
- **SQL Server `timestamp` / `rowversion`**: Not a date/time type; it is an internal binary version counter. Explicitly marked as `MISMATCH` if compared against a Fabric `timestamp`.
- **SQL Server `datetimeoffset`**: Contains timezone-offset semantics that a basic Fabric `timestamp` may not preserve.
- **`uniqueidentifier` to Fabric `string`**: Compatible as a text representation but loses native GUID typing.
- **Decimal precision or scale reduction**: May cause rounding/overflow risks.
- Metadata source and version should be included in report provenance.
