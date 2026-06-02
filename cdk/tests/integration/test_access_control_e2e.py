"""
Access Control End-to-End Integration Test

Tests the full access control flow using CMODataIsolationService with a
mocked LakeFormationService. Verifies CMO data isolation, row-level and
column-level filtering, authorized/unauthorized access, user grants, and
revocation.

Requirements: 10.1, 10.2, 10.3
"""
import os
import sys
from unittest.mock import MagicMock

import pytest

# Ensure the cdk root is on sys.path so service imports resolve
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services.cmo_data_isolation_service import CMODataIsolationService

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

CMO_ALPHA = {
    "cmo_id": "cmo-test-alpha",
    "cmo_role_arn": "arn:aws:iam::123456789012:role/cmo-test-alpha-role",
    "tables_config": [
        {
            "table_name": "cmo_test_alpha_batch_records_silver",
            "all_columns": ["batch_id", "product_name", "quantity", "operator_name", "cmo_id"],
            "pii_columns": ["operator_name"],
        }
    ],
}

CMO_BETA = {
    "cmo_id": "cmo-test-beta",
    "cmo_role_arn": "arn:aws:iam::123456789012:role/cmo-test-beta-role",
    "tables_config": [
        {
            "table_name": "cmo_test_beta_quality_data_silver",
            "all_columns": ["sample_id", "test_name", "result_value", "technician_name", "cmo_id"],
            "pii_columns": ["technician_name"],
        }
    ],
}

USER_ARN = "arn:aws:iam::123456789012:user/analyst-user"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_mock_lf_service() -> MagicMock:
    """Return a MagicMock that mimics LakeFormationService methods."""
    mock_lf = MagicMock()
    mock_lf.grant_database_permissions.return_value = {"status": "success"}
    mock_lf.grant_table_permissions.return_value = {"status": "success"}
    mock_lf.create_row_filter.return_value = {"status": "success"}
    mock_lf.create_column_filter.return_value = {"status": "success"}
    mock_lf.revoke_table_permissions.return_value = {"status": "success"}
    mock_lf.revoke_database_permissions.return_value = {"status": "success"}
    mock_lf.delete_data_cells_filter.return_value = {"status": "success"}
    # list_permissions is configured per-test
    mock_lf.list_permissions.return_value = []
    return mock_lf


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestAccessControlEndToEnd:
    """End-to-end access control tests using mocked LakeFormationService."""

    # ------------------------------------------------------------------
    # 1. Setup CMO isolation for two CMOs
    # ------------------------------------------------------------------

    def test_setup_cmo_isolation(self):
        """Setup isolation for two CMOs and verify grants/filters created."""
        mock_lf = _build_mock_lf_service()
        svc = CMODataIsolationService(lake_formation_service=mock_lf)

        # Setup Alpha
        alpha_result = svc.setup_cmo_isolation(**CMO_ALPHA)
        assert alpha_result["cmo_id"] == "cmo-test-alpha"
        assert alpha_result["tables_configured"] == 1
        assert alpha_result["database_grant"]["status"] == "success"
        assert len(alpha_result["table_grants"]) == 1
        assert len(alpha_result["row_filters"]) == 1
        assert len(alpha_result["column_filters"]) == 1

        # Setup Beta
        beta_result = svc.setup_cmo_isolation(**CMO_BETA)
        assert beta_result["cmo_id"] == "cmo-test-beta"
        assert beta_result["tables_configured"] == 1

        # Verify grant_database_permissions called for both CMOs
        assert mock_lf.grant_database_permissions.call_count == 2

        # Verify grant_table_permissions called for each table
        assert mock_lf.grant_table_permissions.call_count == 2

        # Verify row and column filters created for each table
        assert mock_lf.create_row_filter.call_count == 2
        assert mock_lf.create_column_filter.call_count == 2

    # ------------------------------------------------------------------
    # 2. Verify authorized access (CMO sees only its own tables)
    # ------------------------------------------------------------------

    def test_authorized_access_succeeds(self):
        """Verify that a CMO with only its own tables passes isolation check."""
        mock_lf = _build_mock_lf_service()
        svc = CMODataIsolationService(lake_formation_service=mock_lf)

        # Mock list_permissions to return only Alpha's own table
        mock_lf.list_permissions.return_value = [
            {
                "principal": CMO_ALPHA["cmo_role_arn"],
                "resource": {
                    "Table": {
                        "DatabaseName": "cmo_data_lake",
                        "Name": "cmo_test_alpha_batch_records_silver",
                    }
                },
                "permissions": ["SELECT", "DESCRIBE"],
            }
        ]

        result = svc.verify_cmo_isolation(
            cmo_id=CMO_ALPHA["cmo_id"],
            cmo_role_arn=CMO_ALPHA["cmo_role_arn"],
        )

        assert result["passed"] is True
        assert result["permissions_checked"] == 1
        assert result["violations"] == []

    # ------------------------------------------------------------------
    # 3. Verify unauthorized access (cross-CMO table detected)
    # ------------------------------------------------------------------

    def test_unauthorized_cross_cmo_access_fails(self):
        """Verify that cross-CMO table access is flagged as a violation."""
        mock_lf = _build_mock_lf_service()
        svc = CMODataIsolationService(lake_formation_service=mock_lf)

        # Mock list_permissions to return Beta's table for Alpha's role
        mock_lf.list_permissions.return_value = [
            {
                "principal": CMO_ALPHA["cmo_role_arn"],
                "resource": {
                    "Table": {
                        "DatabaseName": "cmo_data_lake",
                        "Name": "cmo_test_beta_quality_data_silver",
                    }
                },
                "permissions": ["SELECT"],
            }
        ]

        result = svc.verify_cmo_isolation(
            cmo_id=CMO_ALPHA["cmo_id"],
            cmo_role_arn=CMO_ALPHA["cmo_role_arn"],
        )

        assert result["passed"] is False
        assert len(result["violations"]) == 1
        assert result["violations"][0]["table_name"] == "cmo_test_beta_quality_data_silver"

    # ------------------------------------------------------------------
    # 4. Test row-level filtering
    # ------------------------------------------------------------------

    def test_row_level_filtering(self):
        """Verify create_row_filter is called with correct cmo_id filter."""
        mock_lf = _build_mock_lf_service()
        svc = CMODataIsolationService(lake_formation_service=mock_lf)

        svc.setup_cmo_isolation(**CMO_ALPHA)

        # Verify create_row_filter was called with the correct arguments
        mock_lf.create_row_filter.assert_called_once_with(
            cmo_id="cmo-test-alpha",
            table_name="cmo_test_alpha_batch_records_silver",
            all_columns=["batch_id", "product_name", "quantity", "operator_name", "cmo_id"],
        )

    # ------------------------------------------------------------------
    # 5. Test column-level filtering (PII excluded)
    # ------------------------------------------------------------------

    def test_column_level_filtering_excludes_pii(self):
        """Verify create_column_filter excludes PII columns."""
        mock_lf = _build_mock_lf_service()
        svc = CMODataIsolationService(lake_formation_service=mock_lf)

        svc.setup_cmo_isolation(**CMO_ALPHA)

        # operator_name is PII and should be excluded
        mock_lf.create_column_filter.assert_called_once_with(
            cmo_id="cmo-test-alpha",
            table_name="cmo_test_alpha_batch_records_silver",
            allowed_columns=["batch_id", "product_name", "quantity", "cmo_id"],
        )

    # ------------------------------------------------------------------
    # 6. Test user-CMO access grant
    # ------------------------------------------------------------------

    def test_grant_user_cmo_access(self):
        """Verify granting a user access to a CMO's data creates all grants and filters."""
        mock_lf = _build_mock_lf_service()
        svc = CMODataIsolationService(lake_formation_service=mock_lf)

        result = svc.grant_user_cmo_access(
            user_arn=USER_ARN,
            cmo_id=CMO_ALPHA["cmo_id"],
            tables_config=CMO_ALPHA["tables_config"],
        )

        assert result["user_arn"] == USER_ARN
        assert result["cmo_id"] == "cmo-test-alpha"
        assert result["tables_configured"] == 1

        # Database grant for the user
        mock_lf.grant_database_permissions.assert_called_once_with(
            USER_ARN, permissions=["DESCRIBE"]
        )

        # Table grant for the user
        mock_lf.grant_table_permissions.assert_called_once_with(
            USER_ARN,
            "cmo_test_alpha_batch_records_silver",
            permissions=["SELECT", "DESCRIBE"],
        )

        # Row and column filters created
        assert mock_lf.create_row_filter.call_count == 1
        assert mock_lf.create_column_filter.call_count == 1

        # Column filter excludes PII
        mock_lf.create_column_filter.assert_called_once_with(
            cmo_id="cmo-test-alpha",
            table_name="cmo_test_alpha_batch_records_silver",
            allowed_columns=["batch_id", "product_name", "quantity", "cmo_id"],
        )

    # ------------------------------------------------------------------
    # 7. Test revocation
    # ------------------------------------------------------------------

    def test_revoke_cmo_isolation(self):
        """Verify revoking CMO isolation removes all grants and filters."""
        mock_lf = _build_mock_lf_service()
        svc = CMODataIsolationService(lake_formation_service=mock_lf)

        result = svc.revoke_cmo_isolation(**CMO_ALPHA)

        assert result["cmo_id"] == "cmo-test-alpha"
        assert result["tables_revoked"] == 1

        # Table permissions revoked
        mock_lf.revoke_table_permissions.assert_called_once_with(
            CMO_ALPHA["cmo_role_arn"],
            "cmo_test_alpha_batch_records_silver",
            permissions=["SELECT", "DESCRIBE"],
        )

        # Database permissions revoked
        mock_lf.revoke_database_permissions.assert_called_once_with(
            CMO_ALPHA["cmo_role_arn"], permissions=["DESCRIBE"]
        )

        # Row filter and column filter deleted (2 calls total)
        assert mock_lf.delete_data_cells_filter.call_count == 2
        mock_lf.delete_data_cells_filter.assert_any_call(
            "cmo_test_alpha_batch_records_silver",
            "cmo-test-alpha-row-filter-cmo_test_alpha_batch_records_silver",
        )
        mock_lf.delete_data_cells_filter.assert_any_call(
            "cmo_test_alpha_batch_records_silver",
            "cmo-test-alpha-col-filter-cmo_test_alpha_batch_records_silver",
        )
