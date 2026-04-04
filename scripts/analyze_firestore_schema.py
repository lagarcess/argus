#!/usr/bin/env python3
"""
Firestore Schema Analysis Script.

Deep analysis of all Firestore collections (live_signals, rejected_signals, live_positions)
to identify:
- Missing fields compared to Pydantic schemas
- Extra/legacy fields not in schema
- Field naming inconsistencies (snake_case vs camelCase)
- Type mismatches
- Data quality issues

Outputs a detailed JSON report for implementing cleanup/migration.
"""

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

# Add src to path for running as standalone script
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from crypto_signals.config import get_settings
from crypto_signals.domain.schemas import Position, Signal
from crypto_signals.secrets_manager import init_secrets
from google.cloud import firestore
from loguru import logger
from pydantic import ValidationError

# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {message}",
    level="INFO",
)

# Define expected fields from Pydantic schemas
SIGNAL_EXPECTED_FIELDS = set(Signal.model_fields.keys())
POSITION_EXPECTED_FIELDS = set(Position.model_fields.keys())

# Additional operational fields added by repository layer
SIGNAL_OPERATIONAL_FIELDS = {"rejected_at"}
POSITION_OPERATIONAL_FIELDS = {"created_at", "updated_at"}


def get_field_type(value: Any) -> str:
    """Get a string representation of a value's type."""
    if value is None:
        return "null"
    elif isinstance(value, bool):
        return "boolean"
    elif isinstance(value, int):
        return "integer"
    elif isinstance(value, float):
        return "float"
    elif isinstance(value, str):
        return "string"
    elif isinstance(value, list):
        return "array"
    elif isinstance(value, dict):
        return "object"
    elif isinstance(value, datetime):
        return "datetime"
    else:
        return type(value).__name__


def analyze_collection(
    db: firestore.Client,
    collection_name: str,
    expected_fields: set[str],
    operational_fields: set[str],
    pydantic_model: type,
) -> dict[str, Any]:
    """Analyze a Firestore collection against expected schema."""

    logger.info(f"Analyzing collection: {collection_name}")

    docs = list(db.collection(collection_name).stream())
    total_count = len(docs)

    if total_count == 0:
        return {
            "collection": collection_name,
            "total_documents": 0,
            "message": "Collection is empty",
        }

    # Analysis containers
    all_fields_seen = set()
    field_presence_count = Counter()
    field_type_distribution = defaultdict(Counter)
    missing_required_docs = []
    extra_fields_docs = []
    validation_errors = []
    sample_documents = []

    # Field naming analysis
    camel_case_fields = set()
    snake_case_fields = set()

    all_expected = expected_fields | operational_fields

    for doc in docs:
        data = doc.to_dict()
        doc_fields = set(data.keys())
        all_fields_seen.update(doc_fields)

        # Count field presence
        for field in doc_fields:
            field_presence_count[field] += 1
            field_type_distribution[field][get_field_type(data[field])] += 1

            # Check naming convention
            if "_" in field:
                snake_case_fields.add(field)
            elif field[0].islower() and any(c.isupper() for c in field):
                camel_case_fields.add(field)

        # Check for missing required fields
        # Filter to truly required fields (non-Optional in schema)
        required_fields = {
            name
            for name, field_info in pydantic_model.model_fields.items()
            if field_info.is_required()
        }
        missing_truly_required = required_fields - doc_fields

        if missing_truly_required:
            missing_required_docs.append(
                {
                    "id": doc.id,
                    "missing_required": list(missing_truly_required),
                }
            )

        # Check for extra fields (not in expected or operational)
        extra_fields = doc_fields - all_expected
        if extra_fields:
            extra_fields_docs.append(
                {
                    "id": doc.id,
                    "extra_fields": list(extra_fields),
                }
            )

        # Attempt Pydantic validation
        try:
            pydantic_model(**data)
        except ValidationError as e:
            validation_errors.append(
                {
                    "id": doc.id,
                    "errors": [
                        {
                            "field": ".".join(str(loc) for loc in err["loc"]),
                            "type": err["type"],
                            "msg": err["msg"],
                        }
                        for err in e.errors()
                    ],
                }
            )

        # Store first 3 sample documents for reference
        if len(sample_documents) < 3:
            # Convert datetime objects for JSON serialization
            serializable_data = {}
            for k, v in data.items():
                if isinstance(v, datetime):
                    serializable_data[k] = v.isoformat()
                elif isinstance(v, (list, dict)):
                    serializable_data[k] = v
                else:
                    serializable_data[k] = v
            sample_documents.append({"id": doc.id, "data": serializable_data})

    # Calculate field coverage (% of docs having each field)
    field_coverage = {
        field: {
            "count": count,
            "percentage": round(count / total_count * 100, 1),
            "in_schema": field in expected_fields,
            "operational": field in operational_fields,
            "types": dict(field_type_distribution[field]),
        }
        for field, count in field_presence_count.items()
    }

    # Fields expected by schema but never seen in any document
    never_present = expected_fields - all_fields_seen

    # Fields seen but not in schema
    unexpected_fields = all_fields_seen - all_expected

    return {
        "collection": collection_name,
        "total_documents": total_count,
        "schema_analysis": {
            "expected_fields_count": len(expected_fields),
            "operational_fields_count": len(operational_fields),
            "actual_unique_fields_count": len(all_fields_seen),
            "never_present_schema_fields": sorted(never_present),
            "unexpected_fields_not_in_schema": sorted(unexpected_fields),
        },
        "naming_convention_analysis": {
            "snake_case_fields": sorted(snake_case_fields),
            "camel_case_fields": sorted(camel_case_fields),
            "mixed_convention": bool(camel_case_fields and snake_case_fields),
        },
        "field_coverage": dict(
            sorted(field_coverage.items(), key=lambda x: (-x[1]["percentage"], x[0]))
        ),
        "validation_summary": {
            "documents_with_validation_errors": len(validation_errors),
            "documents_with_missing_required": len(missing_required_docs),
            "documents_with_extra_fields": len(extra_fields_docs),
        },
        "validation_errors": validation_errors[:10],  # First 10 for brevity
        "missing_required_docs": missing_required_docs[:10],
        "extra_fields_docs": extra_fields_docs[:10],
        "sample_documents": sample_documents,
    }


def export_all_data(db: firestore.Client, output_path: Path) -> None:
    """Export all Firestore data to JSON for offline analysis."""
    logger.info("Exporting all Firestore data...")

    collections_to_export = [
        "live_signals",
        "rejected_signals",
        "live_positions",
        "test_signals",
        "test_rejected_signals",
        "test_positions",
    ]
    data_export = {}

    for collection_name in collections_to_export:
        docs = list(db.collection(collection_name).stream())
        collection_data = {}

        for doc in docs:
            raw_data = doc.to_dict()
            # Convert datetime objects for JSON serialization
            serializable_data = {}
            for k, v in raw_data.items():
                if isinstance(v, datetime):
                    serializable_data[k] = v.isoformat()
                else:
                    serializable_data[k] = v
            collection_data[doc.id] = serializable_data

        data_export[collection_name] = collection_data
        logger.info(f"  {collection_name}: {len(collection_data)} documents")

    with open(output_path, "w") as f:
        json.dump(data_export, f, indent=2, default=str)

    logger.info(f"Data exported to: {output_path}")


def main():
    """Run comprehensive Firestore schema analysis."""
    logger.info("=" * 60)
    logger.info("FIRESTORE SCHEMA ANALYSIS")
    logger.info("=" * 60)

    # Initialize secrets
    if not init_secrets():
        logger.critical("Failed to load required secrets. Exiting.")
        sys.exit(1)

    try:
        # Initialize Firestore client
        settings = get_settings()
        db = firestore.Client(project=settings.GOOGLE_CLOUD_PROJECT)

        # Run analysis on each collection
        results = {
            "analysis_timestamp": datetime.now().isoformat(),
            "collections": {},
        }

        # Analyze live_signals (PROD)
        results["collections"]["live_signals"] = analyze_collection(
            db, "live_signals", SIGNAL_EXPECTED_FIELDS, SIGNAL_OPERATIONAL_FIELDS, Signal
        )

        # Analyze rejected_signals (PROD)
        results["collections"]["rejected_signals"] = analyze_collection(
            db,
            "rejected_signals",
            SIGNAL_EXPECTED_FIELDS,
            SIGNAL_OPERATIONAL_FIELDS,
            Signal,
        )

        # Analyze live_positions (PROD)
        results["collections"]["live_positions"] = analyze_collection(
            db,
            "live_positions",
            POSITION_EXPECTED_FIELDS,
            POSITION_OPERATIONAL_FIELDS,
            Position,
        )

        # Analyze test_signals (TEST)
        results["collections"]["test_signals"] = analyze_collection(
            db, "test_signals", SIGNAL_EXPECTED_FIELDS, SIGNAL_OPERATIONAL_FIELDS, Signal
        )

        # Analyze test_rejected_signals (TEST)
        results["collections"]["test_rejected_signals"] = analyze_collection(
            db,
            "test_rejected_signals",
            SIGNAL_EXPECTED_FIELDS,
            SIGNAL_OPERATIONAL_FIELDS,
            Signal,
        )

        # Analyze test_positions (TEST)
        results["collections"]["test_positions"] = analyze_collection(
            db,
            "test_positions",
            POSITION_EXPECTED_FIELDS,
            POSITION_OPERATIONAL_FIELDS,
            Position,
        )

        # Output directory
        output_dir = Path(__file__).parent.parent / "temp" / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save analysis report
        report_path = output_dir / "firestore_schema_analysis.json"
        with open(report_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f"\nAnalysis report saved: {report_path}")

        # Export raw data for further analysis
        export_path = output_dir / "firestore_export.json"
        export_all_data(db, export_path)

        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)

        for collection_name, analysis in results["collections"].items():
            if analysis.get("total_documents", 0) == 0:
                logger.info(f"\n{collection_name}: EMPTY")
                continue

            schema_info = analysis.get("schema_analysis", {})
            validation_info = analysis.get("validation_summary", {})
            naming_info = analysis.get("naming_convention_analysis", {})

            logger.info(f"\n📊 {collection_name.upper()}")
            logger.info(f"   Documents: {analysis['total_documents']}")
            logger.info(
                f"   Unique fields seen: {schema_info.get('actual_unique_fields_count', 0)}"
            )

            never_present = schema_info.get("never_present_schema_fields", [])
            if never_present:
                logger.warning(
                    f"   ⚠️  Schema fields NEVER present in data: {never_present}"
                )

            unexpected = schema_info.get("unexpected_fields_not_in_schema", [])
            if unexpected:
                logger.warning(f"   ⚠️  Unexpected fields (not in schema): {unexpected}")

            if naming_info.get("mixed_convention"):
                logger.warning("   ⚠️  Mixed naming conventions detected!")
                logger.warning(
                    f"      camelCase: {naming_info.get('camel_case_fields', [])}"
                )

            if validation_info.get("documents_with_validation_errors", 0) > 0:
                logger.error(
                    f"   ❌ Validation errors: {validation_info['documents_with_validation_errors']} docs"
                )

        logger.info("\n" + "=" * 60)
        logger.info("Review the JSON reports in ./output/ for detailed findings.")
        logger.info("=" * 60)

        sys.exit(0)

    except Exception as e:
        logger.critical(f"Analysis failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
