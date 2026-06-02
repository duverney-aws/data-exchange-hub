"""
Unit Tests for CMO Data Isolation Service.

Tests:
- Full isolation setup for a CMO with multiple tables
- PII columns excluded from column filters
- Cross-CMO access prevention (verify_cmo_isolation)
- Isolation revocation
- User-CMO access grants
- CMO ID validation

Requirements: 10.2, 10.3

Note: Uses unittest.mock since this service orchestrates
LakeFormationService calls.
"""
import sys
import os
import pytest
from unittest.mock import MagicMock, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.cmo_data_isolation_service import CMODataIsolationService


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACCOUNT_ID = "123456789012"
REGION = "us-east-1"
CMO_ID = "cmo-alpha"
CMO_ROLE_ARN = f"arn:aws:iam::{ACCOUNT_ID}:role/pharma-hub-cmo-{CMO_ID}-role"
USER_ARN = f"arn:aws:iam::{ACCOUNT_ID}:user/analyst-1"

TABLES_CONFIG = [
    {
        "table_name": "cmo_alpha_batch_records_silver",
        "all_columns": [
            "batch_id", "cmo_id", "product_name",
            "quantity", "operator_name", "operator_email",
        ],
        "pii_columns": ["operator_name", "operator_email"],
    },
    {
        "table_name": "cmo_alpha_quality_data_silver",
        "all_columns": [
            "quality_id", "cmo_id", "test_result",
            "inspector_name",
        ],
        "pii_columns": ["inspector_name"],
    },
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_lf_service():
    """Mock LakeFormationService with sensible return values."""
    svc = MagicMock()

    svc.grant_database_permissions.return_value = {
        "principal_arn": CMO_ROLE_ARN,
        "database_name": "cmo_data_lake",
        "permissions": ["DESCRIBE"],
        "status": "granted",
    }

    svc.grant_table_permissions.return_value = {
        "principal_arn": CMO_ROLE_ARN,
        "table_name": "placeholder",
        "permissions": ["SELECT", "DESCRIBE"],
        "status": "granted",
    }

    svc.create_row_filter.return_value = {
        "filter_name": "placeholder",
        "cmo_id": CMO_ID,
        "row_filter": f"cmo_id = '{CMO_ID}'",
        "filter_type": "row",
        "status": "created",
    }

    svc.create_column_filter.return_value = {
        "filter_name": "placeholder",
        "cmo_id": CMO_ID,
        "allowed_columns": [],
        "filter_type": "column",
        "status": "created",
    }

    svc.revoke_table_permissions.return_value = {
        "status": "revoked",
    }

    svc.revoke_database_permissions.return_value = {
        "status": "revoked",
    }

    svc.delete_data_cells_filter.return_value = {
        "status": "deleted",
    }

    svc.list_permissions.return_value = []

    return svc


@pytest.fixture
def service(mock_lf_service):
    return CMODataIsolationService(lake_formation_service=mock_lf_service)


# ---------------------------------------------------------------------------
# Full Isolation Setup
# ---------------------------------------------------------------------------

class TestSetupCMOIsolation:
    """Requirement 10.2: One-call CMO isolation setup."""

    def test_setup_returns_correct_cmo_id(self, service):
        result = service.setup_cmo_isolation(CMO_ID, CMO_ROLE_ARN, TABLES_CONFIG)
        assert result["cmo_id"] == CMO_ID

    def test_setup_returns_correct_role_arn(self, service):
        result = service.setup_cmo_isolation(CMO_ID, CMO_ROLE_ARN, TABLES_CONFIG)
        assert result["cmo_role_arn"] == CMO_ROLE_ARN

    def test_setup_grants_database_describe(self, service, mock_lf_service):
        service.setup_cmo_isolation(CMO_ID, CMO_ROLE_ARN, TABLES_CONFIG)
        mock_lf_service.grant_database_permissions.assert_called_once_with(
            CMO_ROLE_ARN, permissions=["DESCRIBE"]
        )

    def test_setup_grants_table_permissions_per_table(self, service, mock_lf_service):
        service.setup_cmo_isolation(CMO_ID, CMO_ROLE_ARN, TABLES_CONFIG)
        assert mock_lf_service.grant_table_permissions.call_count == 2
        mock_lf_service.grant_table_permissions.assert_any_call(
            CMO_ROLE_ARN,
            "cmo_alpha_batch_records_silver",
            permissions=["SELECT", "DESCRIBE"],
        )
        mock_lf_service.grant_table_permissions.assert_any_call(
            CMO_ROLE_ARN,
            "cmo_alpha_quality_data_silver",
            permissions=["SELECT", "DESCRIBE"],
        )

    def test_setup_creates_row_filter_per_table(self, service, mock_lf_service):
        service.setup_cmo_isolation(CMO_ID, CMO_ROLE_ARN, TABLES_CONFIG)
        assert mock_lf_service.create_row_filter.call_count == 2
        mock_lf_service.create_row_filter.assert_any_call(
            cmo_id=CMO_ID,
            table_name="cmo_alpha_batch_records_silver",
            all_columns=TABLES_CONFIG[0]["all_columns"],
        )

    def test_setup_creates_column_filter_per_table(self, service, mock_lf_service):
        service.setup_cmo_isolation(CMO_ID, CMO_ROLE_ARN, TABLES_CONFIG)
        assert mock_lf_service.create_column_filter.call_count == 2

    def test_setup_tables_configured_count(self, service):
        result = service.setup_cmo_isolation(CMO_ID, CMO_ROLE_ARN, TABLES_CONFIG)
        assert result["tables_configured"] == 2

    def test_setup_returns_all_grants_and_filters(self, service):
        result = service.setup_cmo_isolation(CMO_ID, CMO_ROLE_ARN, TABLES_CONFIG)
        assert "database_grant" in result
        assert len(result["table_grants"]) == 2
        assert len(result["row_filters"]) == 2
        assert len(result["column_filters"]) == 2


# ---------------------------------------------------------------------------
# PII Column Exclusion
# ---------------------------------------------------------------------------

class TestPIIColumnExclusion:
    """Requirement 10.2: PII columns excluded from column filters."""

    def test_column_filter_excludes_pii(self, service, mock_lf_service):
        service.setup_cmo_isolation(CMO_ID, CMO_ROLE_ARN, TABLES_CONFIG)

        # First table: operator_name and operator_email are PII
        first_call = mock_lf_service.create_column_filter.call_args_list[0]
        allowed = first_call.kwargs["allowed_columns"]
        assert "operator_name" not in allowed
        assert "operator_email" not in allowed
        assert "batch_id" in allowed
        assert "cmo_id" in allowed
        assert "product_name" in allowed
        assert "quantity" in allowed

    def test_column_filter_excludes_pii_second_table(self, service, mock_lf_service):
        service.setup_cmo_isolation(CMO_ID, CMO_ROLE_ARN, TABLES_CONFIG)

        # Second table: inspector_name is PII
        second_call = mock_lf_service.create_column_filter.call_args_list[1]
        allowed = second_call.kwargs["allowed_columns"]
        assert "inspector_name" not in allowed
        assert "quality_id" in allowed
        assert "cmo_id" in allowed
        assert "test_result" in allowed

    def test_no_pii_columns_keeps_all(self, service, mock_lf_service):
        config = [
            {
                "table_name": "cmo_alpha_metrics_silver",
                "all_columns": ["metric_id", "cmo_id", "value"],
                "pii_columns": [],
            }
        ]
        service.setup_cmo_isolation(CMO_ID, CMO_ROLE_ARN, config)
        call_args = mock_lf_service.create_column_filter.call_args_list[0]
        allowed = call_args.kwargs["allowed_columns"]
        assert allowed == ["metric_id", "cmo_id", "value"]

    def test_missing_pii_key_defaults_to_empty(self, service, mock_lf_service):
        config = [
            {
                "table_name": "cmo_alpha_metrics_silver",
                "all_columns": ["metric_id", "cmo_id"],
            }
        ]
        service.setup_cmo_isolation(CMO_ID, CMO_ROLE_ARN, config)
        call_args = mock_lf_service.create_column_filter.call_args_list[0]
        allowed = call_args.kwargs["allowed_columns"]
        assert allowed == ["metric_id", "cmo_id"]


# ---------------------------------------------------------------------------
# Cross-CMO Access Prevention (Verification)
# ---------------------------------------------------------------------------

class TestVerifyCMOIsolation:
    """Requirement 10.3: Verify cross-CMO access prevention."""

    def test_passes_when_no_permissions(self, service, mock_lf_service):
        mock_lf_service.list_permissions.return_value = []
        result = service.verify_cmo_isolation(CMO_ID, CMO_ROLE_ARN)
        assert result["passed"] is True
        assert result["violations"] == []

    def test_passes_when_only_own_tables(self, service, mock_lf_service):
        mock_lf_service.list_permissions.return_value = [
            {
                "principal": CMO_ROLE_ARN,
                "resource": {
                    "Table": {
                        "DatabaseName": "cmo_data_lake",
                        "Name": "cmo_alpha_batch_records_silver",
                    }
                },
                "permissions": ["SELECT", "DESCRIBE"],
            }
        ]
        result = service.verify_cmo_isolation(CMO_ID, CMO_ROLE_ARN)
        assert result["passed"] is True
        assert result["violations"] == []

    def test_fails_when_accessing_other_cmo_table(self, service, mock_lf_service):
        mock_lf_service.list_permissions.return_value = [
            {
                "principal": CMO_ROLE_ARN,
                "resource": {
                    "Table": {
                        "DatabaseName": "cmo_data_lake",
                        "Name": "cmo_alpha_batch_records_silver",
                    }
                },
                "permissions": ["SELECT", "DESCRIBE"],
            },
            {
                "principal": CMO_ROLE_ARN,
                "resource": {
                    "Table": {
                        "DatabaseName": "cmo_data_lake",
                        "Name": "cmo_beta_quality_data_silver",
                    }
                },
                "permissions": ["SELECT"],
            },
        ]
        result = service.verify_cmo_isolation(CMO_ID, CMO_ROLE_ARN)
        assert result["passed"] is False
        assert len(result["violations"]) == 1
        assert result["violations"][0]["table_name"] == "cmo_beta_quality_data_silver"

    def test_calls_list_permissions_with_principal(self, service, mock_lf_service):
        service.verify_cmo_isolation(CMO_ID, CMO_ROLE_ARN)
        mock_lf_service.list_permissions.assert_called_once_with(
            principal_arn=CMO_ROLE_ARN
        )

    def test_permissions_checked_count(self, service, mock_lf_service):
        mock_lf_service.list_permissions.return_value = [
            {
                "principal": CMO_ROLE_ARN,
                "resource": {
                    "Table": {
                        "DatabaseName": "cmo_data_lake",
                        "Name": "cmo_alpha_batch_records_silver",
                    }
                },
                "permissions": ["SELECT"],
            },
            {
                "principal": CMO_ROLE_ARN,
                "resource": {
                    "Table": {
                        "DatabaseName": "cmo_data_lake",
                        "Name": "cmo_alpha_quality_data_silver",
                    }
                },
                "permissions": ["SELECT"],
            },
        ]
        result = service.verify_cmo_isolation(CMO_ID, CMO_ROLE_ARN)
        assert result["permissions_checked"] == 2

    def test_database_only_permissions_pass(self, service, mock_lf_service):
        """Database-level permissions (no Table key) should not cause violations."""
        mock_lf_service.list_permissions.return_value = [
            {
                "principal": CMO_ROLE_ARN,
                "resource": {
                    "Database": {"Name": "cmo_data_lake"}
                },
                "permissions": ["DESCRIBE"],
            }
        ]
        result = service.verify_cmo_isolation(CMO_ID, CMO_ROLE_ARN)
        assert result["passed"] is True


# ---------------------------------------------------------------------------
# Isolation Revocation
# ---------------------------------------------------------------------------

class TestRevokeCMOIsolation:
    """Requirement 10.2: Revoke all CMO isolation grants and filters."""

    def test_revokes_table_permissions(self, service, mock_lf_service):
        service.revoke_cmo_isolation(CMO_ID, CMO_ROLE_ARN, TABLES_CONFIG)
        assert mock_lf_service.revoke_table_permissions.call_count == 2
        mock_lf_service.revoke_table_permissions.assert_any_call(
            CMO_ROLE_ARN,
            "cmo_alpha_batch_records_silver",
            permissions=["SELECT", "DESCRIBE"],
        )

    def test_deletes_row_and_column_filters(self, service, mock_lf_service):
        service.revoke_cmo_isolation(CMO_ID, CMO_ROLE_ARN, TABLES_CONFIG)
        # 2 tables × 2 filters (row + column) = 4 deletions
        assert mock_lf_service.delete_data_cells_filter.call_count == 4

    def test_deletes_correct_filter_names(self, service, mock_lf_service):
        service.revoke_cmo_isolation(CMO_ID, CMO_ROLE_ARN, TABLES_CONFIG)
        calls = mock_lf_service.delete_data_cells_filter.call_args_list
        filter_names = [c.args[1] if len(c.args) > 1 else c[0][1] for c in calls]
        assert "cmo-alpha-row-filter-cmo_alpha_batch_records_silver" in filter_names
        assert "cmo-alpha-col-filter-cmo_alpha_batch_records_silver" in filter_names
        assert "cmo-alpha-row-filter-cmo_alpha_quality_data_silver" in filter_names
        assert "cmo-alpha-col-filter-cmo_alpha_quality_data_silver" in filter_names

    def test_revokes_database_permissions(self, service, mock_lf_service):
        service.revoke_cmo_isolation(CMO_ID, CMO_ROLE_ARN, TABLES_CONFIG)
        mock_lf_service.revoke_database_permissions.assert_called_once_with(
            CMO_ROLE_ARN, permissions=["DESCRIBE"]
        )

    def test_revocation_summary(self, service):
        result = service.revoke_cmo_isolation(CMO_ID, CMO_ROLE_ARN, TABLES_CONFIG)
        assert result["cmo_id"] == CMO_ID
        assert result["tables_revoked"] == 2
        assert len(result["table_revocations"]) == 2
        assert len(result["filter_deletions"]) == 4
        assert result["database_revocation"]["status"] == "revoked"


# ---------------------------------------------------------------------------
# User-CMO Access Grants
# ---------------------------------------------------------------------------

class TestGrantUserCMOAccess:
    """Requirement 10.3: Grant user access to a specific CMO's data."""

    def test_grants_database_describe_to_user(self, service, mock_lf_service):
        service.grant_user_cmo_access(USER_ARN, CMO_ID, TABLES_CONFIG)
        mock_lf_service.grant_database_permissions.assert_called_once_with(
            USER_ARN, permissions=["DESCRIBE"]
        )

    def test_grants_table_permissions_to_user(self, service, mock_lf_service):
        service.grant_user_cmo_access(USER_ARN, CMO_ID, TABLES_CONFIG)
        assert mock_lf_service.grant_table_permissions.call_count == 2
        mock_lf_service.grant_table_permissions.assert_any_call(
            USER_ARN,
            "cmo_alpha_batch_records_silver",
            permissions=["SELECT", "DESCRIBE"],
        )

    def test_creates_row_filters_for_user(self, service, mock_lf_service):
        service.grant_user_cmo_access(USER_ARN, CMO_ID, TABLES_CONFIG)
        assert mock_lf_service.create_row_filter.call_count == 2

    def test_creates_column_filters_excluding_pii(self, service, mock_lf_service):
        service.grant_user_cmo_access(USER_ARN, CMO_ID, TABLES_CONFIG)
        first_call = mock_lf_service.create_column_filter.call_args_list[0]
        allowed = first_call.kwargs["allowed_columns"]
        assert "operator_name" not in allowed
        assert "operator_email" not in allowed

    def test_returns_user_arn_and_cmo_id(self, service):
        result = service.grant_user_cmo_access(USER_ARN, CMO_ID, TABLES_CONFIG)
        assert result["user_arn"] == USER_ARN
        assert result["cmo_id"] == CMO_ID
        assert result["tables_configured"] == 2


# ---------------------------------------------------------------------------
# CMO ID Validation
# ---------------------------------------------------------------------------

class TestCMOIDValidation:
    """Requirement 10.2: CMO ID must start with 'cmo-'."""

    @pytest.mark.parametrize("bad_id", ["", "alpha", "CMO-alpha", "cm-alpha"])
    def test_setup_rejects_bad_cmo_id(self, service, bad_id):
        with pytest.raises(ValueError, match="Invalid CMO ID"):
            service.setup_cmo_isolation(bad_id, CMO_ROLE_ARN, TABLES_CONFIG)

    @pytest.mark.parametrize("bad_id", ["", "alpha", "CMO-alpha"])
    def test_verify_rejects_bad_cmo_id(self, service, bad_id):
        with pytest.raises(ValueError, match="Invalid CMO ID"):
            service.verify_cmo_isolation(bad_id, CMO_ROLE_ARN)

    @pytest.mark.parametrize("bad_id", ["", "alpha"])
    def test_revoke_rejects_bad_cmo_id(self, service, bad_id):
        with pytest.raises(ValueError, match="Invalid CMO ID"):
            service.revoke_cmo_isolation(bad_id, CMO_ROLE_ARN, TABLES_CONFIG)

    @pytest.mark.parametrize("bad_id", ["", "alpha"])
    def test_grant_user_rejects_bad_cmo_id(self, service, bad_id):
        with pytest.raises(ValueError, match="Invalid CMO ID"):
            service.grant_user_cmo_access(USER_ARN, bad_id, TABLES_CONFIG)
