"""
CMO Data Isolation Service for Pharma Data Exchange Hub

Higher-level orchestration layer for CMO data isolation using
AWS Lake Formation. Coordinates row filters, column filters,
and permission grants to ensure each CMO can only access its
own data with PII columns excluded.

Requirements: 10.2, 10.3
"""
from typing import Optional


class CMODataIsolationService:
    """Orchestrates CMO data isolation via Lake Formation filters and grants."""

    def __init__(self, lake_formation_service):
        """
        Args:
            lake_formation_service: An instance of LakeFormationService
        """
        self.lf = lake_formation_service

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
    # Setup
    # ------------------------------------------------------------------

    def setup_cmo_isolation(
        self,
        cmo_id: str,
        cmo_role_arn: str,
        tables_config: list[dict],
    ) -> dict:
        """
        One-call setup for CMO data isolation.

        Grants database-level DESCRIBE, per-table SELECT+DESCRIBE,
        and creates row filters (WHERE cmo_id = '{cmo_id}') and
        column filters (excluding PII columns) for each table.

        Args:
            cmo_id: CMO identifier (e.g. 'cmo-alpha')
            cmo_role_arn: IAM role ARN for the CMO
            tables_config: List of table config dicts with keys:
                - table_name: Glue table name
                - all_columns: list of all column names
                - pii_columns: list of PII column names to exclude

        Returns:
            dict with database_grant, table_grants, row_filters,
            column_filters, and summary counts
        """
        self._validate_cmo_id(cmo_id)

        # 1. Grant database-level DESCRIBE
        db_grant = self.lf.grant_database_permissions(
            cmo_role_arn, permissions=["DESCRIBE"]
        )

        table_grants = []
        row_filters = []
        column_filters = []

        for table_cfg in tables_config:
            table_name = table_cfg["table_name"]
            all_columns = table_cfg["all_columns"]
            pii_columns = table_cfg.get("pii_columns", [])

            # 2. Grant SELECT + DESCRIBE on each table
            tg = self.lf.grant_table_permissions(
                cmo_role_arn, table_name, permissions=["SELECT", "DESCRIBE"]
            )
            table_grants.append(tg)

            # 3. Create row filter: WHERE cmo_id = '{cmo_id}'
            rf = self.lf.create_row_filter(
                cmo_id=cmo_id,
                table_name=table_name,
                all_columns=all_columns,
            )
            row_filters.append(rf)

            # 4. Create column filter excluding PII
            allowed_columns = [c for c in all_columns if c not in pii_columns]
            cf = self.lf.create_column_filter(
                cmo_id=cmo_id,
                table_name=table_name,
                allowed_columns=allowed_columns,
            )
            column_filters.append(cf)

        return {
            "cmo_id": cmo_id,
            "cmo_role_arn": cmo_role_arn,
            "database_grant": db_grant,
            "table_grants": table_grants,
            "row_filters": row_filters,
            "column_filters": column_filters,
            "tables_configured": len(tables_config),
        }

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def verify_cmo_isolation(
        self,
        cmo_id: str,
        cmo_role_arn: str,
    ) -> dict:
        """
        Verify that a CMO role's permissions are properly isolated.

        Lists all permissions for the CMO role and checks that every
        table-level permission references only tables belonging to
        this CMO (table name contains the CMO prefix).

        Args:
            cmo_id: CMO identifier
            cmo_role_arn: IAM role ARN for the CMO

        Returns:
            dict with passed (bool), permissions list, and any violations
        """
        self._validate_cmo_id(cmo_id)

        permissions = self.lf.list_permissions(principal_arn=cmo_role_arn)

        cmo_prefix = cmo_id.replace("-", "_")
        violations = []

        for perm in permissions:
            resource = perm.get("resource", {})
            table_info = resource.get("Table", {})
            if table_info:
                table_name = table_info.get("Name", "")
                if table_name and not table_name.startswith(cmo_prefix):
                    violations.append({
                        "table_name": table_name,
                        "permissions": perm.get("permissions", []),
                        "reason": f"Table does not belong to {cmo_id}",
                    })

        return {
            "cmo_id": cmo_id,
            "cmo_role_arn": cmo_role_arn,
            "passed": len(violations) == 0,
            "permissions_checked": len(permissions),
            "violations": violations,
        }

    # ------------------------------------------------------------------
    # Revocation
    # ------------------------------------------------------------------

    def revoke_cmo_isolation(
        self,
        cmo_id: str,
        cmo_role_arn: str,
        tables_config: list[dict],
    ) -> dict:
        """
        Revoke all isolation grants and delete all data cell filters
        for a CMO.

        Args:
            cmo_id: CMO identifier
            cmo_role_arn: IAM role ARN for the CMO
            tables_config: Same config used during setup

        Returns:
            dict with revocation summary
        """
        self._validate_cmo_id(cmo_id)

        table_revocations = []
        filter_deletions = []

        for table_cfg in tables_config:
            table_name = table_cfg["table_name"]

            # Revoke table permissions
            tr = self.lf.revoke_table_permissions(
                cmo_role_arn, table_name, permissions=["SELECT", "DESCRIBE"]
            )
            table_revocations.append(tr)

            # Delete row filter
            row_filter_name = f"{cmo_id}-row-filter-{table_name}"
            rd = self.lf.delete_data_cells_filter(table_name, row_filter_name)
            filter_deletions.append(rd)

            # Delete column filter
            col_filter_name = f"{cmo_id}-col-filter-{table_name}"
            cd = self.lf.delete_data_cells_filter(table_name, col_filter_name)
            filter_deletions.append(cd)

        # Revoke database permissions
        db_revocation = self.lf.revoke_database_permissions(
            cmo_role_arn, permissions=["DESCRIBE"]
        )

        return {
            "cmo_id": cmo_id,
            "cmo_role_arn": cmo_role_arn,
            "database_revocation": db_revocation,
            "table_revocations": table_revocations,
            "filter_deletions": filter_deletions,
            "tables_revoked": len(tables_config),
        }

    # ------------------------------------------------------------------
    # User-CMO Access
    # ------------------------------------------------------------------

    def grant_user_cmo_access(
        self,
        user_arn: str,
        cmo_id: str,
        tables_config: list[dict],
    ) -> dict:
        """
        Grant a user access to a specific CMO's data using the same
        row/column filters as the CMO role.

        Args:
            user_arn: IAM user/role ARN
            cmo_id: CMO identifier the user is associated with
            tables_config: Table config (same format as setup)

        Returns:
            dict with grant summary
        """
        self._validate_cmo_id(cmo_id)

        # Database-level DESCRIBE for the user
        db_grant = self.lf.grant_database_permissions(
            user_arn, permissions=["DESCRIBE"]
        )

        table_grants = []
        row_filters = []
        column_filters = []

        for table_cfg in tables_config:
            table_name = table_cfg["table_name"]
            all_columns = table_cfg["all_columns"]
            pii_columns = table_cfg.get("pii_columns", [])

            # Grant SELECT + DESCRIBE
            tg = self.lf.grant_table_permissions(
                user_arn, table_name, permissions=["SELECT", "DESCRIBE"]
            )
            table_grants.append(tg)

            # Row filter: WHERE cmo_id = '{cmo_id}'
            rf = self.lf.create_row_filter(
                cmo_id=cmo_id,
                table_name=table_name,
                all_columns=all_columns,
            )
            row_filters.append(rf)

            # Column filter excluding PII
            allowed_columns = [c for c in all_columns if c not in pii_columns]
            cf = self.lf.create_column_filter(
                cmo_id=cmo_id,
                table_name=table_name,
                allowed_columns=allowed_columns,
            )
            column_filters.append(cf)

        return {
            "user_arn": user_arn,
            "cmo_id": cmo_id,
            "database_grant": db_grant,
            "table_grants": table_grants,
            "row_filters": row_filters,
            "column_filters": column_filters,
            "tables_configured": len(tables_config),
        }
