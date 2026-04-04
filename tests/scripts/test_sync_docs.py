import os

from crypto_signals.scripts.docs.sync_docs import app
from typer.testing import CliRunner

runner = CliRunner()


def test_sync_docs_execution(tmp_path):
    """
    Test that sync-docs runs successfully and updates files.
    """
    # Setup temp directory structure
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "data").mkdir()
    (docs_dir / "architecture").mkdir()

    # Create dummy handbook
    handbook = docs_dir / "data" / "00_data_handbook.md"
    handbook.write_text(
        "Start\n<!-- GENERATED: AccountSnapshot -->\nOld Content\n<!-- END_GENERATED -->\nEnd",
        encoding="utf-8",
    )

    # Create dummy dbml
    dbml = docs_dir / "architecture" / "current-schema.dbml"
    dbml.write_text(
        "Start\n// GENERATED: dim_strategies\nOld Content\n// END_GENERATED\nEnd",
        encoding="utf-8",
    )

    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        # 1. Test Check fails initially
        result = runner.invoke(app, ["--check"])
        assert result.exit_code == 1
        assert "Documentation is out of sync" in result.stdout

        # 2. Test Sync updates files
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        assert "Updating" in result.stdout

        # Verify Handbook updated
        new_handbook = handbook.read_text(encoding="utf-8")
        assert "Old Content" not in new_handbook
        assert "| `account_id` | `str` |" in new_handbook

        # Verify DBML updated
        new_dbml = dbml.read_text(encoding="utf-8")
        assert "Old Content" not in new_dbml
        assert "Table dim_strategies" in new_dbml

        # 3. Test Check passes now
        result = runner.invoke(app, ["--check"])
        assert result.exit_code == 0
        assert "Documentation is up-to-date" in result.stdout

    finally:
        os.chdir(original_cwd)


def test_sync_docs_missing_files(tmp_path):
    """
    Test that sync-docs fails if files are missing.
    """
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(app, [])
        assert result.exit_code == 1
        assert "Handbook not found" in result.stdout
    finally:
        os.chdir(original_cwd)
