import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import bigquery

# Path to migration file (relative to script)
MIGRATION_FILE = Path(__file__).parent / "schema_migration.sql"


def check_preconditions():
    """Verify environment setup before running."""
    # 1. Check Auth (User Request)
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS") and not os.getenv(
        "GOOGLE_CLOUD_PROJECT"
    ):
        # Allow implicit credentials if project is set, but warn
        print(
            "WARNING: GOOGLE_APPLICATION_CREDENTIALS not set. Using default/implicit auth."
        )

    # 2. Check Project ID
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        print("ERROR: GOOGLE_CLOUD_PROJECT is required but not set.")
        sys.exit(1)

    return project_id


def run_migration():
    load_dotenv()

    print("=== Crypto Sentinel Schema Hardening ===")
    project_id = check_preconditions()
    print(f"Target Project: {project_id}")

    client = bigquery.Client(project=project_id)

    # 3. Read and Inject Variables
    try:
        with open(MIGRATION_FILE, "r") as f:
            raw_sql = f.read()
    except FileNotFoundError:
        print(f"ERROR: Migration file not found at {MIGRATION_FILE}")
        sys.exit(1)

    sanitized_sql = raw_sql.replace("{{PROJECT_ID}}", project_id)

    # 4. Execute Queries
    # We split by predefined delimiter or just execute script if BQ supports it.
    # The python client supports scripts with multiple statements.
    print("Executing Migration SQL...")
    try:
        query_job = client.query(sanitized_sql)
        query_job.result()  # Wait for completion
        print("✅ Migration executed successfully.")
        print("   - Fact Table: ALTERED (New columns added)")
        print("   - Staging Table: RESET (Dropped and Recreated via LIKE)")

    except Exception as e:
        print(f"❌ Migration FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_migration()
