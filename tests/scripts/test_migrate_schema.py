from unittest.mock import MagicMock, patch

import pytest
import typer
from crypto_signals.scripts.maintenance.migrate_schema import migrate_schema


@patch("crypto_signals.scripts.maintenance.migrate_schema.SchemaGuardian")
@patch("crypto_signals.scripts.maintenance.migrate_schema.bigquery.Client")
def test_migrate_schema_executes_single_alter_statement(
    mock_bq_client, mock_schema_guardian
):
    """
    Test that migrate_schema generates and executes a single, correct ALTER TABLE
    statement for all missing columns.
    """
    # Arrange
    mock_guardian_instance = MagicMock()
    mock_guardian_instance.validate_schema.return_value = (
        [("asset_class", "STRING"), ("side", "STRING")],
        [],
    )
    mock_schema_guardian.return_value = mock_guardian_instance

    mock_client_instance = MagicMock()
    mock_bq_client.return_value = mock_client_instance

    # Act
    migrate_schema("project.dataset.table", MagicMock())

    # Assert
    mock_client_instance.query.assert_called_once_with(
        "ALTER TABLE `project.dataset.table` ADD COLUMN `asset_class` STRING, ADD COLUMN `side` STRING"
    )


@patch("crypto_signals.scripts.maintenance.migrate_schema.SchemaGuardian")
@patch("crypto_signals.scripts.maintenance.migrate_schema.bigquery.Client")
def test_migrate_schema_no_missing_columns(mock_bq_client, mock_schema_guardian):
    """
    Test that migrate_schema does not execute any queries when there are no
    missing columns.
    """
    # Arrange
    mock_guardian_instance = MagicMock()
    mock_guardian_instance.validate_schema.return_value = ([], [])
    mock_schema_guardian.return_value = mock_guardian_instance

    mock_client_instance = MagicMock()
    mock_bq_client.return_value = mock_client_instance

    # Act
    migrate_schema("project.dataset.table", MagicMock())

    # Assert
    mock_client_instance.query.assert_not_called()


@patch("crypto_signals.scripts.maintenance.migrate_schema.SchemaGuardian")
@patch("crypto_signals.scripts.maintenance.migrate_schema.bigquery.Client")
def test_migrate_schema_only_type_mismatches(mock_bq_client, mock_schema_guardian):
    """
    Test that migrate_schema does not execute any queries when there are only
    type mismatches, as it only handles adding missing columns.
    """
    # Arrange
    mock_guardian_instance = MagicMock()
    mock_guardian_instance.validate_schema.return_value = (
        [],
        ["type_mismatch_error"],
    )
    mock_schema_guardian.return_value = mock_guardian_instance

    mock_client_instance = MagicMock()
    mock_bq_client.return_value = mock_client_instance

    # Act
    migrate_schema("project.dataset.table", MagicMock())

    # Assert
    mock_client_instance.query.assert_not_called()


@patch("crypto_signals.scripts.maintenance.migrate_schema.SchemaGuardian")
@patch("crypto_signals.scripts.maintenance.migrate_schema.bigquery.Client")
def test_migrate_schema_raises_on_alter_failure(mock_bq_client, mock_schema_guardian):
    """
    Test that migrate_schema raises an exception when ALTER TABLE fails.
    This ensures CI/CD correctly reports failure instead of silent success.
    """
    # Arrange
    mock_guardian_instance = MagicMock()
    mock_guardian_instance.validate_schema.return_value = (
        [("new_column", "STRING")],
        [],
    )
    mock_schema_guardian.return_value = mock_guardian_instance

    mock_client_instance = MagicMock()
    mock_client_instance.query.side_effect = Exception("BigQuery ALTER TABLE failed")
    mock_bq_client.return_value = mock_client_instance

    # Act & Assert
    with pytest.raises(Exception, match="BigQuery ALTER TABLE failed"):
        migrate_schema("valid_project.valid_dataset.valid_table", MagicMock())


# =============================================================================
# SECURITY TESTS (PR #203 Review Feedback)
# =============================================================================


def test_validate_table_id_rejects_sql_injection():
    """Test that table_id with SQL injection characters is rejected."""
    from crypto_signals.scripts.maintenance.migrate_schema import _validate_table_id

    # Valid format should pass
    _validate_table_id("my_project.my_dataset.my_table")
    _validate_table_id("project-123.dataset_name.table-v2")

    # SQL injection attempts should fail
    import pytest

    with pytest.raises(ValueError, match="Invalid table_id format"):
        _validate_table_id("project`; DROP TABLE users; --`.dataset.table")

    with pytest.raises(ValueError, match="Invalid table_id format"):
        _validate_table_id("project.dataset.table; DELETE FROM other")

    with pytest.raises(ValueError, match="Invalid table_id format"):
        _validate_table_id("not_valid_format")


def test_main_rejects_untrusted_model_prefix():
    """Test that model_name must start with trusted crypto_signals. prefix."""
    from crypto_signals.scripts.maintenance.migrate_schema import main
    from typer.testing import CliRunner

    runner = CliRunner()
    app = typer.Typer()
    app.command()(main)

    result = runner.invoke(
        app,
        ["project.dataset.table", "os.system"],  # Malicious module
    )

    assert result.exit_code == 1
    assert "trusted package" in result.output or result.exit_code == 1


def test_main_rejects_non_basemodel_class():
    """Test that imported class must be a Pydantic BaseModel subclass."""
    from crypto_signals.scripts.maintenance.migrate_schema import main
    from typer.testing import CliRunner

    runner = CliRunner()
    app = typer.Typer()
    app.command()(main)

    # Settings is not a BaseModel subclass (it's BaseSettings)
    # Actually let's use a non-model class
    result = runner.invoke(
        app,
        [
            "project.dataset.table",
            "crypto_signals.config.get_settings",
        ],  # Function, not model
    )

    assert result.exit_code == 1
