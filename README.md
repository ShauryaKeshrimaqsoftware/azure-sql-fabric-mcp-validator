# Azure SQL–Fabric Lakehouse Schema Validation Agent

A standalone GitHub Copilot custom agent and Agent Skill that compares the schema of one Azure SQL Database table with one Microsoft Fabric Lakehouse table. It asks for missing location details, retrieves metadata through the configured MCP servers, compares the returned metadata deterministically, and displays the findings as Markdown tables in Copilot Chat.

## What it checks

- Columns missing from either side or present only on one side
- Data types and conservative type compatibility
- Nullability
- Length, precision and scale when both systems expose comparable values
- Column order as informational only
- Primary/foreign-key metadata only when both sides expose reliable key metadata

It is read-only. It does not compare row contents, validate data values, or alter the databases.

## Standalone folder

Open this folder itself in VS Code (the folder that directly contains `.github/`). Its agent and skill are separate from any other Power BI skills.

```text
azure-sql-fabric-schema-validator/
├── .github/
│   ├── agents/azure-sql-fabric-schema-validator.agent.md
│   └── skills/azure-sql-fabric-schema-check/
│       ├── SKILL.md
│       ├── scripts/compare_schemas.py
│       ├── references/mcp-metadata-retrieval.md
│       ├── references/type-mapping.md
│       ├── assets/schema-comparison-template.md
│       ├── config/type-mapping.json
│       └── tests/
├── examples/
├── metadata-support/
└── README.md
```

## Prerequisites

1. VS Code with GitHub Copilot Chat supporting custom agents and Agent Skills.
2. The Azure SQL Data API Builder (DAB) SQL MCP server connected and authenticated to the correct database.
3. The Microsoft Fabric MCP server connected and authenticated to the correct tenant/workspace.
4. Read-only permission to inspect metadata for the selected Azure SQL table and Fabric Lakehouse table.
5. Python 3.10+ to run the deterministic comparison script and tests. The script uses only the Python standard library.

### Important Azure SQL MCP metadata caveat

DAB's built-in `describe_entities` tool describes configured entities and field names, but Microsoft documents that its response does not include data types or primary-key indicators. The agent must inspect the actual tools available in your installation. If those tools cannot provide the required schema metadata, expose an approved, read-only metadata view/entity (or a read-only stored procedure) through DAB. An example SQL view is included in `metadata-support/azure-sql-column-metadata-view.example.sql`; a database administrator must review and deploy it, then expose it through DAB. Do not assume it is already installed.

The Fabric MCP server's live OneLake tools can discover workspaces, items, table namespaces, tables, and table definitions. Tool names and availability vary by installed version, so the agent is instructed to inspect the available tool catalog and use actual tool names rather than guessing.

## Run it in Copilot Chat

1. Open this standalone folder in VS Code.
2. Open Copilot Chat and select **Azure SQL–Fabric Schema Validator** in the agent picker (or invoke `/azure-sql-fabric-schema-check` in Agent mode).
3. Start with a simple request, for example:

   > Compare Azure SQL table `dbo.Customers` with the `Customers` table in my Fabric Lakehouse.

4. The agent asks only for missing details, such as Azure SQL database, Fabric workspace, Lakehouse, and namespace/schema.
5. Review the resolved locations. The agent retrieves schema metadata through the connected MCP servers using read-only operations.
6. It normalizes the metadata into the documented JSON contract, runs `compare_schemas.py`, and shows the comparison tables directly in Copilot Chat.
7. The script also saves `schema_comparison.md` and `schema_comparison.json` under `schema-comparison-results/` by default, unless another output directory is chosen.

## Run the local comparison script directly

The agent normally creates the two metadata JSON files from MCP responses. The expected shape is documented in `references/mcp-metadata-retrieval.md` and demonstrated in `examples/`.

```powershell
python .github/skills/azure-sql-fabric-schema-check/scripts/compare_schemas.py `
  --azure-sql-json examples/azure_sql_schema.example.json `
  --fabric-json examples/fabric_lakehouse_schema.example.json `
  --output-dir schema-comparison-results
```

The example files are synthetic fixtures only; don't confuse them with live table metadata.

## Run tests

```powershell
Push-Location .github/skills/azure-sql-fabric-schema-check
python -m unittest discover -s tests -v
Pop-Location
```

## Read-only and failure-handling rules

- The agent must not create, update, delete, refresh, or alter database objects or table data.
- Do not read table rows to infer schema. Retrieve metadata only.
- Do not run a DAB tool that writes or modifies data. Use a configured read-only metadata entity/procedure if needed.
- Never invent missing types, nullability, keys, precision, scale or lengths. Mark them `UNKNOWN`/`NOT AVAILABLE` and explain the limitation.
- If either MCP connection or metadata retrieval fails, stop the comparison and report the blocker rather than reporting a match.
- Type mappings are conservative. `COMPATIBLE` means the configured mapping says the two types can represent the same broad type family; it is not proof of data fidelity.
- Column order is informational and does not count as a blocking mismatch by default.

## Fixed output

See `assets/schema-comparison-template.md`. The agent must show these key tables in Copilot Chat itself:

1. Summary
2. Column-by-column comparison
3. Source-only and target-only columns
4. Key/constraint comparison (only when reliable metadata is available)
5. Warnings and limitations

## Microsoft references

- [SQL MCP Server overview](https://learn.microsoft.com/en-us/azure/data-api-builder/mcp/overview)
- [SQL MCP Server DML tools](https://learn.microsoft.com/en-us/azure/data-api-builder/mcp/data-manipulation-language-tools)
- [Microsoft Fabric MCP Server tools reference](https://learn.microsoft.com/en-us/rest/api/fabric/articles/mcp-servers/pro-dev-local/tools-local-mcp-server)
