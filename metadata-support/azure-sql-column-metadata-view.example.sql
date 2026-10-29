/*
OPTIONAL EXAMPLE ONLY — DBA REVIEW REQUIRED.
This view returns column metadata only; it does not read user table rows.
Deploy it only after security review. It must then be exposed through DAB as a
read-only entity. Do not run this file from the agent. Do not grant broad access
without considering metadata visibility, schema filtering and tenant policy.
*/
CREATE OR ALTER VIEW dbo.vw_AgentSchemaColumnMetadata
AS
SELECT
    s.name AS table_schema,
    t.name AS table_name,
    c.name AS column_name,
    c.column_id AS ordinal_position,
    ty.name AS data_type,
    c.max_length AS max_length_bytes,
    CASE
        WHEN ty.name IN ('nvarchar', 'nchar') AND c.max_length > 0 THEN c.max_length / 2
        WHEN ty.name IN ('varchar', 'char') AND c.max_length > 0 THEN c.max_length
        ELSE NULL
    END AS character_maximum_length,
    c.precision AS [precision],
    c.scale,
    CONVERT(bit, c.is_nullable) AS is_nullable,
    CONVERT(bit, c.is_identity) AS is_identity,
    CONVERT(bit, c.is_computed) AS is_computed,
    CONVERT(bit, c.is_rowguidcol) AS is_rowguidcol,
    CONVERT(bit, CASE WHEN c.system_type_id = 189 THEN 1 ELSE 0 END) AS is_rowversion,
    CONVERT(bit, CASE WHEN pk.column_id IS NOT NULL THEN 1 ELSE 0 END) AS is_primary_key,
    pk.key_ordinal AS primary_key_ordinal
FROM sys.tables AS t
JOIN sys.schemas AS s ON s.schema_id = t.schema_id
JOIN sys.columns AS c ON c.object_id = t.object_id
JOIN sys.types AS ty ON ty.user_type_id = c.user_type_id
LEFT JOIN (
    SELECT ic.object_id, ic.column_id, ic.key_ordinal
    FROM sys.indexes AS i
    JOIN sys.index_columns AS ic
      ON ic.object_id = i.object_id AND ic.index_id = i.index_id
    WHERE i.is_primary_key = 1
) AS pk ON pk.object_id = c.object_id AND pk.column_id = c.column_id;
GO
-- After DBA approval, configure this view as a read-only DAB entity.
-- The agent should filter on table_schema and table_name; never enumerate metadata
-- the caller is not authorized to see.
