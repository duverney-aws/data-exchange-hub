"""
Tests for NLQueryService.

Covers:
  - SQL generation from natural language (Req 12.2)
  - SQL safety validation (Req 12.2)
  - Athena query execution (Req 12.3)
  - Natural language response formatting (Req 12.4, 12.6)
  - User table access via Lake Formation (Req 12.1, 12.5)
  - End-to-end process_query flow
"""
import io
import json
import pytest
from unittest.mock import MagicMock, patch

from services.nl_query_service import (
    NLQueryService,
    NLQueryError,
    SQLValidationError,
    QueryTimeoutError,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _bedrock_response(text: str):
    """Build a mock Bedrock invoke_model response."""
    body_bytes = json.dumps({
        "content": [{"text": text}],
    }).encode()
    return {"body": io.BytesIO(body_bytes)}


def _athena_results(headers: list, rows: list):
    """Build a mock Athena get_query_results response."""
    header_row = {"Data": [{"VarCharValue": h} for h in headers]}
    data_rows = [
        {"Data": [{"VarCharValue": str(v)} for v in row]}
        for row in rows
    ]
    return {"ResultSet": {"Rows": [header_row] + data_rows}}


@pytest.fixture
def mock_clients():
    return {
        "bedrock": MagicMock(),
        "athena": MagicMock(),
        "glue": MagicMock(),
        "lakeformation": MagicMock(),
    }


@pytest.fixture
def service(mock_clients):
    svc = NLQueryService(
        bedrock_client=mock_clients["bedrock"],
        athena_client=mock_clients["athena"],
        glue_client=mock_clients["glue"],
        lakeformation_client=mock_clients["lakeformation"],
        database="cmo_data_lake",
        workgroup="cmo-workgroup",
        results_location="s3://athena-results/",
        query_timeout=5,
    )
    return svc


# ------------------------------------------------------------------
# get_user_tables
# ------------------------------------------------------------------

class TestGetUserTables:
    def test_returns_tables_from_lake_formation(self, service, mock_clients):
        mock_clients["lakeformation"].list_permissions.return_value = {
            "PrincipalResourcePermissions": [
                {
                    "Resource": {
                        "Table": {
                            "DatabaseName": "cmo_data_lake",
                            "Name": "cmo_alpha_batch_records_silver",
                        }
                    },
                    "Permissions": ["SELECT"],
                },
                {
                    "Resource": {
                        "Table": {
                            "DatabaseName": "cmo_data_lake",
                            "Name": "cmo_alpha_quality_data_silver",
                        }
                    },
                    "Permissions": ["SELECT"],
                },
            ]
        }

        tables = service.get_user_tables("arn:aws:iam::123:user/analyst")
        assert len(tables) == 2
        assert tables[0]["table"] == "cmo_alpha_batch_records_silver"
        assert tables[1]["table"] == "cmo_alpha_quality_data_silver"

    def test_filters_out_all_tables_wildcard(self, service, mock_clients):
        mock_clients["lakeformation"].list_permissions.return_value = {
            "PrincipalResourcePermissions": [
                {
                    "Resource": {
                        "Table": {
                            "DatabaseName": "cmo_data_lake",
                            "Name": "ALL_TABLES",
                        }
                    },
                    "Permissions": ["SELECT"],
                },
            ]
        }
        tables = service.get_user_tables("user-1")
        assert tables == []

    def test_handles_table_with_columns_resource(self, service, mock_clients):
        mock_clients["lakeformation"].list_permissions.return_value = {
            "PrincipalResourcePermissions": [
                {
                    "Resource": {
                        "TableWithColumns": {
                            "DatabaseName": "cmo_data_lake",
                            "Name": "cmo_beta_records",
                        }
                    },
                    "Permissions": ["SELECT"],
                },
            ]
        }
        tables = service.get_user_tables("user-2")
        assert len(tables) == 1
        assert tables[0]["table"] == "cmo_beta_records"

    def test_empty_user_id_raises(self, service):
        with pytest.raises(ValueError, match="user_id"):
            service.get_user_tables("")

    def test_lakeformation_error_raises(self, service, mock_clients):
        mock_clients["lakeformation"].list_permissions.side_effect = Exception("access denied")
        with pytest.raises(NLQueryError, match="permissions"):
            service.get_user_tables("user-1")

    def test_no_permissions_returns_empty(self, service, mock_clients):
        mock_clients["lakeformation"].list_permissions.return_value = {
            "PrincipalResourcePermissions": []
        }
        tables = service.get_user_tables("user-1")
        assert tables == []


# ------------------------------------------------------------------
# build_schema_context
# ------------------------------------------------------------------

class TestBuildSchemaContext:
    def test_builds_context_from_glue_catalog(self, service, mock_clients):
        mock_clients["glue"].get_table.return_value = {
            "Table": {
                "StorageDescriptor": {
                    "Columns": [
                        {"Name": "batch_id", "Type": "string"},
                        {"Name": "quantity", "Type": "double"},
                    ]
                },
                "PartitionKeys": [
                    {"Name": "year", "Type": "string"},
                ],
            }
        }

        tables = [{"database": "cmo_data_lake", "table": "cmo_alpha_batch"}]
        ctx = service.build_schema_context(tables)

        assert "cmo_data_lake.cmo_alpha_batch" in ctx
        assert "batch_id (string)" in ctx
        assert "quantity (double)" in ctx
        assert "year (string) [partition key]" in ctx

    def test_handles_glue_error_gracefully(self, service, mock_clients):
        mock_clients["glue"].get_table.side_effect = Exception("not found")

        tables = [{"database": "db", "table": "missing_table"}]
        ctx = service.build_schema_context(tables)

        assert "db.missing_table" in ctx
        assert "unavailable" in ctx

    def test_empty_tables_returns_empty(self, service):
        assert service.build_schema_context([]) == ""

    def test_multiple_tables(self, service, mock_clients):
        mock_clients["glue"].get_table.return_value = {
            "Table": {
                "StorageDescriptor": {
                    "Columns": [{"Name": "id", "Type": "string"}]
                },
                "PartitionKeys": [],
            }
        }

        tables = [
            {"database": "db", "table": "table_a"},
            {"database": "db", "table": "table_b"},
        ]
        ctx = service.build_schema_context(tables)
        assert "db.table_a" in ctx
        assert "db.table_b" in ctx


# ------------------------------------------------------------------
# generate_sql
# ------------------------------------------------------------------

class TestGenerateSQL:
    def test_generates_sql_from_bedrock(self, service, mock_clients):
        mock_clients["bedrock"].invoke_model.return_value = _bedrock_response(
            "SELECT batch_id, quantity FROM cmo_data_lake.batch_records WHERE quantity > 100"
        )

        sql = service.generate_sql("Show batches over 100", "Table: batch_records\nColumns:\n  - batch_id (string)\n  - quantity (double)")
        assert sql.upper().startswith("SELECT")
        assert "batch_id" in sql

    def test_extracts_sql_from_code_block(self, service, mock_clients):
        mock_clients["bedrock"].invoke_model.return_value = _bedrock_response(
            "Here is the query:\n```sql\nSELECT * FROM records\n```"
        )

        sql = service.generate_sql("get all records", "Table: records")
        assert sql == "SELECT * FROM records"

    def test_empty_query_raises(self, service):
        with pytest.raises(ValueError, match="user_query"):
            service.generate_sql("", "some context")

    def test_empty_context_raises(self, service):
        with pytest.raises(ValueError, match="schema_context"):
            service.generate_sql("some query", "")

    def test_bedrock_error_raises(self, service, mock_clients):
        mock_clients["bedrock"].invoke_model.side_effect = Exception("throttled")
        with pytest.raises(NLQueryError, match="Bedrock SQL generation failed"):
            service.generate_sql("query", "context")

    def test_no_sql_in_response_raises(self, service, mock_clients):
        mock_clients["bedrock"].invoke_model.return_value = _bedrock_response(
            "I'm sorry, I cannot help with that."
        )
        with pytest.raises(NLQueryError, match="did not return a valid SQL"):
            service.generate_sql("query", "context")


# ------------------------------------------------------------------
# validate_sql
# ------------------------------------------------------------------

class TestValidateSQL:
    def test_valid_select_passes(self, service):
        service.validate_sql("SELECT * FROM batch_records WHERE cmo_id = 'cmo-alpha'")

    def test_drop_raises(self, service):
        with pytest.raises(SQLValidationError, match="DROP"):
            service.validate_sql("DROP TABLE batch_records")

    def test_delete_raises(self, service):
        with pytest.raises(SQLValidationError, match="DELETE"):
            service.validate_sql("DELETE FROM batch_records WHERE 1=1")

    def test_insert_raises(self, service):
        with pytest.raises(SQLValidationError, match="INSERT"):
            service.validate_sql("INSERT INTO batch_records VALUES ('x')")

    def test_update_raises(self, service):
        with pytest.raises(SQLValidationError, match="UPDATE"):
            service.validate_sql("UPDATE batch_records SET quantity = 0")

    def test_truncate_raises(self, service):
        with pytest.raises(SQLValidationError, match="TRUNCATE"):
            service.validate_sql("TRUNCATE TABLE batch_records")

    def test_alter_raises(self, service):
        with pytest.raises(SQLValidationError, match="ALTER"):
            service.validate_sql("ALTER TABLE batch_records ADD COLUMN x INT")

    def test_create_raises(self, service):
        with pytest.raises(SQLValidationError, match="CREATE"):
            service.validate_sql("CREATE TABLE evil (id INT)")

    def test_non_select_raises(self, service):
        with pytest.raises(SQLValidationError, match="SELECT statement"):
            service.validate_sql("SHOW TABLES")

    def test_empty_sql_raises(self, service):
        with pytest.raises(ValueError, match="sql"):
            service.validate_sql("")

    def test_case_insensitive_detection(self, service):
        with pytest.raises(SQLValidationError, match="DROP"):
            service.validate_sql("drop table batch_records")

    def test_select_with_comment_passes(self, service):
        sql = "-- get all batches\nSELECT * FROM batch_records"
        service.validate_sql(sql)


# ------------------------------------------------------------------
# execute_query
# ------------------------------------------------------------------

class TestExecuteQuery:
    def test_successful_query_returns_results(self, service, mock_clients):
        mock_clients["athena"].start_query_execution.return_value = {
            "QueryExecutionId": "qe-123"
        }
        mock_clients["athena"].get_query_execution.return_value = {
            "QueryExecution": {"Status": {"State": "SUCCEEDED"}}
        }
        mock_clients["athena"].get_query_results.return_value = _athena_results(
            ["batch_id", "quantity"],
            [["B001", "100"], ["B002", "200"]],
        )

        results, exec_id = service.execute_query("SELECT * FROM batch_records")
        assert exec_id == "qe-123"
        assert len(results) == 2
        assert results[0]["batch_id"] == "B001"
        assert results[1]["quantity"] == "200"

    def test_failed_query_raises(self, service, mock_clients):
        mock_clients["athena"].start_query_execution.return_value = {
            "QueryExecutionId": "qe-fail"
        }
        mock_clients["athena"].get_query_execution.return_value = {
            "QueryExecution": {
                "Status": {
                    "State": "FAILED",
                    "StateChangeReason": "SYNTAX_ERROR near line 1",
                }
            }
        }

        with pytest.raises(NLQueryError, match="SYNTAX_ERROR"):
            service.execute_query("SELECT * FORM typo")

    def test_cancelled_query_raises(self, service, mock_clients):
        mock_clients["athena"].start_query_execution.return_value = {
            "QueryExecutionId": "qe-cancel"
        }
        mock_clients["athena"].get_query_execution.return_value = {
            "QueryExecution": {"Status": {"State": "CANCELLED"}}
        }

        with pytest.raises(NLQueryError, match="cancelled"):
            service.execute_query("SELECT 1")

    def test_empty_results(self, service, mock_clients):
        mock_clients["athena"].start_query_execution.return_value = {
            "QueryExecutionId": "qe-empty"
        }
        mock_clients["athena"].get_query_execution.return_value = {
            "QueryExecution": {"Status": {"State": "SUCCEEDED"}}
        }
        mock_clients["athena"].get_query_results.return_value = {
            "ResultSet": {"Rows": []}
        }

        results, _ = service.execute_query("SELECT * FROM empty_table")
        assert results == []

    def test_empty_sql_raises(self, service):
        with pytest.raises(ValueError, match="sql"):
            service.execute_query("")

    def test_start_execution_error_raises(self, service, mock_clients):
        mock_clients["athena"].start_query_execution.side_effect = Exception("access denied")
        with pytest.raises(NLQueryError, match="start Athena query"):
            service.execute_query("SELECT 1")

    @patch("services.nl_query_service.time")
    def test_timeout_raises(self, mock_time, service, mock_clients):
        mock_clients["athena"].start_query_execution.return_value = {
            "QueryExecutionId": "qe-slow"
        }
        mock_clients["athena"].get_query_execution.return_value = {
            "QueryExecution": {"Status": {"State": "RUNNING"}}
        }
        # Simulate time passing beyond timeout
        mock_time.time.side_effect = [0, 0, 1, 2, 3, 4, 5, 6, 7]
        mock_time.sleep = MagicMock()

        with pytest.raises(QueryTimeoutError, match="timed out"):
            service.execute_query("SELECT * FROM big_table")


# ------------------------------------------------------------------
# format_response
# ------------------------------------------------------------------

class TestFormatResponse:
    def test_formats_results_via_bedrock(self, service, mock_clients):
        mock_clients["bedrock"].invoke_model.return_value = _bedrock_response(
            "There were 2 batches: B001 with 100 units and B002 with 200 units."
        )

        results = [
            {"batch_id": "B001", "quantity": "100"},
            {"batch_id": "B002", "quantity": "200"},
        ]
        response = service.format_response("How many batches?", results)
        assert "B001" in response or "2 batches" in response or "batches" in response.lower()

    def test_empty_results_returns_no_results_message(self, service):
        response = service.format_response("query", [])
        assert "no results" in response.lower()

    def test_bedrock_failure_uses_fallback(self, service, mock_clients):
        mock_clients["bedrock"].invoke_model.side_effect = Exception("throttled")

        results = [{"batch_id": "B001", "quantity": "100"}]
        response = service.format_response("query", results)
        assert "1 result" in response

    def test_empty_query_raises(self, service):
        with pytest.raises(ValueError, match="user_query"):
            service.format_response("", [{"a": "1"}])

    def test_large_results_truncated_in_prompt(self, service, mock_clients):
        mock_clients["bedrock"].invoke_model.return_value = _bedrock_response(
            "Found many results."
        )
        results = [{"id": str(i)} for i in range(100)]
        response = service.format_response("query", results)
        assert response  # Should not error


# ------------------------------------------------------------------
# _extract_sql (static helper)
# ------------------------------------------------------------------

class TestExtractSQL:
    def test_plain_select(self):
        assert NLQueryService._extract_sql("SELECT * FROM t") == "SELECT * FROM t"

    def test_code_block(self):
        raw = "```sql\nSELECT id FROM t\n```"
        assert NLQueryService._extract_sql(raw) == "SELECT id FROM t"

    def test_code_block_no_lang(self):
        raw = "```\nSELECT id FROM t\n```"
        assert NLQueryService._extract_sql(raw) == "SELECT id FROM t"

    def test_select_in_text(self):
        raw = "Here is the query: SELECT id FROM t WHERE x = 1"
        result = NLQueryService._extract_sql(raw)
        assert result.startswith("SELECT")

    def test_no_sql_returns_empty(self):
        assert NLQueryService._extract_sql("I cannot help with that.") == ""

    def test_empty_input(self):
        assert NLQueryService._extract_sql("") == ""

    def test_none_input(self):
        assert NLQueryService._extract_sql(None) == ""


# ------------------------------------------------------------------
# _fallback_format (static helper)
# ------------------------------------------------------------------

class TestFallbackFormat:
    def test_no_results(self):
        assert "no results" in NLQueryService._fallback_format([]).lower()

    def test_single_result(self):
        result = NLQueryService._fallback_format([{"batch_id": "B001", "qty": "10"}])
        assert "1 result" in result
        assert "batch_id" in result

    def test_multiple_results(self):
        results = [{"a": "1"}, {"a": "2"}, {"a": "3"}]
        result = NLQueryService._fallback_format(results)
        assert "3 results" in result


# ------------------------------------------------------------------
# process_query (end-to-end)
# ------------------------------------------------------------------

class TestProcessQuery:
    def _setup_happy_path(self, mock_clients):
        """Wire up all mocks for a successful end-to-end query."""
        # Lake Formation: user has access to one table
        mock_clients["lakeformation"].list_permissions.return_value = {
            "PrincipalResourcePermissions": [
                {
                    "Resource": {
                        "Table": {
                            "DatabaseName": "cmo_data_lake",
                            "Name": "cmo_alpha_batch_records_silver",
                        }
                    },
                    "Permissions": ["SELECT"],
                }
            ]
        }
        # Glue: table schema
        mock_clients["glue"].get_table.return_value = {
            "Table": {
                "StorageDescriptor": {
                    "Columns": [
                        {"Name": "batch_id", "Type": "string"},
                        {"Name": "quantity", "Type": "double"},
                    ]
                },
                "PartitionKeys": [],
            }
        }
        # Bedrock: SQL generation
        sql = "SELECT batch_id, quantity FROM cmo_data_lake.cmo_alpha_batch_records_silver WHERE quantity > 100"
        mock_clients["bedrock"].invoke_model.side_effect = [
            _bedrock_response(sql),
            _bedrock_response("There are 2 batches with quantity over 100."),
        ]
        # Athena: execution
        mock_clients["athena"].start_query_execution.return_value = {
            "QueryExecutionId": "qe-e2e"
        }
        mock_clients["athena"].get_query_execution.return_value = {
            "QueryExecution": {"Status": {"State": "SUCCEEDED"}}
        }
        mock_clients["athena"].get_query_results.return_value = _athena_results(
            ["batch_id", "quantity"],
            [["B001", "150"], ["B002", "250"]],
        )

    def test_happy_path(self, service, mock_clients):
        self._setup_happy_path(mock_clients)

        result = service.process_query(
            "Show batches with quantity over 100",
            "arn:aws:iam::123:user/analyst",
        )

        assert result["query"] == "Show batches with quantity over 100"
        assert result["sql"] is not None
        assert "SELECT" in result["sql"].upper()
        assert len(result["results"]) == 2
        assert result["response"]
        assert result["query_execution_id"] == "qe-e2e"

    def test_no_access_returns_message(self, service, mock_clients):
        mock_clients["lakeformation"].list_permissions.return_value = {
            "PrincipalResourcePermissions": []
        }

        result = service.process_query("query", "user-no-access")
        assert result["sql"] is None
        assert result["results"] == []
        assert "do not have access" in result["response"].lower()

    def test_empty_query_raises(self, service):
        with pytest.raises(ValueError, match="user_query"):
            service.process_query("", "user-1")

    def test_empty_user_raises(self, service):
        with pytest.raises(ValueError, match="user_id"):
            service.process_query("query", "")

    def test_sql_validation_failure_propagates(self, service, mock_clients):
        mock_clients["lakeformation"].list_permissions.return_value = {
            "PrincipalResourcePermissions": [
                {
                    "Resource": {
                        "Table": {"DatabaseName": "db", "Name": "t"}
                    },
                    "Permissions": ["SELECT"],
                }
            ]
        }
        mock_clients["glue"].get_table.return_value = {
            "Table": {
                "StorageDescriptor": {"Columns": [{"Name": "id", "Type": "string"}]},
                "PartitionKeys": [],
            }
        }
        mock_clients["bedrock"].invoke_model.return_value = _bedrock_response(
            "```sql\nDROP TABLE t\n```"
        )

        with pytest.raises(SQLValidationError, match="DROP"):
            service.process_query("delete everything", "user-1")
