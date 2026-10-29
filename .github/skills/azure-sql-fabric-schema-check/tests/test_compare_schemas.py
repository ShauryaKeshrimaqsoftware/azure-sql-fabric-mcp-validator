import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT))
import compare_schemas as cs
MAPPING = cs.load_mapping(Path(__file__).resolve().parents[1] / "config" / "type-mapping.json")

class CompareSchemaTests(unittest.TestCase):
    def base(self):
        return {"system":"Azure SQL Database", "database":"db", "schema":"dbo", "table":"T", "columns":[
            {"name":"id","data_type":"int","nullable":False,"precision":10,"scale":0,"ordinal_position":1},
            {"name":"amount","data_type":"decimal","nullable":True,"precision":18,"scale":2,"ordinal_position":2},
        ], "primary_key":["id"], "foreign_keys":[]}

    def target(self):
        return {"system":"Microsoft Fabric Lakehouse", "workspace":"w", "lakehouse":"lh", "schema":"dbo", "table":"T", "columns":[
            {"name":"id","data_type":"integer","nullable":False,"precision":10,"scale":0,"ordinal_position":1},
            {"name":"amount","data_type":"decimal","nullable":True,"precision":18,"scale":2,"ordinal_position":2},
        ], "primary_key":["id"], "foreign_keys":[]}

    def test_exact_matching_metadata(self):
        result=cs.compare_snapshots(self.base(), self.target(), MAPPING)
        self.assertEqual(result["summary"]["column_findings"]["MATCH"], 1)
        self.assertEqual(result["summary"]["column_findings"]["COMPATIBLE"], 1)
        self.assertEqual(result["summary"]["overall_status"], "COMPATIBLE WITH CAVEATS")

    def test_missing_in_fabric(self):
        a=self.base(); f=self.target(); f["columns"].pop(1)
        result=cs.compare_snapshots(a, f, MAPPING)
        self.assertEqual(result["summary"]["column_findings"]["MISSING IN FABRIC"], 1)
        self.assertEqual(result["summary"]["overall_status"], "DIFFERENCES FOUND")
        self.assertEqual(len(result["missing_in_fabric"]), 1)
        self.assertEqual(result["missing_in_fabric"][0]["column"], "amount")
        md = cs.render_markdown(result)
        self.assertIn("Columns removed in Fabric", md)
        self.assertIn("amount", md)

    def test_extra_in_fabric(self):
        a=self.base(); f=self.target(); f["columns"].append({"name":"new","data_type":"string"})
        result=cs.compare_snapshots(a, f, MAPPING)
        self.assertEqual(result["summary"]["column_findings"]["EXTRA IN FABRIC"], 1)
        self.assertEqual(len(result["extra_in_fabric"]), 1)
        self.assertEqual(result["extra_in_fabric"][0]["column"], "new")
        md = cs.render_markdown(result)
        self.assertIn("Columns present only in Fabric", md)
        self.assertIn("new", md)

    def test_type_mismatch(self):
        a=self.base(); f=self.target(); f["columns"][0]["data_type"]="string"
        result=cs.compare_snapshots(a, f, MAPPING)
        self.assertEqual(result["summary"]["column_findings"]["MISMATCH"], 1)

    def test_nullability_mismatch(self):
        a=self.base(); f=self.target(); f["columns"][0]["nullable"]=True
        result=cs.compare_snapshots(a, f, MAPPING)
        item=next(x for x in result["columns"] if x["column"]=="id")
        self.assertEqual(item["status"], "MISMATCH")

    def test_precision_mismatch(self):
        a=self.base(); f=self.target(); f["columns"][1]["precision"]=10
        result=cs.compare_snapshots(a, f, MAPPING)
        item=next(x for x in result["columns"] if x["column"]=="amount")
        self.assertEqual(item["status"], "MISMATCH")

    def test_sql_tinyint_vs_spark_byte_is_not_equivalent(self):
        a=self.base(); f=self.target()
        a["columns"]=[{"name":"code","data_type":"tinyint","nullable":False}]
        f["columns"]=[{"name":"code","data_type":"byte","nullable":False}]
        result=cs.compare_snapshots(a, f, MAPPING)
        self.assertEqual(result["columns"][0]["status"], "MISMATCH")

    def test_unknown_nullability_is_not_match(self):
        a=self.base(); f=self.target()
        a["columns"][0]["nullable"]=None
        result=cs.compare_snapshots(a, f, MAPPING)
        item=next(x for x in result["columns"] if x["column"]=="id")
        self.assertEqual(item["status"], "UNKNOWN")
        self.assertEqual(result["summary"]["overall_status"], "INCOMPLETE")

    def test_duplicate_column_names_rejected(self):
        a=self.base(); a["columns"].append({"name":"ID","data_type":"int"})
        with self.assertRaises(ValueError):
            cs.compare_snapshots(a, self.target(), MAPPING)

    def test_key_metadata_unavailable_distinguished_from_empty(self):
        a=self.base(); f=self.target(); f.pop("primary_key")
        result=cs.compare_snapshots(a, f, MAPPING)
        pk=next(x for x in result["key_comparison"] if x["property"]=="Primary key")
        self.assertEqual(pk["status"], "NOT AVAILABLE")

    def test_order_differences_are_informational(self):
        a=self.base(); f=self.target(); f["columns"][0]["ordinal_position"]=2
        result=cs.compare_snapshots(a, f, MAPPING)
        self.assertEqual(result["summary"]["column_order_differences"], 1)
        self.assertNotEqual(result["summary"]["overall_status"], "DIFFERENCES FOUND")

    def test_missing_snapshot_columns_rejected(self):
        with self.assertRaises(ValueError):
            cs.compare_snapshots({"system":"Azure SQL"}, self.target(), MAPPING)

    def test_datetime2_vs_fabric_timestamp_is_compatible(self):
        a=self.base(); f=self.target()
        a["columns"]=[{"name":"created","data_type":"datetime2","nullable":False,"scale":7}]
        f["columns"]=[{"name":"created","data_type":"timestamp","nullable":False,"scale":6}]
        result=cs.compare_snapshots(a, f, MAPPING)
        self.assertEqual(result["columns"][0]["status"], "MISMATCH")
        self.assertIn("Scale differs", result["columns"][0]["details"])

    def test_sql_timestamp_is_not_misread_as_fabric_datetime(self):
        a=self.base(); f=self.target()
        a["columns"]=[{"name":"row_ver","data_type":"timestamp","nullable":False}]
        f["columns"]=[{"name":"row_ver","data_type":"timestamp","nullable":False}]
        result=cs.compare_snapshots(a, f, MAPPING)
        self.assertEqual(result["columns"][0]["status"], "MISMATCH")
        self.assertIn("rowversion", result["columns"][0]["details"])

    def test_decimal_parameters_parsed_from_type_string(self):
        a=self.base(); f=self.target()
        a["columns"]=[{"name":"amount","data_type":"decimal(18,2)","nullable":True}]
        f["columns"]=[{"name":"amount","data_type":"decimal(18,2)","nullable":True}]
        result=cs.compare_snapshots(a, f, MAPPING)
        self.assertEqual(result["columns"][0]["status"], "MATCH")

    def test_uniqueidentifier_vs_fabric_string_is_compatible(self):
        a=self.base(); f=self.target()
        a["columns"]=[{"name":"guid","data_type":"uniqueidentifier","nullable":False}]
        f["columns"]=[{"name":"guid","data_type":"string","nullable":False}]
        result=cs.compare_snapshots(a, f, MAPPING)
        self.assertEqual(result["columns"][0]["status"], "COMPATIBLE")
        self.assertIn("GUID is represented as a string", result["columns"][0]["details"])

    def test_sql_real_vs_fabric_float_is_compatible(self):
        a=self.base(); f=self.target()
        a["columns"]=[{"name":"val","data_type":"real","nullable":False}]
        f["columns"]=[{"name":"val","data_type":"float","nullable":False}]
        result=cs.compare_snapshots(a, f, MAPPING)
        self.assertEqual(result["columns"][0]["status"], "COMPATIBLE")

    def test_sql_float_vs_fabric_double_is_compatible(self):
        a=self.base(); f=self.target()
        a["columns"]=[{"name":"val","data_type":"float","nullable":False}]
        f["columns"]=[{"name":"val","data_type":"double","nullable":False}]
        result=cs.compare_snapshots(a, f, MAPPING)
        self.assertEqual(result["columns"][0]["status"], "COMPATIBLE")

    def test_sql_float_vs_fabric_float_has_precision_caveat(self):
        a=self.base(); f=self.target()
        a["columns"]=[{"name":"val","data_type":"float","nullable":False}]
        f["columns"]=[{"name":"val","data_type":"float","nullable":False}]
        result=cs.compare_snapshots(a, f, MAPPING)
        self.assertEqual(result["columns"][0]["status"], "COMPATIBLE")
        self.assertIn("SQL Server float is 64-bit double precision, whereas Fabric float is 32-bit single precision", result["columns"][0]["details"])

    def test_sql_tinyint_widened_to_fabric_short_is_compatible(self):
        a=self.base(); f=self.target()
        a["columns"]=[{"name":"code","data_type":"tinyint","nullable":False}]
        f["columns"]=[{"name":"code","data_type":"short","nullable":False}]
        result=cs.compare_snapshots(a, f, MAPPING)
        self.assertEqual(result["columns"][0]["status"], "COMPATIBLE")
        self.assertIn("widened", result["columns"][0]["details"])

    def test_sql_money_mapped_to_fabric_decimal(self):
        a=self.base(); f=self.target()
        a["columns"]=[{"name":"price","data_type":"money","nullable":True}]
        f["columns"]=[{"name":"price","data_type":"decimal","nullable":True}]
        result=cs.compare_snapshots(a, f, MAPPING)
        self.assertEqual(result["columns"][0]["status"], "COMPATIBLE")

    def test_composite_key_order_difference_is_compatible(self):
        a=self.base(); f=self.target()
        a["primary_key"]=["CustomerID", "OrderID"]
        f["primary_key"]=["OrderID", "CustomerID"]
        result=cs.compare_snapshots(a, f, MAPPING)
        pk=next(x for x in result["key_comparison"] if x["property"]=="Primary key")
        self.assertEqual(pk["status"], "COMPATIBLE")
        self.assertIn("ordinal order differs", pk["details"])

    def test_unbounded_sql_vs_bounded_fabric_string_is_mismatch(self):
        a=self.base(); f=self.target()
        a["columns"]=[{"name":"notes","data_type":"varchar","nullable":True,"max_length":-1}]
        f["columns"]=[{"name":"notes","data_type":"string","nullable":True,"max_length":100}]
        result=cs.compare_snapshots(a, f, MAPPING)
        self.assertEqual(result["columns"][0]["status"], "MISMATCH")
        self.assertIn("unbounded", result["columns"][0]["details"])

    def test_nvarchar_byte_length_normalized_to_char_length(self):
        a=self.base(); f=self.target()
        # SQL Server sys.columns stores max_length in bytes (100 bytes = 50 characters)
        a["columns"]=[{"name":"city","data_type":"nvarchar","nullable":True,"max_length_bytes":100}]
        f["columns"]=[{"name":"city","data_type":"string","nullable":True,"max_length":50}]
        result=cs.compare_snapshots(a, f, MAPPING)
        self.assertEqual(result["columns"][0]["status"], "COMPATIBLE")
        self.assertNotIn("MISMATCH", result["columns"][0]["details"])

    def test_decimal_unverified_precision_on_one_side_is_unknown(self):
        a=self.base(); f=self.target()
        a["columns"]=[{"name":"amount","data_type":"decimal","nullable":True,"precision":18,"scale":2}]
        f["columns"]=[{"name":"amount","data_type":"decimal","nullable":True,"precision":None,"scale":None}]
        result=cs.compare_snapshots(a, f, MAPPING)
        item=next(x for x in result["columns"] if x["column"]=="amount")
        self.assertEqual(item["status"], "UNKNOWN")
        self.assertEqual(result["summary"]["overall_status"], "INCOMPLETE")

if __name__ == "__main__":
    unittest.main()
