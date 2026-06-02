"""
Unit Tests for Schema Registry Service and Lambda Handler

Task 2.1: Create Lambda function for schema registration with AWS Glue Schema Registry
- Tests register_schema() supporting AVRO and JSON Schema formats
- Tests get_schema() with version support
- Tests Lambda handler routing for POST and GET
- Requirements: 2.2, 2.3
"""
import json
import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError

from services.schema_registry_service import (
    SchemaRegistryService,
    SchemaRegistryError,
    SchemaNotFoundError,
    SchemaValidationError,
    SUPPORTED_FORMATS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_AVRO_SCHEMA = {
    "type": "record",
    "name": "BatchRecord",
    "namespace": "com.merck.cmo.alpha",
    "fields": [
        {"name": "batch_id", "type": "string"},
        {"name": "product_name", "type": "string"},
        {"name": "quantity", "type": "double"},
    ],
}

SAMPLE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "batch_id": {"type": "string"},
        "product_name": {"type": "string"},
        "quantity": {"type": "number"},
    },
    "required": ["batch_id", "product_name"],
}


@pytest.fixture
def mock_glue():
    """Return a MagicMock standing in for the boto3 Glue client."""
    return MagicMock()


@pytest.fixture
def service(mock_glue):
    """Return a SchemaRegistryService wired to the mock Glue client."""
    return SchemaRegistryService(
        registry_name="pharma-data-exchange",
        glue_client=mock_glue,
    )


# ---------------------------------------------------------------------------
# register_schema – happy paths
# ---------------------------------------------------------------------------

class TestRegisterSchema:
    """Tests for SchemaRegistryService.register_schema()"""

    def test_register_new_avro_schema(self, service, mock_glue):
        """Register a brand-new AVRO schema returns a version ID."""
        mock_glue.create_schema.return_value = {
            "SchemaVersionId": "version-abc-123",
        }

        version_id = service.register_schema(
            schema_name="cmo-alpha-batch-records",
            schema_definition=SAMPLE_AVRO_SCHEMA,
            data_format="AVRO",
        )

        assert version_id == "version-abc-123"
        mock_glue.create_schema.assert_called_once()
        call_kwargs = mock_glue.create_schema.call_args[1]
        assert call_kwargs["SchemaName"] == "cmo-alpha-batch-records"
        assert call_kwargs["DataFormat"] == "AVRO"

    def test_register_new_json_schema(self, service, mock_glue):
        """Register a brand-new JSON schema returns a version ID."""
        mock_glue.create_schema.return_value = {
            "SchemaVersionId": "version-json-456",
        }

        version_id = service.register_schema(
            schema_name="cmo-beta-quality-data",
            schema_definition=SAMPLE_JSON_SCHEMA,
            data_format="JSON",
        )

        assert version_id == "version-json-456"
        call_kwargs = mock_glue.create_schema.call_args[1]
        assert call_kwargs["DataFormat"] == "JSON"

    def test_register_existing_schema_adds_version(self, service, mock_glue):
        """When schema already exists, a new version is registered."""
        mock_glue.create_schema.side_effect = ClientError(
            {"Error": {"Code": "AlreadyExistsException", "Message": "exists"}},
            "CreateSchema",
        )
        mock_glue.register_schema_version.return_value = {
            "SchemaVersionId": "version-v2-789",
        }

        version_id = service.register_schema(
            schema_name="cmo-alpha-batch-records",
            schema_definition=SAMPLE_AVRO_SCHEMA,
            data_format="AVRO",
        )

        assert version_id == "version-v2-789"
        mock_glue.register_schema_version.assert_called_once()

    def test_register_schema_unsupported_format_raises(self, service):
        """Unsupported data format raises SchemaValidationError."""
        with pytest.raises(SchemaValidationError, match="Unsupported data format"):
            service.register_schema(
                schema_name="test",
                schema_definition=SAMPLE_AVRO_SCHEMA,
                data_format="XML",
            )

    def test_register_schema_non_serializable_raises(self, service):
        """Non-JSON-serializable definition raises SchemaValidationError."""
        with pytest.raises(SchemaValidationError, match="not valid JSON"):
            service.register_schema(
                schema_name="test",
                schema_definition={"bad": set()},
                data_format="AVRO",
            )

    def test_register_schema_api_error_raises(self, service, mock_glue):
        """Unexpected AWS error raises SchemaRegistryError."""
        mock_glue.create_schema.side_effect = ClientError(
            {"Error": {"Code": "InternalServiceError", "Message": "boom"}},
            "CreateSchema",
        )

        with pytest.raises(SchemaRegistryError, match="Failed to register"):
            service.register_schema(
                schema_name="test",
                schema_definition=SAMPLE_AVRO_SCHEMA,
                data_format="AVRO",
            )


# ---------------------------------------------------------------------------
# get_schema – happy paths
# ---------------------------------------------------------------------------

class TestGetSchema:
    """Tests for SchemaRegistryService.get_schema()"""

    def test_get_latest_schema(self, service, mock_glue):
        """Retrieve the latest version of a schema."""
        mock_glue.get_schema_version.return_value = {
            "SchemaVersionId": "ver-latest",
            "SchemaDefinition": json.dumps(SAMPLE_AVRO_SCHEMA),
            "DataFormat": "AVRO",
            "VersionNumber": 3,
        }

        result = service.get_schema(schema_id="cmo-alpha-batch-records")

        assert result["schema_name"] == "cmo-alpha-batch-records"
        assert result["schema_version_id"] == "ver-latest"
        assert result["schema_definition"] == SAMPLE_AVRO_SCHEMA
        assert result["data_format"] == "AVRO"
        assert result["version_number"] == 3

        call_kwargs = mock_glue.get_schema_version.call_args[1]
        assert call_kwargs["SchemaVersionNumber"] == {"LatestVersion": True}

    def test_get_specific_version(self, service, mock_glue):
        """Retrieve a specific version of a schema."""
        mock_glue.get_schema_version.return_value = {
            "SchemaVersionId": "ver-1",
            "SchemaDefinition": json.dumps(SAMPLE_JSON_SCHEMA),
            "DataFormat": "JSON",
            "VersionNumber": 1,
        }

        result = service.get_schema(schema_id="cmo-beta-quality", version="1")

        assert result["version_number"] == 1
        assert result["data_format"] == "JSON"

        call_kwargs = mock_glue.get_schema_version.call_args[1]
        assert call_kwargs["SchemaVersionNumber"] == {"VersionNumber": 1}

    def test_get_schema_not_found_raises(self, service, mock_glue):
        """EntityNotFoundException maps to SchemaNotFoundError."""
        mock_glue.get_schema_version.side_effect = ClientError(
            {"Error": {"Code": "EntityNotFoundException", "Message": "nope"}},
            "GetSchemaVersion",
        )

        with pytest.raises(SchemaNotFoundError, match="not found"):
            service.get_schema(schema_id="nonexistent")

    def test_get_schema_api_error_raises(self, service, mock_glue):
        """Unexpected AWS error raises SchemaRegistryError."""
        mock_glue.get_schema_version.side_effect = ClientError(
            {"Error": {"Code": "InternalServiceError", "Message": "boom"}},
            "GetSchemaVersion",
        )

        with pytest.raises(SchemaRegistryError, match="Failed to retrieve"):
            service.get_schema(schema_id="test")


# ---------------------------------------------------------------------------
# Supported formats constant
# ---------------------------------------------------------------------------

class TestSupportedFormats:
    """Verify the SUPPORTED_FORMATS constant."""

    def test_avro_supported(self):
        assert "AVRO" in SUPPORTED_FORMATS

    def test_json_supported(self):
        assert "JSON" in SUPPORTED_FORMATS

    def test_only_two_formats(self):
        assert len(SUPPORTED_FORMATS) == 2


# ---------------------------------------------------------------------------
# Lambda handler tests
# ---------------------------------------------------------------------------

class TestLambdaHandler:
    """Tests for the Lambda handler routing and responses."""

    @pytest.fixture(autouse=True)
    def _patch_service(self, mock_glue):
        """Patch the module-level _service in the handler module."""
        with patch(
            "lambdas.schema_registry.handler._service"
        ) as patched:
            self.mock_service = patched
            yield

    def _invoke(self, event):
        from lambdas.schema_registry.handler import handler
        return handler(event, None)

    # -- POST (register) --

    def test_post_register_success(self):
        self.mock_service.register_schema.return_value = "ver-new"

        resp = self._invoke({
            "httpMethod": "POST",
            "body": json.dumps({
                "schema_name": "test-schema",
                "schema_definition": SAMPLE_AVRO_SCHEMA,
                "data_format": "AVRO",
            }),
        })

        assert resp["statusCode"] == 201
        body = json.loads(resp["body"])
        assert body["schema_version_id"] == "ver-new"

    def test_post_missing_fields(self):
        resp = self._invoke({
            "httpMethod": "POST",
            "body": json.dumps({"schema_name": "only-name"}),
        })

        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert "Missing required fields" in body["error"]

    def test_post_invalid_body(self):
        resp = self._invoke({
            "httpMethod": "POST",
            "body": "not-json",
        })

        assert resp["statusCode"] == 400

    def test_post_validation_error(self):
        self.mock_service.register_schema.side_effect = SchemaValidationError("bad format")

        resp = self._invoke({
            "httpMethod": "POST",
            "body": json.dumps({
                "schema_name": "s",
                "schema_definition": {},
                "data_format": "XML",
            }),
        })

        assert resp["statusCode"] == 400

    def test_post_registry_error(self):
        self.mock_service.register_schema.side_effect = SchemaRegistryError("aws boom")

        resp = self._invoke({
            "httpMethod": "POST",
            "body": json.dumps({
                "schema_name": "s",
                "schema_definition": {},
                "data_format": "AVRO",
            }),
        })

        assert resp["statusCode"] == 500

    # -- GET (retrieve) --

    def test_get_schema_success(self):
        self.mock_service.get_schema.return_value = {
            "schema_name": "test",
            "schema_version_id": "v1",
            "schema_definition": SAMPLE_AVRO_SCHEMA,
            "data_format": "AVRO",
            "version_number": 1,
        }

        resp = self._invoke({
            "httpMethod": "GET",
            "pathParameters": {"schemaId": "test"},
            "queryStringParameters": {"version": "1"},
        })

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["schema_name"] == "test"

    def test_get_schema_latest(self):
        self.mock_service.get_schema.return_value = {
            "schema_name": "test",
            "schema_version_id": "v-latest",
            "schema_definition": {},
            "data_format": "JSON",
            "version_number": 5,
        }

        resp = self._invoke({
            "httpMethod": "GET",
            "pathParameters": {"schemaId": "test"},
            "queryStringParameters": None,
        })

        assert resp["statusCode"] == 200
        self.mock_service.get_schema.assert_called_with(
            schema_id="test", version="latest"
        )

    def test_get_schema_missing_id(self):
        resp = self._invoke({
            "httpMethod": "GET",
            "pathParameters": {},
            "queryStringParameters": None,
        })

        assert resp["statusCode"] == 400

    def test_get_schema_not_found(self):
        self.mock_service.get_schema.side_effect = SchemaNotFoundError("nope")

        resp = self._invoke({
            "httpMethod": "GET",
            "pathParameters": {"schemaId": "missing"},
            "queryStringParameters": None,
        })

        assert resp["statusCode"] == 404

    # -- Unsupported method --

    def test_unsupported_method(self):
        resp = self._invoke({
            "httpMethod": "DELETE",
            "pathParameters": {},
        })

        assert resp["statusCode"] == 405


# ---------------------------------------------------------------------------
# validate_compatibility – Task 2.3
# Requirements: 2.7
# ---------------------------------------------------------------------------

class TestValidateCompatibility:
    """Tests for SchemaRegistryService.validate_compatibility()"""

    # -- Backward compatible change --

    def test_backward_compatible_change(self, service, mock_glue):
        """Adding an optional field is backward compatible."""
        # get_schema is called internally to find the data format
        mock_glue.get_schema_version.return_value = {
            "SchemaVersionId": "ver-1",
            "SchemaDefinition": json.dumps(SAMPLE_AVRO_SCHEMA),
            "DataFormat": "AVRO",
            "VersionNumber": 1,
        }
        mock_glue.check_schema_version_validity.return_value = {
            "Valid": True,
        }

        new_schema = {
            **SAMPLE_AVRO_SCHEMA,
            "fields": SAMPLE_AVRO_SCHEMA["fields"] + [
                {"name": "notes", "type": ["null", "string"], "default": None}
            ],
        }

        result = service.validate_compatibility(
            schema_name="cmo-alpha-batch-records",
            new_schema=new_schema,
            compatibility_mode="BACKWARD",
        )

        assert result["compatible"] is True
        assert result["compatibility_mode"] == "BACKWARD"
        assert "compatible" in result["message"].lower()
        mock_glue.check_schema_version_validity.assert_called_once()

    # -- Incompatible change --

    def test_incompatible_change(self, service, mock_glue):
        """Removing a required field is not backward compatible."""
        mock_glue.get_schema_version.return_value = {
            "SchemaVersionId": "ver-1",
            "SchemaDefinition": json.dumps(SAMPLE_AVRO_SCHEMA),
            "DataFormat": "AVRO",
            "VersionNumber": 1,
        }
        mock_glue.check_schema_version_validity.return_value = {
            "Valid": False,
            "Error": "Removed required field 'quantity'",
        }

        # Schema with a field removed
        new_schema = {
            **SAMPLE_AVRO_SCHEMA,
            "fields": [f for f in SAMPLE_AVRO_SCHEMA["fields"] if f["name"] != "quantity"],
        }

        result = service.validate_compatibility(
            schema_name="cmo-alpha-batch-records",
            new_schema=new_schema,
            compatibility_mode="BACKWARD",
        )

        assert result["compatible"] is False
        assert result["compatibility_mode"] == "BACKWARD"
        assert "NOT" in result["message"]

    # -- Forward compatibility --

    def test_forward_compatibility(self, service, mock_glue):
        """Forward compatibility mode is accepted and checked."""
        mock_glue.get_schema_version.return_value = {
            "SchemaVersionId": "ver-1",
            "SchemaDefinition": json.dumps(SAMPLE_JSON_SCHEMA),
            "DataFormat": "JSON",
            "VersionNumber": 1,
        }
        mock_glue.check_schema_version_validity.return_value = {
            "Valid": True,
        }

        result = service.validate_compatibility(
            schema_name="cmo-beta-quality",
            new_schema=SAMPLE_JSON_SCHEMA,
            compatibility_mode="FORWARD",
        )

        assert result["compatible"] is True
        assert result["compatibility_mode"] == "FORWARD"

    # -- Full compatibility --

    def test_full_compatibility(self, service, mock_glue):
        """Full compatibility mode is accepted and checked."""
        mock_glue.get_schema_version.return_value = {
            "SchemaVersionId": "ver-1",
            "SchemaDefinition": json.dumps(SAMPLE_AVRO_SCHEMA),
            "DataFormat": "AVRO",
            "VersionNumber": 1,
        }
        mock_glue.check_schema_version_validity.return_value = {
            "Valid": True,
        }

        result = service.validate_compatibility(
            schema_name="cmo-alpha-batch-records",
            new_schema=SAMPLE_AVRO_SCHEMA,
            compatibility_mode="FULL",
        )

        assert result["compatible"] is True
        assert result["compatibility_mode"] == "FULL"

    # -- Schema not found --

    def test_schema_not_found(self, service, mock_glue):
        """SchemaNotFoundError when the schema does not exist."""
        mock_glue.get_schema_version.side_effect = ClientError(
            {"Error": {"Code": "EntityNotFoundException", "Message": "nope"}},
            "GetSchemaVersion",
        )

        with pytest.raises(SchemaNotFoundError, match="not found"):
            service.validate_compatibility(
                schema_name="nonexistent",
                new_schema=SAMPLE_AVRO_SCHEMA,
            )

    # -- API error during compatibility check --

    def test_api_error_during_check(self, service, mock_glue):
        """SchemaRegistryError on unexpected AWS API failure."""
        mock_glue.get_schema_version.return_value = {
            "SchemaVersionId": "ver-1",
            "SchemaDefinition": json.dumps(SAMPLE_AVRO_SCHEMA),
            "DataFormat": "AVRO",
            "VersionNumber": 1,
        }
        mock_glue.check_schema_version_validity.side_effect = ClientError(
            {"Error": {"Code": "InternalServiceError", "Message": "boom"}},
            "CheckSchemaVersionValidity",
        )

        with pytest.raises(SchemaRegistryError, match="Failed to check compatibility"):
            service.validate_compatibility(
                schema_name="cmo-alpha-batch-records",
                new_schema=SAMPLE_AVRO_SCHEMA,
            )

    # -- Invalid compatibility mode --

    def test_invalid_compatibility_mode(self, service):
        """SchemaValidationError for unsupported compatibility mode."""
        with pytest.raises(SchemaValidationError, match="Unsupported compatibility mode"):
            service.validate_compatibility(
                schema_name="test",
                new_schema=SAMPLE_AVRO_SCHEMA,
                compatibility_mode="NONE",
            )

    # -- Default compatibility mode --

    def test_default_compatibility_mode_is_backward(self, service, mock_glue):
        """When no mode is specified, BACKWARD is used by default."""
        mock_glue.get_schema_version.return_value = {
            "SchemaVersionId": "ver-1",
            "SchemaDefinition": json.dumps(SAMPLE_AVRO_SCHEMA),
            "DataFormat": "AVRO",
            "VersionNumber": 1,
        }
        mock_glue.check_schema_version_validity.return_value = {
            "Valid": True,
        }

        result = service.validate_compatibility(
            schema_name="cmo-alpha-batch-records",
            new_schema=SAMPLE_AVRO_SCHEMA,
        )

        assert result["compatibility_mode"] == "BACKWARD"
