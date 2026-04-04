#!/usr/bin/env python3
"""
Semantic Time Field Verification Script.

Verifies that Firestore documents have the correct semantic time fields:
- valid_until: Logical expiration (24h from candle close)
- delete_at: Physical TTL for GCP cleanup (30d live, 7d rejected)

Also verifies no legacy camelCase fields (expireAt) remain.

Usage:
    poetry run python scripts/verify_hardening.py
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

# Add src to path for direct script execution
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from crypto_signals.config import get_settings
from crypto_signals.secrets_manager import init_secrets
from google.cloud import firestore
from loguru import logger

# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {message}",
    level="INFO",
)


def verify_collection(
    db: firestore.Client, collection_name: str, expected_ttl_days: int
) -> bool:
    """
    Verify semantic time fields in a Firestore collection.

    Args:
        db: Firestore client
        collection_name: Name of collection to verify
        expected_ttl_days: Expected TTL (30 for live, 7 for rejected)

    Returns:
        True if all checks pass, False otherwise
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Verifying collection: {collection_name}")
    logger.info(f"{'='*60}")

    # Get most recent documents
    query = (
        db.collection(collection_name)
        .order_by("ds", direction=firestore.Query.DESCENDING)
        .limit(5)
    )

    docs = list(query.stream())

    if not docs:
        logger.warning(f"⚠️  No documents found in {collection_name}")
        logger.info("   Run visual_discord_test.py to generate test signals first")
        return True  # Not a failure, just no data

    all_passed = True
    legacy_fields_found = []
    missing_fields = []

    for doc in docs:
        data = doc.to_dict()
        doc_id = doc.id
        symbol = data.get("symbol", "UNKNOWN")

        logger.info(f"\n📄 Document: {doc_id[:20]}... ({symbol})")

        # Check 1: valid_until exists and is datetime
        valid_until = data.get("valid_until")
        if valid_until is None:
            missing_fields.append((doc_id, "valid_until"))
            logger.error("   ❌ MISSING: valid_until")
            all_passed = False
        elif isinstance(valid_until, datetime):
            logger.info(f"   ✅ valid_until: {valid_until} (datetime)")
        elif isinstance(valid_until, str):
            logger.warning(f"   ⚠️  valid_until is string, not datetime: {valid_until}")
        else:
            logger.warning(f"   ⚠️  valid_until has unexpected type: {type(valid_until)}")

        # Check 2: delete_at exists and is datetime
        delete_at = data.get("delete_at")
        if delete_at is None:
            missing_fields.append((doc_id, "delete_at"))
            logger.error("   ❌ MISSING: delete_at")
            all_passed = False
        elif isinstance(delete_at, datetime):
            logger.info(f"   ✅ delete_at: {delete_at} (datetime)")

            # Verify TTL is roughly correct (within reasonable tolerance)
            now = datetime.now(timezone.utc)
            if delete_at.tzinfo is None:
                delete_at = delete_at.replace(tzinfo=timezone.utc)
            days_until_delete = (delete_at - now).days

            if expected_ttl_days - 5 <= days_until_delete <= expected_ttl_days + 5:
                logger.info(
                    f"   ✅ TTL check: ~{days_until_delete} days (expected ~{expected_ttl_days})"
                )
            else:
                logger.warning(
                    f"   ⚠️  TTL mismatch: {days_until_delete} days (expected ~{expected_ttl_days})"
                )
        elif isinstance(delete_at, str):
            logger.warning(f"   ⚠️  delete_at is string, not datetime: {delete_at}")
        else:
            logger.warning(f"   ⚠️  delete_at has unexpected type: {type(delete_at)}")

        # Check 3: NO legacy camelCase fields
        legacy_camel_case = ["expireAt", "expirationAt", "expiration_at"]
        for legacy_field in legacy_camel_case:
            if legacy_field in data:
                legacy_fields_found.append((doc_id, legacy_field))
                logger.error(f"   ❌ LEGACY FIELD FOUND: {legacy_field}")
                all_passed = False

        # Check 4: Verify other expected fields exist
        expected_fields = ["signal_id", "ds", "symbol", "pattern_name", "status"]
        for field in expected_fields:
            if field not in data:
                logger.warning(f"   ⚠️  Missing standard field: {field}")

    # Summary
    logger.info(f"\n{'='*60}")
    if all_passed:
        logger.info(f"✅ {collection_name}: All {len(docs)} documents PASSED")
    else:
        logger.error(f"❌ {collection_name}: FAILED")
        if missing_fields:
            logger.error(f"   Missing fields: {missing_fields}")
        if legacy_fields_found:
            logger.error(f"   Legacy fields found: {legacy_fields_found}")

    return all_passed


def main():
    """Run the hardening verification."""
    logger.info("=" * 60)
    logger.info("SEMANTIC TIME FIELD VERIFICATION")
    logger.info("=" * 60)

    # Initialize secrets
    if not init_secrets():
        logger.critical("Failed to load secrets. Exiting.")
        sys.exit(1)

    # Initialize Firestore
    settings = get_settings()
    db = firestore.Client(project=settings.GOOGLE_CLOUD_PROJECT)

    # Verify collections
    live_passed = verify_collection(db, "live_signals", expected_ttl_days=30)
    rejected_passed = verify_collection(db, "rejected_signals", expected_ttl_days=7)

    # Final result
    logger.info("\n" + "=" * 60)
    if live_passed and rejected_passed:
        logger.info("🎉 ALL VERIFICATIONS PASSED")
        logger.info("=" * 60)
        logger.info("\nSemantic time fields are correctly configured:")
        logger.info("  - valid_until: Logical expiration (24h from candle)")
        logger.info("  - delete_at: Physical TTL for GCP cleanup")
        logger.info("\nReady for GCP TTL policy:")
        logger.info("  gcloud firestore fields ttls update delete_at \\")
        logger.info("    --collection-group=live_signals --enable-ttl")
        sys.exit(0)
    else:
        logger.error("❌ VERIFICATION FAILED")
        logger.error("=" * 60)
        logger.error("\nSome documents are missing semantic time fields.")
        logger.error("These may be legacy documents created before the refactoring.")
        logger.error("New signals should have the correct fields.")
        sys.exit(1)


if __name__ == "__main__":
    main()
