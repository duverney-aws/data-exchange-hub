"""
Natural Language Query End-to-End Integration Test

Tests the full NL query flow:
  User question → Lake Formation access check → Schema context build →
  Bedrock SQL generation → SQL validation → Athena execution →
  Bedrock response formatting → Natural language answer

Uses unittest.mock.MagicMock for all external clients (Bedrock, Athena,
Glue, Lake Formation) since these services cannot be mocked with moto.

Requirements: 12.1, 12.2, 12.3, 12.4, 12.5
"""
import io
import json
import os
import sys

import pytest
from unittest.mock import MagicMock

# Ensure the cdk root is on sys.path so service imports resolve
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from services.nl_query_service import (
    NLQueryService,
    SQLValidationError,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATABASE = "cmo_data_lake"
WORKGROUP = "cmo-workgroup"
RESULTS_LOCATION = "s3://athena-results/"
MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"

USER_ID = "arn:aws:iam::123456789012:user/pharma-analyst"
USER_QUERY = "Show me all batches that passed quality checks"

TABLE_NAME = "cmo_test_alpha_batch_records_silver"

GENERATED_SQL = (
    "SELECT batch_id, product_name, quantity "
    f"FROM {DATABASE}.{TABLE_NAME} "
    "WHERE quality_status = 'PASS' LIMIT 10"
)

NL_RESPONSE = "Based on the data, there are 3 batches that passed quality checks."

# ---------------------------------------------------------------------------
# Mock response builders
# ---------------------------------------------------------------------------


def _bedrock_response(text: str) -> dict:
    """Build a mock Bedrock invoke_model response with a readable body."""
    body_bytes = json.dumps({
        "content": [{"text": text}],
    }).encode()
    return {"body": io.BytesIO(body_bytes)}


def _lake_formation_permissions(table_names: list[str]) -> dict:
    """Build a mock Lake Formation list_permissions response."""
    entries = []
    for name in table_names:
        entries.append({
            "Resource": {
                "Table": {
                    "DatabaseName": DATABASE,
                    "Name": name,
                }
            },
            "Permissions": ["SELECT"],
        })
    return {"PrincipalResourcePermissions": entries}


def _glue_table_response() -> dict:
    """Build a mock Glue get_table response for the test table."""
    return {
        "Table": {
            "Name": TABLE_NAME,
            "StorageDescriptor": {
                "Columns": [
                    {"Name": "batch_id", "Type": "string"},
                    {"Name": "product_name", "Type": "string"},
                    {"Name": "quantity", "Type": "bigint"},
                    {"Name": "quality_status", "Type": "string"},
                ]
            },
            "PartitionKeys": [
                {"Name": "year", "Type": "string"},
                {"Name": "month", "Type": "string"},
            ],
        }
    }


def _athena_results() -> dict:
    """Build a mock Athena get_query_results response with header + data rows."""
    return {
        "ResultSet": {
            "Rows": [
                {"Data": [
                    {"VarCharValue": "batch_id"},
                    {"VarCharValue": "product_name"},
                    {"VarCharValue": "quantity"},
                ]},
                {"Data": [
                    {"VarCharValue": "BATCH001"},
                    {"VarCharValue": "Aspirin 500mg"},
                    {"VarCharValue": "10000"},
                ]},
                {"Data": [
                    {"VarCharValue": "BATCH002"},
                    {"VarCharValue": "Ibuprofen 200mg"},
                    {"VarCharValue": "5000"},
                ]},
                {"Data": [
                    {"VarCharValue": "BATCH003"},
                    {"VarCharValue": "Amoxicillin 250mg"},
                    {"VarCharValue": "8000"},
                ]},
            ]
        }
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_bedrock():
    return MagicMock()


@pytest.fixture
def mock_athena():
    return MagicMock()


@pytest.fixture
def mock_glue():
    return MagicMock()


@pytest.fixture
def mock_lakeformation():
    return MagicMock()


@pytest.fixture
def service(mock_bedrock, mock_athena, mock_glue, mock_lakeformation):
    return NLQueryService(
        bedrock_client=mock_bedrock,
        athena_client=mock_athena,
        glue_client=mock_glue,
        lakeformation_client=mock_lakeformation,
        database=DATABASE,
        workgroup=WORKGROUP,
        results_location=RESULTS_LOCATION,
        model_id=MODEL_ID,
        query_timeout=5,
    )


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestNLQueryEndToEnd:
    """
    End-to-end test for the Natural Language Query flow.

    Exercises every step of NLQueryService using MagicMock clients.
    """

    # ---------------------------------------------------------------
    # Step 1: get_user_tables — Lake Formation permissions
    # ---------------------------------------------------------------

    def test_get_user_tables(self, service, mock_lakeformation):
        """Verify tables are extracted correctly from Lake Formation permissions."""
        mock_lakeformation.list_permissions.return_value = (
            _lake_formation_permissions([TABLE_NAME])
        )

        tables = service.get_user_tables(USER_ID)

        assert len(tables) == 1
        assert tables[0]["database"] == DATABASE
        assert tables[0]["table"] == TABLE_NAME
        mock_lakeformation.list_permissions.assert_called_once_with(
            Principal={"DataLakePrincipalIdentifier": USER_ID}
        )

    # ---------------------------------------------------------------
    # Step 2: build_schema_context — Glue Data Catalog metadata
    # ---------------------------------------------------------------

    def test_build_schema_context(self, service, mock_glue):
        """Verify schema context string is built correctly from Glue metadata."""
        mock_glue.get_table.return_value = _glue_table_response()

        tables = [{"database": DATABASE, "table": TABLE_NAME}]
        context = service.build_schema_context(tables)

        assert f"{DATABASE}.{TABLE_NAME}" in context
        assert "batch_id (string)" in context
        assert "product_name (string)" in context
        assert "quantity (bigint)" in context
        assert "quality_status (string)" in context
        assert "year (string) [partition key]" in context
        assert "month (string) [partition key]" in context

    # ---------------------------------------------------------------
    # Step 3: generate_sql — Bedrock SQL generation
    # ---------------------------------------------------------------

    def test_generate_sql(self, service, mock_bedrock):
        """Verify SQL is extracted from Bedrock response."""
        mock_bedrock.invoke_model.return_value = _bedrock_response(GENERATED_SQL)

        schema_context = (
            f"Table: {DATABASE}.{TABLE_NAME}\nColumns:\n"
            "  - batch_id (string)\n  - product_name (string)\n"
            "  - quantity (bigint)\n  - quality_status (string)"
        )
        sql = service.generate_sql(USER_QUERY, schema_context)

        assert sql.upper().startswith("SELECT")
        assert "batch_id" in sql
        assert TABLE_NAME in sql

    # ---------------------------------------------------------------
    # Step 4: validate_sql — SQL safety validation
    # ---------------------------------------------------------------

    def test_validate_sql_safe_query(self, service):
        """Verify safe SELECT queries pass validation."""
        service.validate_sql(GENERATED_SQL)  # Should not raise

    def test_validate_sql_rejects_drop(self, service):
        """Verify DROP statements are rejected."""
        with pytest.raises(SQLValidationError, match="DROP"):
            service.validate_sql("DROP TABLE batch_records")

    def test_validate_sql_rejects_delete(self, service):
        """Verify DELETE statements are rejected."""
        with pytest.raises(SQLValidationError, match="DELETE"):
            service.validate_sql("DELETE FROM batch_records WHERE 1=1")

    # ---------------------------------------------------------------
    # Step 5: execute_query — Athena execution
    # ---------------------------------------------------------------

    def test_execute_query(self, service, mock_athena):
        """Verify Athena execution and result parsing."""
        mock_athena.start_query_execution.return_value = {
            "QueryExecutionId": "test-exec-001"
        }
        mock_athena.get_query_execution.return_value = {
            "QueryExecution": {"Status": {"State": "SUCCEEDED"}}
        }
        mock_athena.get_query_results.return_value = _athena_results()

        results, execution_id = service.execute_query(GENERATED_SQL)

        assert execution_id == "test-exec-001"
        assert len(results) == 3
        assert results[0]["batch_id"] == "BATCH001"
        assert results[0]["product_name"] == "Aspirin 500mg"
        assert results[0]["quantity"] == "10000"
        assert results[1]["batch_id"] == "BATCH002"
        assert results[2]["batch_id"] == "BATCH003"

    # ---------------------------------------------------------------
    # Step 6: format_response — Bedrock response formatting
    # ---------------------------------------------------------------

    def test_format_response(self, service, mock_bedrock):
        """Verify natural language response is generated from results."""
        mock_bedrock.invoke_model.return_value = _bedrock_response(NL_RESPONSE)

        results = [
            {"batch_id": "BATCH001", "product_name": "Aspirin 500mg", "quantity": "10000"},
            {"batch_id": "BATCH002", "product_name": "Ibuprofen 200mg", "quantity": "5000"},
            {"batch_id": "BATCH003", "product_name": "Amoxicillin 250mg", "quantity": "8000"},
        ]
        response = service.format_response(USER_QUERY, results)

        assert "3 batches" in response
        assert "passed quality checks" in response

    # ---------------------------------------------------------------
    # Step 7: Full process_query — end-to-end flow
    # ---------------------------------------------------------------

    def test_full_process_query(
        self, service, mock_bedrock, mock_athena, mock_glue, mock_lakeformation
    ):
        """Wire all mocks together and verify end-to-end process_query flow."""
        # Lake Formation: user has access to one table
        mock_lakeformation.list_permissions.return_value = (
            _lake_formation_permissions([TABLE_NAME])
        )

        # Glue: table schema
        mock_glue.get_table.return_value = _glue_table_response()

        # Bedrock: first call = SQL generation, second call = response formatting
        mock_bedrock.invoke_model.side_effect = [
            _bedrock_response(GENERATED_SQL),
            _bedrock_response(NL_RESPONSE),
        ]

        # Athena: execution
        mock_athena.start_query_execution.return_value = {
            "QueryExecutionId": "test-exec-001"
        }
        mock_athena.get_query_execution.return_value = {
            "QueryExecution": {"Status": {"State": "SUCCEEDED"}}
        }
        mock_athena.get_query_results.return_value = _athena_results()

        # Execute
        result = service.process_query(USER_QUERY, USER_ID)

        # Verify all output fields
        assert result["query"] == USER_QUERY
        assert result["sql"] is not None
        assert "SELECT" in result["sql"].upper()
        assert TABLE_NAME in result["sql"]
        assert len(result["results"]) == 3
        assert result["results"][0]["batch_id"] == "BATCH001"
        assert result["response"] == NL_RESPONSE
        assert result["query_execution_id"] == "test-exec-001"

        # Verify service interactions
        mock_lakeformation.list_permissions.assert_called_once()
        mock_glue.get_table.assert_called_once()
        assert mock_bedrock.invoke_model.call_count == 2
        mock_athena.start_query_execution.assert_called_once()

    # ---------------------------------------------------------------
    # Step 8: Access control enforcement — no permissions
    # ---------------------------------------------------------------

    def test_access_control_no_permissions(self, service, mock_lakeformation):
        """When user has no table permissions, verify 'no access' response."""
        mock_lakeformation.list_permissions.return_value = {
            "PrincipalResourcePermissions": []
        }

        result = service.process_query(USER_QUERY, USER_ID)

        assert result["sql"] is None
        assert result["results"] == []
        assert "do not have access" in result["response"].lower()
        assert result["query_execution_id"] is None
