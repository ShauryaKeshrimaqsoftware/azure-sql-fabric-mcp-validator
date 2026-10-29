#!/usr/bin/env python3
"""Compare normalized Azure SQL and Fabric Lakehouse table schema snapshots."""
from __future__ import annotations
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_MAPPING = Path(__file__).resolve().parents[1] / "config" / "type-mapping.json"


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read valid JSON from {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return data


def norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def boolish(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"true", "yes", "1", "nullable", "null"}:
            return True
        if v in {"false", "no", "0", "not nullable", "not null"}:
            return False
    return None


def intish(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def type_base(col: dict[str, Any]) -> str:
    raw = norm(col.get("data_type") or col.get("type"))
    # If metadata passes names like decimal(18,2), remove parameters for family lookup.
    return re.sub(r"\s*\([^)]*\)", "", raw).strip()


def hydrate_type_parameters(col: dict[str, Any]) -> dict[str, Any]:
    """Extract numeric and character type parameters when a metadata source encodes them in data_type."""
    raw = norm(col.get("data_type") or col.get("type"))
    match = re.fullmatch(r"(decimal|numeric)\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)", raw)
    if match:
        if col.get("precision") is None and col.get("numeric_precision") is None:
            col["precision"] = int(match.group(2))
        if col.get("scale") is None and col.get("numeric_scale") is None:
            col["scale"] = int(match.group(3))
    match = re.fullmatch(r"(varchar|nvarchar|char|nchar)\s*\(\s*(\d+)\s*\)", raw)
    if match and col.get("max_length") is None and col.get("character_maximum_length") is None:
        col["max_length"] = int(match.group(2))
    return col


def load_mapping(path: Path) -> dict[str, Any]:
    data = load_json(path)
    rules = data.get("rules", [])
    if not isinstance(rules, list):
        raise ValueError("Type mapping JSON must contain a 'rules' array")
    return data


def find_rule(left_type: str, right_type: str, mapping: dict[str, Any], left_system: str, right_system: str) -> dict[str, Any] | None:
    left_sqlish = "sql" in norm(left_system) or "database" in norm(left_system)
    right_fabricish = "fabric" in norm(right_system) or "lakehouse" in norm(right_system)
    rules = mapping.get("rules", [])
    for rule in rules:
        lvalues = [norm(v) for v in rule.get("azure_sql", [])]
        rvalues = [norm(v) for v in rule.get("fabric", [])]
        if left_sqlish and right_fabricish:
            if left_type in lvalues and right_type in rvalues:
                return rule
        elif not left_sqlish and not right_fabricish:
            if left_type in lvalues and right_type in rvalues:
                return rule
        else:
            if left_type in lvalues and right_type in rvalues:
                return rule
            if left_type in rvalues and right_type in lvalues:
                return {**rule, "_reversed": True}
    return None


def family_for(col: dict[str, Any], system: str, mapping: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
    dt = type_base(col)
    sysnorm = norm(system)
    if "sql" in sysnorm or "database" in sysnorm:
        for r in mapping.get("rules", []):
            if dt in [norm(x) for x in r.get("azure_sql", [])]:
                return r.get("family"), r
    if "fabric" in sysnorm or "lakehouse" in sysnorm:
        for r in mapping.get("rules", []):
            if dt in [norm(x) for x in r.get("fabric", [])]:
                return r.get("family"), r
    # Exact known primitive fallback for samples or other named systems.
    fallback = {
        "bool": "boolean", "boolean": "boolean", "bit": "boolean",
        "tinyint": "sql_tinyint_unsigned", "byte": "spark_byte_signed",
        "smallint": "int16", "short": "int16", "int": "int32", "integer": "int32",
        "bigint": "int64", "long": "int64", "float": "float32", "real": "float32", "double": "float64",
        "decimal": "decimal", "numeric": "decimal", "string": "string", "varchar": "string", "nvarchar": "string", "char": "string", "nchar": "string", "text": "string", "ntext": "string",
        "date": "date", "time": "time", "timestamp": "timestamp", "datetime": "timestamp", "datetime2": "timestamp", "smalldatetime": "timestamp",
        "binary": "binary", "varbinary": "binary", "image": "binary", "uniqueidentifier": "guid", "rowversion": "rowversion",
        "money": "decimal", "smallmoney": "decimal", "xml": "xml_string"
    }
    return fallback.get(dt), None


def safe_column(col: Any, side: str, index: int) -> dict[str, Any]:
    if not isinstance(col, dict):
        raise ValueError(f"{side} column at index {index} is not a JSON object")
    name = str(col.get("name") or col.get("column_name") or "").strip()
    dtype = str(col.get("data_type") or col.get("type") or "").strip()
    if not name:
        raise ValueError(f"{side} column at index {index} has no name")
    if not dtype:
        dtype = "UNKNOWN"

    raw_char_len = col.get("character_maximum_length")
    raw_max_len = col.get("max_length")
    raw_max_bytes = col.get("max_length_bytes")
    max_len = None
    if raw_char_len is not None:
        max_len = intish(raw_char_len)
    elif raw_max_len is not None:
        max_len = intish(raw_max_len)
    elif raw_max_bytes is not None:
        max_len = intish(raw_max_bytes)

    normalized = {
        **col,
        "name": name,
        "data_type": dtype,
        "nullable": boolish(col.get("nullable", col.get("is_nullable"))),
        "max_length": max_len,
        "precision": intish(col.get("precision", col.get("numeric_precision"))),
        "scale": intish(col.get("scale", col.get("numeric_scale"))),
        "ordinal_position": intish(col.get("ordinal_position", col.get("ordinal"))),
    }
    normalized = hydrate_type_parameters(normalized)

    # In SQL Server, sys.columns stores max_length for nvarchar/nchar in bytes (2 bytes per character).
    # If character_maximum_length was not supplied and max_length is from byte metadata, normalize to char count.
    base_t = type_base(normalized)
    if "sql" in norm(side) and base_t in {"nvarchar", "nchar"} and raw_char_len is None:
        curr_len = normalized.get("max_length")
        if curr_len and curr_len > 0 and (raw_max_bytes is not None or (raw_max_len is not None and curr_len % 2 == 0 and not re.search(r"\(\s*\d+\s*\)", norm(dtype)))):
            normalized["max_length"] = curr_len // 2

    return normalized


def get_columns(snapshot: dict[str, Any], side: str) -> dict[str, dict[str, Any]]:
    raw = snapshot.get("columns")
    if not isinstance(raw, list):
        raise ValueError(f"{side} snapshot must contain a 'columns' array")
    result: dict[str, dict[str, Any]] = {}
    for i, item in enumerate(raw):
        col = safe_column(item, side, i)
        key = col["name"].casefold()
        if key in result:
            raise ValueError(f"{side} snapshot contains duplicate column name (case-insensitive): {col['name']}")
        result[key] = col
    return result


def comp_type(left: dict[str, Any], right: dict[str, Any], lsys: str, rsys: str, mapping: dict[str, Any]) -> tuple[str, str]:
    lt, rt = type_base(left), type_base(right)
    if not lt or lt == "unknown" or not rt or rt == "unknown":
        return "UNKNOWN", "A data type is missing from the retrieved metadata."

    left_sqlish = "sql" in norm(lsys) or "database" in norm(lsys)

    # 1. Check explicit not-equivalent mappings first
    for entry in mapping.get("explicitly_not_equivalent", []):
        esql = norm(entry.get("azure_sql"))
        efab = norm(entry.get("fabric"))
        reason = entry.get("reason", "Types are explicitly not equivalent.")
        if left_sqlish:
            if (lt == esql or (esql == "timestamp" and lt in {"timestamp", "rowversion"})) and rt == efab:
                return "MISMATCH", reason
        else:
            if (rt == esql or (esql == "timestamp" and rt in {"timestamp", "rowversion"})) and lt == efab:
                return "MISMATCH", reason

    # 2. SQL Server timestamp / rowversion check
    if ("sql" in norm(lsys) and lt in {"timestamp", "rowversion"}) or ("sql" in norm(rsys) and rt in {"timestamp", "rowversion"}):
        return "MISMATCH", "SQL Server timestamp may mean rowversion, not a date/time type; verify actual source semantics."

    # 3. Pair-wise rule matching
    rule = find_rule(lt, rt, mapping, lsys, rsys)
    if rule is not None:
        family = rule.get("family", "")
        if family == "float_precision_caveat":
            return "COMPATIBLE", "SQL Server float is 64-bit double precision, whereas Fabric float is 32-bit single precision; verify precision needs or use Fabric double."
        if lt == rt:
            return "MATCH", "Normalized data type names match."
        note = "Different type names map to the same configured type family."
        if family == "string":
            note = "Compatible string representation; a source length limit may not be enforced by Fabric string."
        elif family == "decimal":
            note = "Decimal/numeric types are comparable; inspect precision and scale below."
        elif family == "guid_string":
            note = "GUID is represented as a string; native GUID typing is not preserved."
        elif family == "timestamp":
            note = "Date/time types map to a timestamp family; inspect precision/time semantics."
        elif family == "int16_widened":
            note = "SQL unsigned tinyint (0-255) is safely widened to Fabric signed integer."
        elif family == "xml_string":
            note = "XML data is represented as string in Fabric."
        elif family == "spatial_string":
            note = "Spatial/geometry data is represented as string or binary in Fabric."
        elif family:
            note = f"Different type names map to the same configured type family ({family})."
        return "COMPATIBLE", note

    # 4. Same base type names without explicit rule
    if lt == rt:
        if lt == "float" and (("sql" in norm(lsys) and "fabric" in norm(rsys)) or ("sql" in norm(rsys) and "fabric" in norm(lsys))):
            return "COMPATIBLE", "SQL Server float is 64-bit double precision, whereas Fabric float is 32-bit single precision; verify precision needs or use Fabric double."
        return "MATCH", "Normalized data type names match."

    # 5. Fallback single-side family comparison
    lf, lr = family_for(left, lsys, mapping)
    rf, rr = family_for(right, rsys, mapping)
    if {lf, rf} == {"sql_tinyint_unsigned", "spark_byte_signed"}:
        return "MISMATCH", "SQL tinyint is unsigned; Spark byte is signed and has a different range."
    if "datetimeoffset" in {lt, rt}:
        return "MISMATCH", "Timezone-offset semantics may not be preserved by the other type."
    if lf and rf and lf == rf:
        note = "Different type names map to the same configured type family."
        if lf == "string":
            note = "Compatible string representation; a source length limit may not be enforced by Fabric string."
        elif lf == "decimal":
            note = "Decimal/numeric types are comparable; inspect precision and scale below."
        elif lf == "guid_string":
            note = "GUID is represented as a string; native GUID typing is not preserved."
        elif lf == "timestamp":
            note = "Date/time types map to a timestamp family; inspect precision/time semantics."
        return "COMPATIBLE", note

    return "MISMATCH", f"No supported compatibility mapping found for {left['data_type']} and {right['data_type']}."


def compare_keys(left: dict[str, Any], right: dict[str, Any], field: str, label: str) -> dict[str, Any]:
    lval, rval = left.get(field, None), right.get(field, None)
    if lval is None or rval is None:
        return {"property": label, "azure_sql": lval, "fabric": rval, "status": "NOT AVAILABLE", "details": "One or both endpoints did not provide this metadata."}
    if field == "primary_key":
        ll = [str(x).casefold() for x in lval] if isinstance(lval, list) else []
        rr = [str(x).casefold() for x in rval] if isinstance(rval, list) else []
        if ll == rr:
            return {"property": label, "azure_sql": lval, "fabric": rval, "status": "MATCH", "details": "Metadata agrees."}
        if sorted(ll) == sorted(rr):
            return {"property": label, "azure_sql": lval, "fabric": rval, "status": "COMPATIBLE", "details": f"Key columns match, but ordinal order differs between systems (Azure SQL: {', '.join(ll)} vs Fabric: {', '.join(rr)})."}
        return {"property": label, "azure_sql": lval, "fabric": rval, "status": "MISMATCH", "details": "Key metadata differs; review target constraints and platform capabilities."}
    else:
        ll = sorted(json.dumps(x, sort_keys=True, default=str) for x in lval) if isinstance(lval, list) else []
        rr = sorted(json.dumps(x, sort_keys=True, default=str) for x in rval) if isinstance(rval, list) else []
        same = ll == rr
        return {"property": label, "azure_sql": lval, "fabric": rval, "status": "MATCH" if same else "MISMATCH", "details": "Metadata agrees." if same else "Key metadata differs; review target constraints and platform capabilities."}


def compare_snapshots(left: dict[str, Any], right: dict[str, Any], mapping: dict[str, Any]) -> dict[str, Any]:
    lcols, rcols = get_columns(left, "Azure SQL"), get_columns(right, "Fabric")
    lsys = str(left.get("system", "Azure SQL"))
    rsys = str(right.get("system", "Microsoft Fabric Lakehouse"))
    details = []
    counts = {k: 0 for k in ["MATCH", "COMPATIBLE", "MISMATCH", "MISSING IN FABRIC", "EXTRA IN FABRIC", "UNKNOWN"]}
    order_diffs = []
    for key in sorted(lcols.keys() | rcols.keys()):
        lc, rc = lcols.get(key), rcols.get(key)
        if lc is None:
            details.append({"column": rc["name"], "azure_sql_type": "—", "fabric_type": rc["data_type"], "nullability": "NOT COMPARABLE", "attributes": "NOT COMPARABLE", "status": "EXTRA IN FABRIC", "details": "Column exists only in Fabric."})
            counts["EXTRA IN FABRIC"] += 1
            continue
        if rc is None:
            details.append({"column": lc["name"], "azure_sql_type": lc["data_type"], "fabric_type": "—", "nullability": "NOT COMPARABLE", "attributes": "NOT COMPARABLE", "status": "MISSING IN FABRIC", "details": "Column exists in Azure SQL but not in Fabric."})
            counts["MISSING IN FABRIC"] += 1
            continue
        typestatus, typedetails = comp_type(lc, rc, lsys, rsys, mapping)
        findings: list[tuple[str, str]] = [(typestatus, typedetails)]
        if lc["nullable"] is None or rc["nullable"] is None:
            findings.append(("UNKNOWN", "Nullability is unavailable on at least one side."))
        elif lc["nullable"] != rc["nullable"]:
            findings.append(("MISMATCH", f"Nullable differs: Azure SQL={lc['nullable']}, Fabric={rc['nullable']}."))

        attrnotes = []
        is_string_or_binary = any(t in {"string", "varchar", "nvarchar", "char", "nchar", "text", "ntext", "binary", "varbinary", "image"} for t in {type_base(lc), type_base(rc)})
        if is_string_or_binary:
            l_len = None if lc["max_length"] in (None, -1) else lc["max_length"]
            r_len = None if rc["max_length"] in (None, -1) else rc["max_length"]
            if l_len is not None and r_len is not None and l_len != r_len:
                findings.append(("MISMATCH", f"Maximum length differs: Azure SQL={l_len}, Fabric={r_len}."))
                attrnotes.append(f"max_length {l_len} vs {r_len}")
            elif l_len is not None and r_len is None:
                attrnotes.append(f"Azure SQL length limit {l_len} is not exposed/enforced by Fabric metadata")
            elif l_len is None and r_len is not None:
                findings.append(("MISMATCH", f"Azure SQL length is unbounded, but Fabric enforces max_length={r_len}."))
                attrnotes.append(f"Azure SQL unbounded vs Fabric max_length {r_len}")

        for prop in ("precision", "scale"):
            lv, rv = lc[prop], rc[prop]
            if lv is not None and rv is not None and lv != rv:
                findings.append(("MISMATCH", f"{prop.capitalize()} differs: Azure SQL={lv}, Fabric={rv}."))
                attrnotes.append(f"{prop} {lv} vs {rv}")
            elif (lv is not None and rv is None) or (lv is None and rv is not None):
                if any(t in {"decimal", "numeric"} for t in {type_base(lc), type_base(rc)}):
                    findings.append(("UNKNOWN", f"{prop.capitalize()} is unverified (Azure SQL={lv}, Fabric={rv})."))
                    attrnotes.append(f"{prop} unverified ({lv} vs {rv})")

        if lc["ordinal_position"] is not None and rc["ordinal_position"] is not None and lc["ordinal_position"] != rc["ordinal_position"]:
            order_diffs.append({"column": lc["name"], "azure_sql": lc["ordinal_position"], "fabric": rc["ordinal_position"]})
        statuses = [s for s, _ in findings]
        if "MISMATCH" in statuses:
            overall = "MISMATCH"
        elif "UNKNOWN" in statuses:
            overall = "UNKNOWN"
        elif typestatus == "COMPATIBLE":
            overall = "COMPATIBLE"
        else:
            overall = "MATCH"
        counts[overall] += 1
        details.append({
            "column": lc["name"], "azure_sql_type": lc["data_type"], "fabric_type": rc["data_type"],
            "nullability": f"{lc['nullable']} / {rc['nullable']}" if lc["nullable"] is not None and rc["nullable"] is not None else "UNKNOWN",
            "attributes": "; ".join(attrnotes) if attrnotes else "No comparable length/precision/scale difference detected.",
            "status": overall,
            "details": " ".join(x[1] for x in findings if x[1])
        })

    missing_in_fabric = [
        {"column": x["column"], "azure_sql_type": x["azure_sql_type"], "status": x["status"], "details": x["details"]}
        for x in details if x["status"] == "MISSING IN FABRIC"
    ]
    extra_in_fabric = [
        {"column": x["column"], "fabric_type": x["fabric_type"], "status": x["status"], "details": x["details"]}
        for x in details if x["status"] == "EXTRA IN FABRIC"
    ]

    key_results = [compare_keys(left, right, "primary_key", "Primary key"), compare_keys(left, right, "foreign_keys", "Foreign keys")]
    required_metadata_available = bool(left.get("table") and right.get("table") and isinstance(left.get("columns"), list) and isinstance(right.get("columns"), list))
    col_blockers = any(x["status"] == "UNKNOWN" for x in details)
    substantive = counts["MISMATCH"] + counts["MISSING IN FABRIC"] + counts["EXTRA IN FABRIC"]
    if not required_metadata_available or col_blockers:
        overall_status = "INCOMPLETE"
    elif substantive > 0 or any(x["status"] == "MISMATCH" for x in key_results):
        overall_status = "DIFFERENCES FOUND"
    elif counts["COMPATIBLE"] > 0 or any(x["status"] == "COMPATIBLE" for x in key_results):
        overall_status = "COMPATIBLE WITH CAVEATS"
    else:
        overall_status = "MATCH"

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "comparison": {"azure_sql": {k: left.get(k) for k in ["system", "server", "database", "schema", "table", "retrieved_at", "workspace", "lakehouse"]}, "fabric": {k: right.get(k) for k in ["system", "server", "database", "schema", "table", "retrieved_at", "workspace", "lakehouse"]}},
        "summary": {"azure_sql_column_count": len(lcols), "fabric_column_count": len(rcols), "column_findings": counts, "column_order_differences": len(order_diffs), "overall_status": overall_status},
        "missing_in_fabric": missing_in_fabric,
        "extra_in_fabric": extra_in_fabric,
        "columns_removed_in_fabric": missing_in_fabric,
        "columns_added_in_fabric": extra_in_fabric,
        "columns": details,
        "column_order_differences": order_diffs,
        "key_comparison": key_results,
        "warnings": ["This is a metadata comparison, not a row-data comparison.", "Type-family compatibility is not proof of lossless conversion.", "If type, nullability, length, precision, scale or key metadata was unavailable, results are partial."]
    }


def esc(value: Any) -> str:
    if value is None:
        return "NOT AVAILABLE"
    if isinstance(value, (list, dict)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(result: dict[str, Any]) -> str:
    c = result["comparison"]; s = result["summary"]; counts = s["column_findings"]
    a, f = c["azure_sql"], c["fabric"]
    lines = ["# Azure SQL–Fabric Lakehouse Schema Comparison", "", "## Comparison scope", "",
      "| Field | Azure SQL source | Fabric Lakehouse target |", "|---|---|---|"]
    def label(meta: dict[str, Any], key: str) -> Any: return meta.get(key) or "NOT AVAILABLE"
    rows = [("System", label(a,"system"), label(f,"system")), ("Database / Workspace", label(a,"database"), label(f,"workspace")), ("Schema / Namespace", label(a,"schema"), label(f,"schema")), ("Table / Lakehouse", label(a,"table"), f"{label(f,'lakehouse')} / {label(f,'table')}"), ("Metadata retrieved", label(a,"retrieved_at"), label(f,"retrieved_at"))]
    for r in rows: lines.append("| " + " | ".join(esc(x) for x in r) + " |")
    lines += ["", "## Summary", "", "| Metric | Count |", "|---|---:|", f"| Azure SQL columns | {s['azure_sql_column_count']} |", f"| Fabric columns | {s['fabric_column_count']} |"]
    for key in ["MATCH", "COMPATIBLE", "MISMATCH", "MISSING IN FABRIC", "EXTRA IN FABRIC", "UNKNOWN"]:
        lines.append(f"| {key.title()} | {counts.get(key, 0)} |")
    lines += [f"| Column order differences (informational) | {s['column_order_differences']} |", f"| **Overall status** | **{s['overall_status']}** |", "", "## Column-by-column comparison", "", "| Column | Azure SQL type | Fabric type | Nullability | Length / precision / scale | Status | Details |", "|---|---|---|---|---|---|---|"]
    for x in result["columns"]:
        row = [x["column"], x["azure_sql_type"], x["fabric_type"], x["nullability"], x["attributes"], x["status"], x["details"]]
        lines.append("| " + " | ".join(esc(y) for y in row) + " |")

    # Dedicated Section: Missing and Additional Columns
    lines += ["", "## Missing and additional columns", ""]
    lines += ["### Columns removed in Fabric (Present in Azure SQL only / Missing in Fabric)", ""]
    if result.get("missing_in_fabric"):
        lines += ["| Column | Azure SQL type | Status | Details |", "|---|---|---|---|"]
        for x in result["missing_in_fabric"]:
            lines.append(f"| {esc(x['column'])} | {esc(x['azure_sql_type'])} | MISSING IN FABRIC | {esc(x['details'])} |")
    else:
        lines.append("No columns removed in Fabric (all Azure SQL columns exist in Fabric).")

    lines += ["", "### Columns present only in Fabric (Added in Fabric / Extra in Fabric)", ""]
    if result.get("extra_in_fabric"):
        lines += ["| Column | Fabric type | Status | Details |", "|---|---|---|---|"]
        for x in result["extra_in_fabric"]:
            lines.append(f"| {esc(x['column'])} | {esc(x['fabric_type'])} | EXTRA IN FABRIC | {esc(x['details'])} |")
    else:
        lines.append("No extra columns present in Fabric (all Fabric columns exist in Azure SQL).")

    lines += ["", "## Column order differences", ""]
    if result["column_order_differences"]:
        lines += ["| Column | Azure SQL position | Fabric position |", "|---|---:|---:|"]
        for x in result["column_order_differences"]: lines.append(f"| {esc(x['column'])} | {x['azure_sql']} | {x['fabric']} |")
    else: lines.append("No order differences detected, or ordinal metadata was unavailable.")
    lines += ["", "## Keys and constraints", "", "| Property | Azure SQL | Fabric | Result | Notes |", "|---|---|---|---|---|"]
    for x in result["key_comparison"]: lines.append("| " + " | ".join(esc(x[k]) for k in ["property", "azure_sql", "fabric", "status", "details"]) + " |")
    lines += ["", "## Warnings and limitations", ""]
    for w in result["warnings"]: lines.append(f"- {w}")
    lines += ["", "## Suggested interpretation", "", "- `MATCH`: retrieved comparable schema properties match.", "- `COMPATIBLE`: different type representations are mapped to a known family; review caveats.", "- `MISMATCH`: a substantive schema property differs.", "- `MISSING IN FABRIC` / `EXTRA IN FABRIC`: the column exists on one side only.", "- `UNKNOWN` / `NOT AVAILABLE`: metadata was insufficient.", "- Overall `INCOMPLETE`: required metadata could not be reliably retrieved.", ""]
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--azure-sql-json", required=True, help="Normalized Azure SQL schema snapshot JSON")
    p.add_argument("--fabric-json", required=True, help="Normalized Fabric Lakehouse schema snapshot JSON")
    p.add_argument("--output-dir", default="schema-comparison-results", help="Output directory")
    p.add_argument("--mapping", default=str(DEFAULT_MAPPING), help="Type mapping JSON")
    args = p.parse_args()
    try:
        left = load_json(Path(args.azure_sql_json)); right = load_json(Path(args.fabric_json)); mapping = load_mapping(Path(args.mapping))
        if not isinstance(left.get("columns"), list) or not isinstance(right.get("columns"), list):
            raise ValueError("Each snapshot must contain a 'columns' array, even if it is empty.")
        result = compare_snapshots(left, right, mapping)
        out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
        md_path, json_path = out / "schema_comparison.md", out / "schema_comparison.json"
        md_path.write_text(render_markdown(result), encoding="utf-8")
        json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Markdown report: {md_path.resolve()}")
        print(f"JSON report: {json_path.resolve()}")
        print(f"Summary: {result['summary']['overall_status']}; Azure SQL columns={result['summary']['azure_sql_column_count']}; Fabric columns={result['summary']['fabric_column_count']}; mismatches={result['summary']['column_findings']['MISMATCH']}; missing in Fabric={result['summary']['column_findings']['MISSING IN FABRIC']}; extra in Fabric={result['summary']['column_findings']['EXTRA IN FABRIC']}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
