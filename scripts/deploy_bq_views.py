"""
Deploy BigQuery Views.

Executes the SQL DDL files in scripts/bq/ against the configured GCP project.
Supports environment-based table suffixes via --env flag (PROD vs DEV/TEST).

Usage:
    poetry run python scripts/deploy_bq_views.py --env PROD
    poetry run python scripts/deploy_bq_views.py --env DEV --dry-run
"""

import argparse
import re
import sys
from pathlib import Path

from google.cloud import bigquery
from loguru import logger

# SQL files to deploy, in dependency order
SQL_FILES = [
    "mv_agg_strategy_daily.sql",
    "vw_summary_strategy_performance.sql",
]

# Strict validation pattern for GCP project IDs
_PROJECT_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")


def _validate_project_id(project_id: str) -> None:
    """Validate project_id to prevent SQL injection.

    GCP project IDs must be 6-30 chars, lowercase letters, digits, and hyphens.

    Raises:
        ValueError: If project_id doesn't match GCP naming rules.
    """
    if not _PROJECT_ID_PATTERN.match(project_id):
        raise ValueError(
            f"Invalid GCP project ID: '{project_id}'. "
            "Must be 6-30 chars, lowercase alphanumeric and hyphens only."
        )


def _resolve_env_suffix(env: str) -> str:
    """Return table suffix based on environment.

    Args:
        env: Environment name (PROD, DEV, TEST).

    Returns:
        Empty string for PROD, '_test' for DEV/TEST.
    """
    return "" if env.upper() == "PROD" else "_test"


def deploy_views(project_id: str, env: str, dry_run: bool = False) -> None:
    """Deploy all BQ views/materialized views.

    Args:
        project_id: GCP project ID (validated against naming rules).
        env: Environment name (PROD, DEV, TEST).
        dry_run: If True, only validate SQL without executing.
    """
    _validate_project_id(project_id)
    env_suffix = _resolve_env_suffix(env)

    bq_dir = Path(__file__).parent / "bq"
    client = bigquery.Client(project=project_id)

    logger.info(f"Deploying to project={project_id}, env={env}, suffix='{env_suffix}'")

    for sql_file in SQL_FILES:
        sql_path = bq_dir / sql_file
        if not sql_path.exists():
            logger.error(f"SQL file not found: {sql_path}")
            sys.exit(1)

        # Read and inject project_id and env_suffix
        sql = sql_path.read_text().format(
            project_id=project_id,
            env_suffix=env_suffix,
        )

        logger.info(f"{'[DRY-RUN] ' if dry_run else ''}Deploying {sql_file}...")

        if dry_run:
            # Validate syntax without executing
            job_config = bigquery.QueryJobConfig(dry_run=True, use_legacy_sql=False)
            try:
                client.query(sql, job_config=job_config)
                logger.info(f"  ✅ {sql_file} — syntax valid")
            except Exception as e:
                logger.error(f"  ❌ {sql_file} — {e}")
                sys.exit(1)
        else:
            try:
                job = client.query(sql)
                job.result()  # Wait for completion
                logger.info(f"  ✅ {sql_file} — deployed successfully")
            except Exception as e:
                logger.error(f"  ❌ {sql_file} — {e}")
                sys.exit(1)

    logger.info(
        "All views deployed successfully." if not dry_run else "Dry-run complete."
    )


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Deploy BigQuery views for analytics.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate SQL syntax without executing.",
    )
    parser.add_argument(
        "--project-id",
        type=str,
        default=None,
        help="GCP project ID. Defaults to GOOGLE_CLOUD_PROJECT env var.",
    )
    parser.add_argument(
        "--env",
        type=str,
        default="PROD",
        choices=["PROD", "DEV", "TEST"],
        help="Target environment. DEV/TEST appends '_test' suffix to table names.",
    )
    args = parser.parse_args()

    # Resolve project ID
    project_id = args.project_id
    if not project_id:
        import os

        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        logger.error("No project ID. Set --project-id or GOOGLE_CLOUD_PROJECT env var.")
        sys.exit(1)

    deploy_views(project_id, args.env, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
