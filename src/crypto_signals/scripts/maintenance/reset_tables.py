"""
Maintenance script to reset BigQuery tables to fix Schema Drift.

Usage:
    python -m crypto_signals.scripts.maintenance.reset_tables [--dry-run]
"""

import typer
from google.cloud import bigquery
from loguru import logger

from crypto_signals.config import get_settings

app = typer.Typer()


@app.command()
def reset_tables(dry_run: bool = False, force: bool = False):
    """
    Delete mismatched BigQuery tables so they can be recreated with clean schema.
    """
    settings = get_settings()
    client = bigquery.Client(project=settings.GOOGLE_CLOUD_PROJECT)

    env_suffix = "" if settings.ENVIRONMENT == "PROD" else "_test"

    # List of tables to reset (based on Diagnosis)
    # Staging + Fact for affected pipelines
    tables_to_reset = [
        # Trades
        f"crypto_analytics.stg_trades_import{env_suffix}",
        f"crypto_analytics.fact_trades{env_suffix}",
        # Expired Signals
        f"crypto_analytics.stg_signals_expired_import{env_suffix}",
        f"crypto_analytics.fact_signals_expired{env_suffix}",
        # Rejected Signals
        f"crypto_analytics.stg_rejected_signals{env_suffix}",
        f"crypto_analytics.fact_rejected_signals{env_suffix}",
    ]

    logger.info(f"Target Project: {settings.GOOGLE_CLOUD_PROJECT}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info("The following tables will be DELETED:")
    for t in tables_to_reset:
        logger.info(f" - {t}")

    if dry_run:
        logger.success("DRY RUN: No changes made.")
        return

    if not force:
        confirm = typer.confirm("Are you sure you want to delete these tables?")
        if not confirm:
            logger.info("Aborted.")
            return

    success_count = 0
    for table_id in tables_to_reset:
        full_table_id = f"{settings.GOOGLE_CLOUD_PROJECT}.{table_id}"
        try:
            logger.info(f"Deleting {full_table_id}...")
            client.delete_table(full_table_id, not_found_ok=True)
            logger.success(f"Deleted {full_table_id}")
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to delete {full_table_id}: {e}")

    logger.success(
        f"Complete. {success_count} tables deleted. Run the job again to recreate them."
    )


if __name__ == "__main__":
    app()
