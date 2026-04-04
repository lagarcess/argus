import sys

from crypto_signals.observability import configure_logging
from crypto_signals.pipelines.account_snapshot import AccountSnapshotPipeline
from crypto_signals.secrets_manager import init_secrets
from loguru import logger


def verify_pipeline():
    """
    Manual trigger for AccountSnapshotPipeline.
    Verifies that Extract -> Transform -> Load -> Merge works with the new schema.
    """
    configure_logging(level="INFO")

    logger.info("=== Account Snapshot Verification ===")

    # 1. Load Secrets (Needed for BigQuery & Alpaca)
    if not init_secrets():
        logger.error("Failed to load secrets.")
        sys.exit(1)

    try:
        # 2. Initialize Pipeline
        pipeline = AccountSnapshotPipeline()
        logger.info(f"Initialized Pipeline: {pipeline.job_name}")
        logger.info(f"Target Project: {pipeline.bq_client.project}")
        logger.info(f"Staging Table: {pipeline.staging_table_id}")
        logger.info(f"Fact Table: {pipeline.fact_table_id}")

        # 3. Execution (Extract -> Transform -> Load -> Merge)
        logger.info("Starting pipeline execution...")
        pipeline.run()

        logger.success("✅ VERIFICATION SUCCESS: Pipeline ran end-to-end.")
        logger.info("BigQuery and Firestore are aligned.")

    except Exception as e:
        logger.error(f"❌ VERIFICATION FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    verify_pipeline()
