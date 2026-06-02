"""
Schema Registry Service

Wraps AWS Glue Schema Registry API for schema registration and retrieval.
Supports AVRO and JSON Schema formats with version control.

Requirements: 2.2, 2.3, 3.1, 3.5
"""
import csv
import io
import json
import logging
from typing import Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Valid data formats supported by Glue Schema Registry
SUPPORTED_FORMATS = {'AVRO', 'JSON'}

# Supported file formats for schema inference
SUPPORTED_FILE_FORMATS = {'csv', 'json', 'parquet'}

# Default registry name for the pharma data exchange hub
DEFAULT_REGISTRY_NAME = 'pharma-data-exchange'


class SchemaRegistryError(Exception):
    """Base exception for schema registry operations."""
    pass


class SchemaValidationError(SchemaRegistryError):
    """Raised when schema format validation fails."""
    pass


class SchemaNotFoundError(SchemaRegistryError):
    """Raised when a schema or version is not found."""
    pass


class SchemaRegistryService:
    """
    Service for registering and retrieving schemas from AWS Glue Schema Registry.

    Supports AVRO and JSON Schema formats with version control.
    """

    def __init__(
        self,
        registry_name: str = DEFAULT_REGISTRY_NAME,
        glue_client=None,
    ):
        """
        Initialize the Schema Registry Service.

        Args:
            registry_name: Name of the Glue Schema Registry.
            glue_client: Optional pre-configured boto3 Glue client (useful for testing).
        """
        self.registry_name = registry_name
        self.glue_client = glue_client or boto3.client('glue')

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_schema(
        self,
        schema_name: str,
        schema_definition: dict,
        data_format: str,
    ) -> str:
        """
        Register a new schema or add a new version to an existing schema.

        Args:
            schema_name: Unique name for the schema (e.g. 'cmo-alpha-batch-records').
            schema_definition: Schema definition as a Python dict.
            data_format: Data format – must be 'AVRO' or 'JSON'.

        Returns:
            The schema version ID assigned by Glue Schema Registry.

        Raises:
            SchemaValidationError: If the data format is unsupported or the
                definition cannot be serialised to JSON.
            SchemaRegistryError: On unexpected AWS API errors.
        """
        self._validate_data_format(data_format)
        definition_str = self._serialize_definition(schema_definition)

        try:
            # Try to create a brand-new schema first.
            response = self.glue_client.create_schema(
                RegistryId={'RegistryName': self.registry_name},
                SchemaName=schema_name,
                DataFormat=data_format,
                Compatibility='BACKWARD',
                SchemaDefinition=definition_str,
            )
            schema_version_id = response.get('SchemaVersionId', '')
            logger.info(
                "Created new schema '%s' (version id: %s)",
                schema_name,
                schema_version_id,
            )
            return schema_version_id

        except ClientError as exc:
            error_code = exc.response['Error']['Code']

            if error_code == 'AlreadyExistsException':
                # Schema already exists – register a new version instead.
                return self._register_new_version(
                    schema_name, definition_str, data_format,
                )

            logger.error("Failed to create schema '%s': %s", schema_name, exc)
            raise SchemaRegistryError(
                f"Failed to register schema '{schema_name}': {exc}"
            ) from exc

    def get_schema(
        self,
        schema_id: str,
        version: str = 'latest',
    ) -> dict:
        """
        Retrieve a schema definition by name and version.

        Args:
            schema_id: The schema name in the registry.
            version: Version number (as string) or 'latest'.

        Returns:
            A dict with keys:
                - schema_name: str
                - schema_version_id: str
                - schema_definition: dict (parsed JSON)
                - data_format: str
                - version_number: int

        Raises:
            SchemaNotFoundError: If the schema or version does not exist.
            SchemaRegistryError: On unexpected AWS API errors.
        """
        try:
            if version == 'latest':
                response = self.glue_client.get_schema_version(
                    SchemaId={
                        'RegistryName': self.registry_name,
                        'SchemaName': schema_id,
                    },
                    SchemaVersionNumber={'LatestVersion': True},
                )
            else:
                response = self.glue_client.get_schema_version(
                    SchemaId={
                        'RegistryName': self.registry_name,
                        'SchemaName': schema_id,
                    },
                    SchemaVersionNumber={'VersionNumber': int(version)},
                )

            definition_str = response.get('SchemaDefinition', '{}')

            return {
                'schema_name': schema_id,
                'schema_version_id': response.get('SchemaVersionId', ''),
                'schema_definition': json.loads(definition_str),
                'data_format': response.get('DataFormat', ''),
                'version_number': response.get('VersionNumber', 0),
            }

        except ClientError as exc:
            error_code = exc.response['Error']['Code']
            if error_code in ('EntityNotFoundException', 'InvalidInputException'):
                raise SchemaNotFoundError(
                    f"Schema '{schema_id}' version '{version}' not found"
                ) from exc
            logger.error("Failed to get schema '%s': %s", schema_id, exc)
            raise SchemaRegistryError(
                f"Failed to retrieve schema '{schema_id}': {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Compatibility checking
    # ------------------------------------------------------------------

    # Valid compatibility modes for schema evolution
    VALID_COMPATIBILITY_MODES = {'BACKWARD', 'FORWARD', 'FULL'}

    def validate_compatibility(
        self,
        schema_name: str,
        new_schema: dict,
        compatibility_mode: str = 'BACKWARD',
    ) -> dict:
        """
        Check whether a new schema version is compatible with the existing schema.

        Uses the AWS Glue Schema Registry ``check_schema_version_validity``
        API to determine if *new_schema* can safely replace the current
        version of *schema_name* under the given *compatibility_mode*.

        Args:
            schema_name: Name of the existing schema in the registry.
            new_schema: Proposed new schema definition as a Python dict.
            compatibility_mode: One of ``'BACKWARD'``, ``'FORWARD'``, or
                ``'FULL'``.

        Returns:
            A dict with keys:
                - ``compatible`` (bool): Whether the new schema is compatible.
                - ``compatibility_mode`` (str): The mode that was checked.
                - ``message`` (str): Human-readable explanation.

        Raises:
            SchemaValidationError: If *compatibility_mode* is invalid or the
                schema definition cannot be serialised.
            SchemaNotFoundError: If *schema_name* does not exist in the
                registry.
            SchemaRegistryError: On unexpected AWS API errors.
        """
        # Validate the requested compatibility mode
        if compatibility_mode not in self.VALID_COMPATIBILITY_MODES:
            raise SchemaValidationError(
                f"Unsupported compatibility mode '{compatibility_mode}'. "
                f"Must be one of: {', '.join(sorted(self.VALID_COMPATIBILITY_MODES))}"
            )

        definition_str = self._serialize_definition(new_schema)

        # Retrieve the current schema to find its data format
        current = self.get_schema(schema_id=schema_name)
        data_format = current.get('data_format', 'JSON')

        try:
            response = self.glue_client.check_schema_version_validity(
                SchemaId={
                    'RegistryName': self.registry_name,
                    'SchemaName': schema_name,
                },
                DataFormat=data_format,
                SchemaDefinition=definition_str,
            )

            is_valid = response.get('Valid', False)

            if is_valid:
                message = (
                    f"Schema '{schema_name}' is {compatibility_mode} compatible "
                    f"with the proposed changes."
                )
            else:
                error_msg = response.get('Error', 'Unknown validation error')
                message = (
                    f"Schema '{schema_name}' is NOT {compatibility_mode} compatible: "
                    f"{error_msg}"
                )

            logger.info(
                "Compatibility check for '%s' (%s): valid=%s",
                schema_name,
                compatibility_mode,
                is_valid,
            )

            return {
                'compatible': is_valid,
                'compatibility_mode': compatibility_mode,
                'message': message,
            }

        except ClientError as exc:
            error_code = exc.response['Error']['Code']
            if error_code in ('EntityNotFoundException', 'InvalidInputException'):
                raise SchemaNotFoundError(
                    f"Schema '{schema_name}' not found in registry"
                ) from exc
            logger.error(
                "Compatibility check failed for '%s': %s", schema_name, exc,
            )
            raise SchemaRegistryError(
                f"Failed to check compatibility for '{schema_name}': {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Schema inference from sample data (Requirements: 3.1, 3.5)
    # ------------------------------------------------------------------

    def infer_schema_from_sample(
        self,
        sample_data: bytes,
        file_format: str,
    ) -> dict:
        """
        Infer a JSON Schema from raw sample data bytes.

        Args:
            sample_data: Raw file content as bytes.
            file_format: One of 'csv', 'json', or 'parquet'.

        Returns:
            A JSON Schema dict with inferred field names, types, and
            basic constraints (``required`` list for non-null fields).

        Raises:
            SchemaValidationError: If the file format is unsupported,
                the data is empty, or the data cannot be parsed.
        """
        fmt = file_format.lower().strip()
        if fmt not in SUPPORTED_FILE_FORMATS:
            raise SchemaValidationError(
                f"Unsupported file format '{file_format}'. "
                f"Must be one of: {', '.join(sorted(SUPPORTED_FILE_FORMATS))}"
            )

        if not sample_data:
            raise SchemaValidationError("Sample data is empty")

        try:
            if fmt == 'csv':
                return self._infer_csv_schema(sample_data)
            elif fmt == 'json':
                return self._infer_json_schema(sample_data)
            else:  # parquet
                return self._infer_parquet_schema(sample_data)
        except SchemaValidationError:
            raise
        except Exception as exc:
            raise SchemaValidationError(
                f"Failed to parse {fmt} data: {exc}"
            ) from exc

    def merge_schemas(self, schemas: list) -> dict:
        """
        Merge multiple inferred schemas into a single unified schema.

        Takes the union of all fields.  When the same field appears in
        multiple schemas with different types, the most general type is
        chosen (``string`` wins over everything else; ``number`` wins
        over ``integer``).

        Args:
            schemas: A list of JSON Schema dicts (as returned by
                ``infer_schema_from_sample``).

        Returns:
            A merged JSON Schema dict.

        Raises:
            SchemaValidationError: If the list is empty or contains
                invalid schemas.
        """
        if not schemas:
            raise SchemaValidationError("No schemas provided for merging")

        # Collect field info across all schemas
        merged_properties: dict = {}
        # Track how many schemas each field appears in
        field_counts: dict[str, int] = {}
        total = len(schemas)

        for schema in schemas:
            if not isinstance(schema, dict):
                raise SchemaValidationError(
                    "Each schema must be a dict"
                )
            props = schema.get('properties', {})
            for field_name, field_def in props.items():
                field_counts[field_name] = field_counts.get(field_name, 0) + 1
                if field_name not in merged_properties:
                    merged_properties[field_name] = dict(field_def)
                else:
                    # Resolve type conflicts
                    existing_type = merged_properties[field_name].get('type', 'string')
                    new_type = field_def.get('type', 'string')
                    merged_properties[field_name]['type'] = self._resolve_type_conflict(
                        existing_type, new_type,
                    )

        # Build required list: fields present in ALL schemas
        required = [
            name for name, count in field_counts.items()
            if count == total
        ]

        return {
            'type': 'object',
            'properties': merged_properties,
            'required': sorted(required),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    # -- Schema inference helpers --

    @staticmethod
    def _infer_csv_schema(data: bytes) -> dict:
        """Infer JSON Schema from CSV bytes."""
        text = data.decode('utf-8')
        reader = csv.reader(io.StringIO(text))
        try:
            headers = next(reader)
        except StopIteration:
            raise SchemaValidationError("CSV data has no header row")

        if not any(h.strip() for h in headers):
            raise SchemaValidationError("CSV data has no header row")

        # Collect sample rows (up to 100) for type inference
        rows: list[list[str]] = []
        for row in reader:
            rows.append(row)
            if len(rows) >= 100:
                break

        properties: dict = {}
        required: list[str] = []

        for col_idx, header in enumerate(headers):
            header = header.strip()
            if not header:
                continue
            col_values = [
                row[col_idx].strip()
                for row in rows
                if col_idx < len(row) and row[col_idx].strip()
            ]
            inferred = SchemaRegistryService._infer_column_type(col_values)
            properties[header] = {'type': inferred}
            # Mark as required if all sample rows have a non-empty value
            if col_values and len(col_values) == len(rows):
                required.append(header)

        return {
            'type': 'object',
            'properties': properties,
            'required': sorted(required),
        }

    @staticmethod
    def _infer_json_schema(data: bytes) -> dict:
        """Infer JSON Schema from JSON bytes (object or array of objects)."""
        text = data.decode('utf-8')
        parsed = json.loads(text)

        if isinstance(parsed, dict):
            records = [parsed]
        elif isinstance(parsed, list):
            if not parsed:
                raise SchemaValidationError("JSON array is empty")
            records = parsed
        else:
            raise SchemaValidationError(
                "JSON data must be an object or array of objects"
            )

        # Gather all keys and their value types across records
        field_types: dict[str, set] = {}
        field_counts: dict[str, int] = {}
        total = len(records)

        for record in records:
            if not isinstance(record, dict):
                continue
            for key, value in record.items():
                field_counts[key] = field_counts.get(key, 0) + 1
                if key not in field_types:
                    field_types[key] = set()
                field_types[key].add(
                    SchemaRegistryService._json_value_type(value)
                )

        properties: dict = {}
        required: list[str] = []

        for field, types in field_types.items():
            if len(types) == 1:
                properties[field] = {'type': types.pop()}
            else:
                # Multiple types observed – pick the most general
                resolved = 'string'
                if types <= {'integer', 'number'}:
                    resolved = 'number'
                properties[field] = {'type': resolved}
            if field_counts.get(field, 0) == total:
                required.append(field)

        return {
            'type': 'object',
            'properties': properties,
            'required': sorted(required),
        }

    @staticmethod
    def _infer_parquet_schema(data: bytes) -> dict:
        """Infer JSON Schema from Parquet bytes using pyarrow."""
        import pyarrow.parquet as pq

        buf = io.BytesIO(data)
        table = pq.read_table(buf)
        arrow_schema = table.schema

        type_map = {
            'int8': 'integer', 'int16': 'integer', 'int32': 'integer',
            'int64': 'integer', 'uint8': 'integer', 'uint16': 'integer',
            'uint32': 'integer', 'uint64': 'integer',
            'float': 'number', 'double': 'number',
            'float16': 'number', 'float32': 'number', 'float64': 'number',
            'bool': 'boolean',
            'string': 'string', 'utf8': 'string', 'large_string': 'string',
            'large_utf8': 'string',
            'date32': 'string', 'date64': 'string',
            'timestamp': 'string',
        }

        properties: dict = {}
        required: list[str] = []

        for field in arrow_schema:
            type_str = str(field.type)
            # Handle parameterised types like timestamp[ns]
            base_type = type_str.split('[')[0]
            json_type = type_map.get(base_type, 'string')
            properties[field.name] = {'type': json_type}
            if not field.nullable:
                required.append(field.name)

        return {
            'type': 'object',
            'properties': properties,
            'required': sorted(required),
        }

    @staticmethod
    def _infer_column_type(values: list[str]) -> str:
        """Infer the JSON Schema type for a list of string cell values."""
        if not values:
            return 'string'

        all_bool = True
        all_int = True
        all_number = True

        for v in values:
            low = v.lower()
            if low not in ('true', 'false', '0', '1'):
                all_bool = False
            try:
                int(v)
            except ValueError:
                all_int = False
            try:
                float(v)
            except ValueError:
                all_number = False

        if all_bool:
            return 'boolean'
        if all_int:
            return 'integer'
        if all_number:
            return 'number'
        return 'string'

    @staticmethod
    def _json_value_type(value) -> str:
        """Map a Python JSON value to a JSON Schema type string."""
        if isinstance(value, bool):
            return 'boolean'
        if isinstance(value, int):
            return 'integer'
        if isinstance(value, float):
            return 'number'
        if isinstance(value, str):
            return 'string'
        if isinstance(value, list):
            return 'array'
        if isinstance(value, dict):
            return 'object'
        if value is None:
            return 'string'  # treat null as string for schema purposes
        return 'string'

    @staticmethod
    def _resolve_type_conflict(type_a: str, type_b: str) -> str:
        """Pick the most general type when two schemas disagree."""
        if type_a == type_b:
            return type_a
        # string is the most general
        if 'string' in (type_a, type_b):
            return 'string'
        # number is more general than integer
        if {type_a, type_b} == {'integer', 'number'}:
            return 'number'
        # fallback
        return 'string'

    # -- Existing helpers --

    @staticmethod
    def _validate_data_format(data_format: str) -> None:
        """Raise SchemaValidationError if the format is not supported."""
        if data_format not in SUPPORTED_FORMATS:
            raise SchemaValidationError(
                f"Unsupported data format '{data_format}'. "
                f"Must be one of: {', '.join(sorted(SUPPORTED_FORMATS))}"
            )

    @staticmethod
    def _serialize_definition(schema_definition: dict) -> str:
        """Serialize a schema definition dict to a JSON string."""
        try:
            return json.dumps(schema_definition)
        except (TypeError, ValueError) as exc:
            raise SchemaValidationError(
                f"Schema definition is not valid JSON: {exc}"
            ) from exc

    def _register_new_version(
        self,
        schema_name: str,
        definition_str: str,
        data_format: str,
    ) -> str:
        """Register a new version for an existing schema."""
        try:
            response = self.glue_client.register_schema_version(
                SchemaId={
                    'RegistryName': self.registry_name,
                    'SchemaName': schema_name,
                },
                SchemaDefinition=definition_str,
            )
            schema_version_id = response.get('SchemaVersionId', '')
            logger.info(
                "Registered new version for schema '%s' (version id: %s)",
                schema_name,
                schema_version_id,
            )
            return schema_version_id

        except ClientError as exc:
            logger.error(
                "Failed to register new version for schema '%s': %s",
                schema_name,
                exc,
            )
            raise SchemaRegistryError(
                f"Failed to register new version for '{schema_name}': {exc}"
            ) from exc
