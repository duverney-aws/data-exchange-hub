"""
Natural Language Query Service

Converts natural language questions to SQL using Amazon Bedrock (Claude 3),
executes queries via Amazon Athena with Lake Formation access controls,
and formats results as natural language responses.

Requirements: 12.1, 12.2, 12.3, 12.4, 12.6
"""
import json
import logging
import re
import time
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

# SQL keywords that are forbidden in generated queries
FORBIDDEN_SQL_PATTERNS = [
    r"\bDROP\b",
    r"\bDELETE\b",
    r"\bTRUNCATE\b",
    r"\bALTER\b",
    r"\bCREATE\b",
    r"\bINSERT\b",
    r"\bUPDATE\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
    r"\bEXEC\b",
    r"\bEXECUTE\b",
    r"\bMERGE\b",
    r"\bCALL\b",
]

ATHENA_TERMINAL_STATES = {"SUCCEEDED", "FAILED", "CANCELLED"}
DEFAULT_QUERY_TIMEOUT_SECONDS = 30
DEFAULT_MAX_RESULTS = 1000
DEFAULT_DATABASE = "cmo_data_lake"
DEFAULT_WORKGROUP = "cmo-workgroup"
DEFAULT_RESULTS_BUCKET = "s3://athena-results/"
BEDROCK_MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"
BEDROCK_MAX_TOKENS_SQL = 1000
BEDROCK_MAX_TOKENS_FORMAT = 500


class NLQueryError(Exception):
    """Base exception for natural language query operations."""
    pass


class SQLValidationError(NLQueryError):
    """Raised when generated SQL contains forbidden operations."""
    pass


class QueryTimeoutError(NLQueryError):
    """Raised when an Athena query exceeds the timeout."""
    pass


class NLQueryService:
    """
    Service for processing natural language queries against the CMO data lake.

    Integrates Amazon Bedrock for NL-to-SQL and response formatting,
    Amazon Athena for query execution, AWS Glue Data Catalog for schema
    context, and AWS Lake Formation for access control.
    """

    def __init__(
        self,
        bedrock_client=None,
        athena_client=None,
        glue_client=None,
        lakeformation_client=None,
        database: str = DEFAULT_DATABASE,
        workgroup: str = DEFAULT_WORKGROUP,
        results_location: str = DEFAULT_RESULTS_BUCKET,
        model_id: str = BEDROCK_MODEL_ID,
        query_timeout: int = DEFAULT_QUERY_TIMEOUT_SECONDS,
    ):
        self.bedrock = bedrock_client
        self.athena = athena_client
        self.glue = glue_client
        self.lakeformation = lakeformation_client
        self.database = database
        self.workgroup = workgroup
        self.results_location = results_location
        self.model_id = model_id
        self.query_timeout = query_timeout

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_query(self, user_query: str, user_id: str) -> dict:
        """
        Process a natural language query end-to-end.

        1. Retrieve user's accessible tables from Lake Formation
        2. Build schema context from Glue Data Catalog
        3. Generate SQL via Bedrock
        4. Validate SQL for safety
        5. Execute via Athena
        6. Format results as natural language

        Args:
            user_query: The natural language question.
            user_id: Principal ARN or identifier for access control.

        Returns:
            dict with keys: query, sql, results, response, query_execution_id

        Raises:
            ValueError: If inputs are invalid.
            NLQueryError: If any processing step fails.
        """
        if not user_query or not user_query.strip():
            raise ValueError("user_query is required")
        if not user_id or not user_id.strip():
            raise ValueError("user_id is required")

        user_query = user_query.strip()

        try:
            accessible_tables = self.get_user_tables(user_id)
            if not accessible_tables:
                return {
                    "query": user_query,
                    "sql": None,
                    "results": [],
                    "response": "You do not have access to any data tables. Please contact your administrator to request access.",
                    "query_execution_id": None,
                }

            schema_context = self.build_schema_context(accessible_tables)
            sql = self.generate_sql(user_query, schema_context)
            self.validate_sql(sql)
            results, execution_id = self.execute_query(sql)
            response = self.format_response(user_query, results)

            return {
                "query": user_query,
                "sql": sql,
                "results": results,
                "response": response,
                "query_execution_id": execution_id,
            }
        except (ValueError, SQLValidationError):
            raise
        except NLQueryError:
            raise
        except Exception as exc:
            raise NLQueryError(f"Failed to process query: {exc}") from exc

    def get_user_tables(self, user_id: str) -> list:
        """
        Get the list of tables a user has access to via Lake Formation.

        Args:
            user_id: Principal ARN or identifier.

        Returns:
            List of dicts with 'database' and 'table' keys.
        """
        if not user_id:
            raise ValueError("user_id is required")

        # Only call Lake Formation if user_id is a full IAM ARN
        if user_id.startswith("arn:aws:"):
            try:
                response = self.lakeformation.list_permissions(
                    Principal={"DataLakePrincipalIdentifier": user_id}
                )
                tables = []
                for entry in response.get("PrincipalResourcePermissions", []):
                    resource = entry.get("Resource", {})
                    table_info = resource.get("Table") or resource.get("TableWithColumns")
                    if table_info:
                        db = table_info.get("DatabaseName", self.database)
                        tbl = table_info.get("Name", "")
                        if tbl and tbl != "ALL_TABLES":
                            tables.append({"database": db, "table": tbl})
                return tables
            except Exception as exc:
                raise NLQueryError(
                    f"Failed to retrieve user permissions: {exc}"
                ) from exc

        # For non-ARN identifiers, fall back to all tables in the Glue catalog
        try:
            response = self.glue.get_tables(DatabaseName=self.database)
            return [
                {"database": self.database, "table": t["Name"]}
                for t in response.get("TableList", [])
            ]
        except Exception:
            return []

    def build_schema_context(self, tables: list) -> str:
        """
        Build a schema description string from Glue Data Catalog metadata.

        Args:
            tables: List of dicts with 'database' and 'table' keys.

        Returns:
            Formatted string describing available tables and columns.
        """
        if not tables:
            return ""

        context_parts = []
        for tbl in tables:
            db_name = tbl["database"]
            tbl_name = tbl["table"]
            try:
                resp = self.glue.get_table(
                    DatabaseName=db_name, Name=tbl_name
                )
                table_def = resp.get("Table", {})
                columns = table_def.get("StorageDescriptor", {}).get("Columns", [])
                partition_keys = table_def.get("PartitionKeys", [])

                col_lines = []
                for col in columns:
                    col_lines.append(f"  - {col['Name']} ({col['Type']})")
                for pk in partition_keys:
                    col_lines.append(f"  - {pk['Name']} ({pk['Type']}) [partition key]")

                cols_str = "\n".join(col_lines) if col_lines else "  (no columns)"
                context_parts.append(
                    f"Table: {db_name}.{tbl_name}\nColumns:\n{cols_str}"
                )
            except Exception as exc:
                logger.warning(
                    "Failed to get schema for %s.%s: %s", db_name, tbl_name, exc
                )
                context_parts.append(f"Table: {db_name}.{tbl_name}\nColumns: (unavailable)")

        return "\n\n".join(context_parts)

    def generate_sql(self, user_query: str, schema_context: str) -> str:
        """
        Use Amazon Bedrock (Claude 3) to convert a natural language query to SQL.

        Args:
            user_query: The natural language question.
            schema_context: Formatted string of available tables and columns.

        Returns:
            Generated SQL string.

        Raises:
            NLQueryError: If Bedrock invocation fails or returns no SQL.
        """
        if not user_query:
            raise ValueError("user_query is required")
        if not schema_context:
            raise ValueError("schema_context is required")

        prompt = (
            "You are a SQL expert for a pharmaceutical data lake on Amazon Athena. "
            "Convert the following natural language query to a valid SQL SELECT statement.\n\n"
            f"Available tables and columns:\n{schema_context}\n\n"
            f"User question: {user_query}\n\n"
            "Rules:\n"
            "- Only use tables and columns listed above.\n"
            "- Only generate SELECT statements. Never generate DROP, DELETE, INSERT, UPDATE, ALTER, or CREATE.\n"
            "- Use standard SQL compatible with Amazon Athena (Presto/Trino).\n"
            "- If the question is ambiguous, generate the most reasonable interpretation.\n"
            "- Return ONLY the SQL query, no explanation.\n"
        )

        try:
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": BEDROCK_MAX_TOKENS_SQL,
            })
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                body=body,
            )
            response_body = json.loads(response["body"].read())
            raw_text = response_body.get("content", [{}])[0].get("text", "")
        except Exception as exc:
            raise NLQueryError(f"Bedrock SQL generation failed: {exc}") from exc

        sql = self._extract_sql(raw_text)
        if not sql:
            raise NLQueryError(
                "Bedrock did not return a valid SQL query. "
                "Please rephrase your question."
            )
        return sql

    def validate_sql(self, sql: str) -> None:
        """
        Validate that generated SQL does not contain forbidden operations.

        Args:
            sql: The SQL string to validate.

        Raises:
            SQLValidationError: If forbidden patterns are found.
            ValueError: If sql is empty.
        """
        if not sql or not sql.strip():
            raise ValueError("sql is required")

        upper_sql = sql.upper()
        for pattern in FORBIDDEN_SQL_PATTERNS:
            if re.search(pattern, upper_sql):
                keyword = re.search(pattern, upper_sql).group()
                raise SQLValidationError(
                    f"Generated SQL contains forbidden operation: {keyword}"
                )

        # Must start with SELECT (after optional whitespace/comments)
        stripped = re.sub(r"^\s*--[^\n]*\n", "", sql, flags=re.MULTILINE).strip()
        if not stripped.upper().startswith("SELECT"):
            raise SQLValidationError(
                "Generated SQL must be a SELECT statement"
            )

    def execute_query(self, sql: str) -> tuple:
        """
        Execute SQL via Amazon Athena with Lake Formation access controls.

        Args:
            sql: The SQL query to execute.

        Returns:
            Tuple of (results_list, query_execution_id).
            results_list is a list of dicts (column_name -> value).

        Raises:
            QueryTimeoutError: If the query exceeds the timeout.
            NLQueryError: If execution fails.
        """
        if not sql or not sql.strip():
            raise ValueError("sql is required")

        try:
            start_resp = self.athena.start_query_execution(
                QueryString=sql,
                QueryExecutionContext={"Database": self.database},
                ResultConfiguration={"OutputLocation": self.results_location},
                WorkGroup=self.workgroup,
            )
            execution_id = start_resp["QueryExecutionId"]
        except Exception as exc:
            raise NLQueryError(f"Failed to start Athena query: {exc}") from exc

        # Poll for completion
        state = self._wait_for_query(execution_id)

        if state == "FAILED":
            reason = self._get_failure_reason(execution_id)
            raise NLQueryError(f"Athena query failed: {reason}")
        if state == "CANCELLED":
            raise NLQueryError("Athena query was cancelled")

        # Fetch results
        try:
            results = self._fetch_results(execution_id)
        except NLQueryError:
            raise
        except Exception as exc:
            raise NLQueryError(f"Failed to fetch query results: {exc}") from exc

        return results, execution_id

    def format_response(self, user_query: str, results: list) -> str:
        """
        Use Amazon Bedrock to format query results as a natural language response.

        Args:
            user_query: The original natural language question.
            results: List of result dicts from Athena.

        Returns:
            Natural language response string.
        """
        if not user_query:
            raise ValueError("user_query is required")

        if not results:
            return "No results were found for your query."

        # Truncate results for the prompt to avoid token limits
        display_results = results[:50]
        results_json = json.dumps(display_results, indent=2, default=str)
        truncation_note = ""
        if len(results) > 50:
            truncation_note = f"\n(Showing 50 of {len(results)} total results)"

        prompt = (
            "You are a helpful data analyst for a pharmaceutical company. "
            "A user asked a question and received query results from the data lake.\n\n"
            f"User question: {user_query}\n\n"
            f"Query results:\n{results_json}{truncation_note}\n\n"
            "Provide a clear, concise natural language answer to the user's question "
            "based on these results. Highlight key numbers and trends. "
            "If the data is insufficient to fully answer the question, say so."
        )

        try:
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": BEDROCK_MAX_TOKENS_FORMAT,
            })
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                body=body,
            )
            response_body = json.loads(response["body"].read())
            text = response_body.get("content", [{}])[0].get("text", "")
            return text.strip() if text else "Unable to format the response."
        except Exception as exc:
            logger.warning("Bedrock response formatting failed: %s", exc)
            # Graceful fallback: return a simple summary
            return self._fallback_format(results)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_sql(raw_text: str) -> str:
        """Extract SQL from Bedrock response, handling markdown code blocks."""
        if not raw_text:
            return ""

        # Try to extract from ```sql ... ``` block
        match = re.search(r"```(?:sql)?\s*\n?(.*?)```", raw_text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # Otherwise treat the whole response as SQL if it looks like a SELECT
        stripped = raw_text.strip()
        if stripped.upper().startswith("SELECT"):
            return stripped

        # Try to find a SELECT statement anywhere in the text
        select_match = re.search(r"(SELECT\b.*)", stripped, re.DOTALL | re.IGNORECASE)
        if select_match:
            return select_match.group(1).strip()

        return ""

    def _wait_for_query(self, execution_id: str) -> str:
        """Poll Athena until the query reaches a terminal state or times out."""
        deadline = time.time() + self.query_timeout
        poll_interval = 0.5

        while time.time() < deadline:
            try:
                resp = self.athena.get_query_execution(
                    QueryExecutionId=execution_id
                )
                state = resp["QueryExecution"]["Status"]["State"]
                if state in ATHENA_TERMINAL_STATES:
                    return state
            except Exception as exc:
                raise NLQueryError(
                    f"Failed to check query status: {exc}"
                ) from exc
            time.sleep(poll_interval)
            poll_interval = min(poll_interval * 1.5, 5)

        raise QueryTimeoutError(
            f"Athena query {execution_id} timed out after {self.query_timeout}s"
        )

    def _get_failure_reason(self, execution_id: str) -> str:
        """Get the failure reason for a failed Athena query."""
        try:
            resp = self.athena.get_query_execution(
                QueryExecutionId=execution_id
            )
            return resp["QueryExecution"]["Status"].get(
                "StateChangeReason", "Unknown error"
            )
        except Exception:
            return "Unknown error"

    def _fetch_results(self, execution_id: str) -> list:
        """Fetch and parse Athena query results into a list of dicts."""
        try:
            resp = self.athena.get_query_results(
                QueryExecutionId=execution_id,
                MaxResults=DEFAULT_MAX_RESULTS,
            )
        except Exception as exc:
            raise NLQueryError(f"Failed to fetch results: {exc}") from exc

        rows = resp.get("ResultSet", {}).get("Rows", [])
        if len(rows) < 1:
            return []

        # First row is the header
        headers = [
            col.get("VarCharValue", f"col_{i}")
            for i, col in enumerate(rows[0].get("Data", []))
        ]

        results = []
        for row in rows[1:]:
            values = row.get("Data", [])
            record = {}
            for i, val in enumerate(values):
                col_name = headers[i] if i < len(headers) else f"col_{i}"
                record[col_name] = val.get("VarCharValue")
            results.append(record)

        return results

    @staticmethod
    def _fallback_format(results: list) -> str:
        """Simple fallback formatting when Bedrock is unavailable."""
        count = len(results)
        if count == 0:
            return "No results found."
        if count == 1:
            row = results[0]
            parts = [f"{k}: {v}" for k, v in row.items() if v is not None]
            return f"Found 1 result: {', '.join(parts)}"
        return f"Found {count} results. The first record contains: {', '.join(results[0].keys())}."
