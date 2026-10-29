# MCP Metadata Retrieval and Snapshot Contract

## Azure SQL through DAB MCP

1. Inspect the connected DAB MCP tool list; use its actual tool names and schemas.
2. `describe_entities` can help identify configured entities and exposed field names, but Microsoft documents that its response does not include types or primary-key indicators.
3. If available, use an already configured read-only view/entity or read-only stored procedure that returns metadata from `INFORMATION_SCHEMA.COLUMNS` and `sys` catalog views. Expose only the required metadata columns and restrict it to permitted schemas/tables.
4. Do not use create/update/delete tools. Do not create the view/procedure yourself, or execute DDL, as part of a schema comparison.
5. If type/nullability/length/precision/scale cannot be retrieved through current DAB tools, report that the Azure SQL metadata is incomplete and request an approved metadata surface.

An optional example read-only view definition is in `metadata-support/azure-sql-column-metadata-view.example.sql` at the package root. A DBA must review and deploy it. The DAB configuration must also expose the view to this agent with read-only permissions. The example is not automatically deployed and may require organization-specific security review.

## Fabric through Microsoft Fabric MCP

Discover the installed Fabric MCP tools first. Depending on version and configuration, OneLake tools may include operations to list workspaces/items, list table namespaces, list tables and retrieve a table definition. Use those live authenticated tools, not documentation-only tools, to retrieve the target Lakehouse's actual definition.

The table-definition response is the source of the column schema. If that response lacks a field needed for comparison, mark it unavailable rather than infer it. Table namespaces may be called schemas in the report; preserve the exact name returned by Fabric.

## Canonical normalized JSON

Create one file for each side with this shape:

```json
{
  "system": "Azure SQL",
  "database": "SalesDb",
  "schema": "dbo",
  "table": "Customers",
  "retrieved_at": "2026-10-29T10:00:00Z",
  "columns": [
    {
      "name": "CustomerId",
      "data_type": "int",
      "nullable": false,
      "max_length": null,
      "precision": 10,
      "scale": 0,
      "ordinal_position": 1
    }
  ],
  "primary_key": ["CustomerId"],
  "foreign_keys": []
}
```

`columns` is required. Every item requires `name` and `data_type`. Optional properties may be absent or null if unavailable. `primary_key`/`foreign_keys` have three states:

- Array (including `[]`): metadata was retrieved; contents are known.
- `null` or omitted: metadata was not available.

Don't include connection strings, tokens, credentials, row data or sensitive values. Store only metadata needed for comparison.

## Failure states

- **MCP unavailable:** stop and report which MCP server is unreachable.
- **Table not found:** show discovered candidates and ask user to choose, if any.
- **Metadata incomplete:** continue only with explicitly partial results and overall status `INCOMPLETE`.
- **Permission denied:** ask for an administrator-approved read-only metadata surface; never attempt privilege escalation.
