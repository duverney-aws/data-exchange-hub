"""
Lake Formation Service for Pharma Data Exchange Hub

Manages AWS Lake Formation access control for the CMO data lake.
Registers S3 locations, configures Glue Data Catalog database/table
permissions, and sets up data cell filters for row-level and
column-level security.

Requirements: 10.2
"""
import boto3
from typing import Optional


class LakeFormationService:
    """Service for managing Lake Formation access control per CMO."""

    DATABASE_NAME = "cmo_data_lake"
    DATA_CLASSIFICATION_LEVELS = ("public", "internal", "confidential", "restricted")

    def __init__(
        self,
        lakeformation_client=None,
        glue_client=None,
        region: str = "us-east-1",
    ):
        self.lf = lakeformation_client or boto3.client("lakeformation", region_name=region)
        self.glue = glue_client or boto3.client("glue", region_name=region)
        self.region = region

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_cmo_id(cmo_id: str) -> None:
        if not cmo_id or not cmo_id.startswith("cmo-"):
            raise ValueError(
                f"Invalid CMO ID format: {cmo_id}. Must start with 'cmo-'"
            )

    # ------------------------------------------------------------------
    # S3 Location Registration
    # ------------------------------------------------------------------

    def register_s3_location(self, s3_arn: str, role_arn: str) -> dict:
        """
        Register an S3 location with Lake Formation.

        Args:
            s3_arn: ARN of the S3 path (e.g. arn:aws:s3:::bucket/bronze/)
            role_arn: IAM role ARN that Lake Formation uses to access S3

        Returns:
            dict with s3_arn, role_arn, status
        """
        self.lf.register_resource(
            ResourceArn=s3_arn,
            UseServiceLinkedRole=False,
            RoleArn=role_arn,
        )
        return {
            "s3_arn": s3_arn,
            "role_arn": role_arn,
            "status": "registered",
        }

    def register_data_lake_locations(
        self, bucket_arn: str, role_arn: str
    ) -> dict:
        """
        Register bronze, silver, and gold S3 locations.

        Args:
            bucket_arn: ARN of the data lake bucket
            role_arn: IAM role ARN for Lake Formation

        Returns:
            dict with registered locations list
        """
        layers = ["bronze", "silver", "gold"]
        registered = []
        for layer in layers:
            layer_arn = f"{bucket_arn}/{layer}/"
            result = self.register_s3_location(layer_arn, role_arn)
            registered.append(result)
        return {"locations": registered, "bucket_arn": bucket_arn}

    # ------------------------------------------------------------------
    # Glue Data Catalog Database
    # ------------------------------------------------------------------

    def create_database(self, description: str = "CMO Data Lake") -> dict:
        """
        Create the Glue Data Catalog database for the CMO data lake.

        Returns:
            dict with database_name and status
        """
        self.glue.create_database(
            DatabaseInput={
                "Name": self.DATABASE_NAME,
                "Description": description,
            }
        )
        return {
            "database_name": self.DATABASE_NAME,
            "status": "created",
        }

    def get_database(self) -> Optional[dict]:
        """
        Get the Glue Data Catalog database metadata.

        Returns:
            dict with database info or None if not found
        """
        try:
            response = self.glue.get_database(Name=self.DATABASE_NAME)
            db = response["Database"]
            return {
                "database_name": db["Name"],
                "description": db.get("Description", ""),
            }
        except self.glue.exceptions.EntityNotFoundException:
            return None

    # ------------------------------------------------------------------
    # Database & Table Permissions
    # ------------------------------------------------------------------

    def grant_database_permissions(
        self, principal_arn: str, permissions: Optional[list] = None
    ) -> dict:
        """
        Grant Lake Formation permissions on the data lake database.

        Args:
            principal_arn: IAM role/user ARN
            permissions: List of permissions (default: DESCRIBE, CREATE_TABLE)

        Returns:
            dict with principal, database, permissions, status
        """
        if permissions is None:
            permissions = ["DESCRIBE", "CREATE_TABLE"]

        self.lf.grant_permissions(
            Principal={"DataLakePrincipalIdentifier": principal_arn},
            Resource={
                "Database": {"Name": self.DATABASE_NAME},
            },
            Permissions=permissions,
            PermissionsWithGrantOption=[],
        )
        return {
            "principal_arn": principal_arn,
            "database_name": self.DATABASE_NAME,
            "permissions": permissions,
            "status": "granted",
        }

    def grant_table_permissions(
        self,
        principal_arn: str,
        table_name: str,
        permissions: Optional[list] = None,
    ) -> dict:
        """
        Grant Lake Formation permissions on a specific table.

        Args:
            principal_arn: IAM role/user ARN
            table_name: Glue Data Catalog table name
            permissions: List of permissions (default: SELECT, DESCRIBE)

        Returns:
            dict with principal, table, permissions, status
        """
        if permissions is None:
            permissions = ["SELECT", "DESCRIBE"]

        self.lf.grant_permissions(
            Principal={"DataLakePrincipalIdentifier": principal_arn},
            Resource={
                "Table": {
                    "DatabaseName": self.DATABASE_NAME,
                    "Name": table_name,
                },
            },
            Permissions=permissions,
            PermissionsWithGrantOption=[],
        )
        return {
            "principal_arn": principal_arn,
            "database_name": self.DATABASE_NAME,
            "table_name": table_name,
            "permissions": permissions,
            "status": "granted",
        }

    def grant_cmo_table_permissions(
        self,
        cmo_id: str,
        cmo_role_arn: str,
        data_domain: str,
        permissions: Optional[list] = None,
    ) -> dict:
        """
        Grant a CMO role permissions on its own silver-layer table.

        Table name follows convention: {cmo_id}_{data_domain}_silver
        (with hyphens replaced by underscores).

        Args:
            cmo_id: CMO identifier (e.g. 'cmo-alpha')
            cmo_role_arn: IAM role ARN for the CMO
            data_domain: Data domain (e.g. 'batch_records')
            permissions: List of permissions (default: SELECT, DESCRIBE)

        Returns:
            dict with grant details
        """
        self._validate_cmo_id(cmo_id)
        table_name = self._build_table_name(cmo_id, data_domain)
        return self.grant_table_permissions(cmo_role_arn, table_name, permissions)

    # ------------------------------------------------------------------
    # Revoke Permissions
    # ------------------------------------------------------------------

    def revoke_table_permissions(
        self,
        principal_arn: str,
        table_name: str,
        permissions: Optional[list] = None,
    ) -> dict:
        """
        Revoke Lake Formation permissions on a table.

        Args:
            principal_arn: IAM role/user ARN
            table_name: Glue Data Catalog table name
            permissions: Permissions to revoke (default: SELECT, DESCRIBE)

        Returns:
            dict with revocation details
        """
        if permissions is None:
            permissions = ["SELECT", "DESCRIBE"]

        self.lf.revoke_permissions(
            Principal={"DataLakePrincipalIdentifier": principal_arn},
            Resource={
                "Table": {
                    "DatabaseName": self.DATABASE_NAME,
                    "Name": table_name,
                },
            },
            Permissions=permissions,
            PermissionsWithGrantOption=[],
        )
        return {
            "principal_arn": principal_arn,
            "database_name": self.DATABASE_NAME,
            "table_name": table_name,
            "permissions": permissions,
            "status": "revoked",
        }

    def revoke_database_permissions(
        self,
        principal_arn: str,
        permissions: Optional[list] = None,
    ) -> dict:
        """
        Revoke Lake Formation permissions on the database.

        Args:
            principal_arn: IAM role/user ARN
            permissions: Permissions to revoke (default: DESCRIBE, CREATE_TABLE)

        Returns:
            dict with revocation details
        """
        if permissions is None:
            permissions = ["DESCRIBE", "CREATE_TABLE"]

        self.lf.revoke_permissions(
            Principal={"DataLakePrincipalIdentifier": principal_arn},
            Resource={
                "Database": {"Name": self.DATABASE_NAME},
            },
            Permissions=permissions,
            PermissionsWithGrantOption=[],
        )
        return {
            "principal_arn": principal_arn,
            "database_name": self.DATABASE_NAME,
            "permissions": permissions,
            "status": "revoked",
        }

    # ------------------------------------------------------------------
    # Data Cell Filters (Row-Level & Column-Level Security)
    # ------------------------------------------------------------------

    def create_row_filter(
        self,
        cmo_id: str,
        table_name: str,
        all_columns: list,
    ) -> dict:
        """
        Create a data cell filter for row-level security.

        Restricts rows to WHERE cmo_id = '{cmo_id}'.

        Args:
            cmo_id: CMO identifier
            table_name: Glue Data Catalog table name
            all_columns: List of all column names in the table

        Returns:
            dict with filter details
        """
        self._validate_cmo_id(cmo_id)
        filter_name = f"{cmo_id}-row-filter-{table_name}"

        self.lf.create_data_cells_filter(
            TableData={
                "TableCatalogId": self._get_catalog_id(),
                "DatabaseName": self.DATABASE_NAME,
                "TableName": table_name,
                "Name": filter_name,
                "RowFilter": {
                    "FilterExpression": f"cmo_id = '{cmo_id}'",
                },
                "ColumnNames": all_columns,
            }
        )
        return {
            "filter_name": filter_name,
            "cmo_id": cmo_id,
            "table_name": table_name,
            "row_filter": f"cmo_id = '{cmo_id}'",
            "filter_type": "row",
            "status": "created",
        }

    def create_column_filter(
        self,
        cmo_id: str,
        table_name: str,
        allowed_columns: list,
    ) -> dict:
        """
        Create a data cell filter for column-level security.

        Only the specified columns are visible to the CMO.

        Args:
            cmo_id: CMO identifier
            table_name: Glue Data Catalog table name
            allowed_columns: List of column names the CMO may see

        Returns:
            dict with filter details
        """
        self._validate_cmo_id(cmo_id)
        filter_name = f"{cmo_id}-col-filter-{table_name}"

        self.lf.create_data_cells_filter(
            TableData={
                "TableCatalogId": self._get_catalog_id(),
                "DatabaseName": self.DATABASE_NAME,
                "TableName": table_name,
                "Name": filter_name,
                "RowFilter": {
                    "AllRowsWildcard": {},
                },
                "ColumnNames": allowed_columns,
            }
        )
        return {
            "filter_name": filter_name,
            "cmo_id": cmo_id,
            "table_name": table_name,
            "allowed_columns": allowed_columns,
            "filter_type": "column",
            "status": "created",
        }

    def create_combined_filter(
        self,
        cmo_id: str,
        table_name: str,
        allowed_columns: list,
    ) -> dict:
        """
        Create a data cell filter combining row-level and column-level security.

        Row filter: WHERE cmo_id = '{cmo_id}'
        Column filter: only allowed_columns are visible (PII excluded).

        Args:
            cmo_id: CMO identifier
            table_name: Glue Data Catalog table name
            allowed_columns: Columns the CMO may see (PII columns excluded)

        Returns:
            dict with filter details
        """
        self._validate_cmo_id(cmo_id)
        filter_name = f"{cmo_id}-combined-filter-{table_name}"

        self.lf.create_data_cells_filter(
            TableData={
                "TableCatalogId": self._get_catalog_id(),
                "DatabaseName": self.DATABASE_NAME,
                "TableName": table_name,
                "Name": filter_name,
                "RowFilter": {
                    "FilterExpression": f"cmo_id = '{cmo_id}'",
                },
                "ColumnNames": allowed_columns,
            }
        )
        return {
            "filter_name": filter_name,
            "cmo_id": cmo_id,
            "table_name": table_name,
            "row_filter": f"cmo_id = '{cmo_id}'",
            "allowed_columns": allowed_columns,
            "filter_type": "combined",
            "status": "created",
        }

    def delete_data_cells_filter(
        self,
        table_name: str,
        filter_name: str,
    ) -> dict:
        """
        Delete a data cell filter.

        Args:
            table_name: Glue Data Catalog table name
            filter_name: Name of the filter to delete

        Returns:
            dict with deletion details
        """
        self.lf.delete_data_cells_filter(
            TableCatalogId=self._get_catalog_id(),
            DatabaseName=self.DATABASE_NAME,
            TableName=table_name,
            Name=filter_name,
        )
        return {
            "filter_name": filter_name,
            "table_name": table_name,
            "status": "deleted",
        }

    # ------------------------------------------------------------------
    # List Permissions
    # ------------------------------------------------------------------

    def list_permissions(
        self, principal_arn: Optional[str] = None
    ) -> list:
        """
        List Lake Formation permissions, optionally filtered by principal.

        Args:
            principal_arn: Optional principal ARN to filter by

        Returns:
            list of permission dicts
        """
        kwargs = {}
        if principal_arn:
            kwargs["Principal"] = {
                "DataLakePrincipalIdentifier": principal_arn
            }

        response = self.lf.list_permissions(**kwargs)
        results = []
        for entry in response.get("PrincipalResourcePermissions", []):
            results.append({
                "principal": entry["Principal"]["DataLakePrincipalIdentifier"],
                "resource": entry["Resource"],
                "permissions": entry["Permissions"],
            })
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_table_name(cmo_id: str, data_domain: str) -> str:
        """Build a Glue table name from CMO ID and data domain.

        Convention: {cmo_id}_{data_domain}_silver
        Hyphens are replaced with underscores for Glue compatibility.
        """
        safe_cmo = cmo_id.replace("-", "_")
        safe_domain = data_domain.replace("-", "_")
        return f"{safe_cmo}_{safe_domain}_silver"

    def _get_catalog_id(self) -> str:
        """Return the Glue Data Catalog account ID.

        Uses STS if available, otherwise returns a placeholder that
        the Lake Formation API will resolve to the caller's account.
        """
        try:
            sts = boto3.client("sts", region_name=self.region)
            return sts.get_caller_identity()["Account"]
        except Exception:
            return ""
