"""
Unit Tests for Schema Inference and Merging

Task 2.4: Implement schema inference from sample data
- Tests infer_schema_from_sample() for CSV, JSON, and Parquet formats
- Tests merge_schemas() for combining multiple inferred schemas
- Requirements: 3.1, 3.5
"""
import io
import json
import pytest

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from services.schema_registry_service import (
    SchemaRegistryService,
    SchemaValidationError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def service():
    """Return a SchemaRegistryService (no Glue client needed for inference)."""
    from unittest.mock import MagicMock
    return SchemaRegistryService(glue_client=MagicMock())


def _make_csv_bytes(header: str, rows: list[str]) -> bytes:
    """Helper to build CSV bytes from header + row strings."""
    lines = [header] + rows
    return "\n".join(lines).encode("utf-8")


def _make_parquet_bytes(df: pd.DataFrame) -> bytes:
    """Helper to convert a DataFrame to Parquet bytes."""
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# CSV inference
# ---------------------------------------------------------------------------

class TestInferCSV:
    """Tests for CSV schema inference."""

    def test_basic_csv_types(self, service):
        """Infer string, integer, number, and boolean from CSV."""
        data = _make_csv_bytes(
            "name,age,score,active",
            [
                "Alice,30,95.5,true",
                "Bob,25,88.0,false",
            ],
        )
        schema = service.infer_schema_from_sample(data, "csv")

        assert schema["type"] == "object"
        assert schema["properties"]["name"]["type"] == "string"
        assert schema["properties"]["age"]["type"] == "integer"
        assert schema["properties"]["score"]["type"] == "number"
        assert schema["properties"]["active"]["type"] == "boolean"

    def test_csv_required_fields(self, service):
        """All columns with values in every row are required."""
        data = _make_csv_bytes(
            "id,value,optional",
            [
                "1,hello,x",
                "2,world,",
            ],
        )
        schema = service.infer_schema_from_sample(data, "csv")

        assert "id" in schema["required"]
        assert "value" in schema["required"]
        # 'optional' has an empty value in row 2
        assert "optional" not in schema["required"]

    def test_csv_date_strings(self, service):
        """Date-like values are inferred as string (not a numeric type)."""
        data = _make_csv_bytes(
            "batch_id,manufacture_date",
            [
                "B001,2024-01-15",
                "B002,2024-02-20",
            ],
        )
        schema = service.infer_schema_from_sample(data, "csv")

        assert schema["properties"]["manufacture_date"]["type"] == "string"

    def test_csv_empty_body_raises(self, service):
        """CSV with header only (no data rows) still returns a schema."""
        data = b"col_a,col_b\n"
        schema = service.infer_schema_from_sample(data, "csv")
        # Fields exist but nothing is required (no rows to confirm)
        assert "col_a" in schema["properties"]
        assert schema["required"] == []

    def test_csv_no_header_raises(self, service):
        """Completely empty CSV raises SchemaValidationError."""
        with pytest.raises(SchemaValidationError, match="empty"):
            service.infer_schema_from_sample(b"", "csv")


# ---------------------------------------------------------------------------
# JSON inference
# ---------------------------------------------------------------------------

class TestInferJSON:
    """Tests for JSON schema inference."""

    def test_single_object(self, service):
        """Infer schema from a single JSON object."""
        data = json.dumps({
            "batch_id": "B001",
            "quantity": 100,
            "weight": 55.5,
            "passed": True,
        }).encode("utf-8")

        schema = service.infer_schema_from_sample(data, "json")

        assert schema["properties"]["batch_id"]["type"] == "string"
        assert schema["properties"]["quantity"]["type"] == "integer"
        assert schema["properties"]["weight"]["type"] == "number"
        assert schema["properties"]["passed"]["type"] == "boolean"

    def test_array_of_objects(self, service):
        """Infer schema from an array of JSON objects."""
        data = json.dumps([
            {"id": 1, "name": "Alpha"},
            {"id": 2, "name": "Beta"},
        ]).encode("utf-8")

        schema = service.infer_schema_from_sample(data, "json")

        assert schema["properties"]["id"]["type"] == "integer"
        assert schema["properties"]["name"]["type"] == "string"
        assert sorted(schema["required"]) == ["id", "name"]

    def test_nested_object_type(self, service):
        """Nested objects are typed as 'object'."""
        data = json.dumps({
            "id": "X1",
            "metadata": {"source": "lab", "version": 2},
        }).encode("utf-8")

        schema = service.infer_schema_from_sample(data, "json")
        assert schema["properties"]["metadata"]["type"] == "object"

    def test_array_field_type(self, service):
        """Array fields are typed as 'array'."""
        data = json.dumps({
            "id": "X1",
            "tags": ["pharma", "batch"],
        }).encode("utf-8")

        schema = service.infer_schema_from_sample(data, "json")
        assert schema["properties"]["tags"]["type"] == "array"

    def test_mixed_types_resolve_to_general(self, service):
        """When a field has int in one record and float in another, resolve to number."""
        data = json.dumps([
            {"value": 10},
            {"value": 10.5},
        ]).encode("utf-8")

        schema = service.infer_schema_from_sample(data, "json")
        assert schema["properties"]["value"]["type"] == "number"

    def test_empty_array_raises(self, service):
        """Empty JSON array raises SchemaValidationError."""
        with pytest.raises(SchemaValidationError, match="empty"):
            service.infer_schema_from_sample(b"[]", "json")

    def test_invalid_json_raises(self, service):
        """Malformed JSON raises SchemaValidationError."""
        with pytest.raises(SchemaValidationError, match="Failed to parse"):
            service.infer_schema_from_sample(b"{bad json", "json")


# ---------------------------------------------------------------------------
# Parquet inference
# ---------------------------------------------------------------------------

class TestInferParquet:
    """Tests for Parquet schema inference."""

    def test_basic_parquet_types(self, service):
        """Infer types from a Parquet file with various column types."""
        df = pd.DataFrame({
            "batch_id": ["B001", "B002"],
            "quantity": [100, 200],
            "weight": [55.5, 60.0],
            "passed": [True, False],
        })
        data = _make_parquet_bytes(df)

        schema = service.infer_schema_from_sample(data, "parquet")

        assert schema["properties"]["batch_id"]["type"] == "string"
        assert schema["properties"]["quantity"]["type"] == "integer"
        assert schema["properties"]["weight"]["type"] == "number"
        assert schema["properties"]["passed"]["type"] == "boolean"

    def test_parquet_timestamp_as_string(self, service):
        """Timestamp columns map to 'string' in JSON Schema."""
        df = pd.DataFrame({
            "event_time": pd.to_datetime(["2024-01-01", "2024-06-15"]),
        })
        data = _make_parquet_bytes(df)

        schema = service.infer_schema_from_sample(data, "parquet")
        assert schema["properties"]["event_time"]["type"] == "string"

    def test_parquet_corrupt_raises(self, service):
        """Corrupt Parquet bytes raise SchemaValidationError."""
        with pytest.raises(SchemaValidationError, match="Failed to parse"):
            service.infer_schema_from_sample(b"not-parquet", "parquet")


# ---------------------------------------------------------------------------
# Unsupported format / empty data
# ---------------------------------------------------------------------------

class TestInferEdgeCases:
    """Edge-case tests for infer_schema_from_sample."""

    def test_unsupported_format(self, service):
        """Unsupported file format raises SchemaValidationError."""
        with pytest.raises(SchemaValidationError, match="Unsupported file format"):
            service.infer_schema_from_sample(b"data", "xml")

    def test_empty_bytes(self, service):
        """Empty bytes raise SchemaValidationError."""
        with pytest.raises(SchemaValidationError, match="empty"):
            service.infer_schema_from_sample(b"", "csv")

    def test_format_case_insensitive(self, service):
        """Format string is case-insensitive."""
        data = json.dumps({"a": 1}).encode("utf-8")
        schema = service.infer_schema_from_sample(data, "JSON")
        assert "a" in schema["properties"]


# ---------------------------------------------------------------------------
# Schema merging
# ---------------------------------------------------------------------------

class TestMergeSchemas:
    """Tests for merge_schemas."""

    def test_merge_identical_schemas(self, service):
        """Merging identical schemas returns the same schema."""
        s = {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "value": {"type": "integer"},
            },
            "required": ["id", "value"],
        }
        merged = service.merge_schemas([s, s])

        assert merged["properties"]["id"]["type"] == "string"
        assert merged["properties"]["value"]["type"] == "integer"
        assert sorted(merged["required"]) == ["id", "value"]

    def test_merge_overlapping_fields(self, service):
        """Union of fields from two schemas with some overlap."""
        s1 = {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
            },
            "required": ["id", "name"],
        }
        s2 = {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["id", "age"],
        }
        merged = service.merge_schemas([s1, s2])

        assert set(merged["properties"].keys()) == {"id", "name", "age"}
        # Only 'id' is in both schemas
        assert merged["required"] == ["id"]

    def test_merge_conflicting_types_string_wins(self, service):
        """When one schema says string and another says integer, string wins."""
        s1 = {"type": "object", "properties": {"val": {"type": "integer"}}}
        s2 = {"type": "object", "properties": {"val": {"type": "string"}}}

        merged = service.merge_schemas([s1, s2])
        assert merged["properties"]["val"]["type"] == "string"

    def test_merge_conflicting_int_number(self, service):
        """integer + number resolves to number."""
        s1 = {"type": "object", "properties": {"val": {"type": "integer"}}}
        s2 = {"type": "object", "properties": {"val": {"type": "number"}}}

        merged = service.merge_schemas([s1, s2])
        assert merged["properties"]["val"]["type"] == "number"

    def test_merge_empty_list_raises(self, service):
        """Empty schema list raises SchemaValidationError."""
        with pytest.raises(SchemaValidationError, match="No schemas"):
            service.merge_schemas([])

    def test_merge_invalid_schema_raises(self, service):
        """Non-dict schema raises SchemaValidationError."""
        with pytest.raises(SchemaValidationError, match="must be a dict"):
            service.merge_schemas(["not a dict"])

    def test_merge_three_schemas(self, service):
        """Merge three schemas with progressive field additions."""
        s1 = {"type": "object", "properties": {"a": {"type": "string"}}}
        s2 = {"type": "object", "properties": {"a": {"type": "string"}, "b": {"type": "integer"}}}
        s3 = {"type": "object", "properties": {"a": {"type": "string"}, "c": {"type": "boolean"}}}

        merged = service.merge_schemas([s1, s2, s3])

        assert set(merged["properties"].keys()) == {"a", "b", "c"}
        # Only 'a' appears in all three
        assert merged["required"] == ["a"]
