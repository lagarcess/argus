# Scripts Organization

This document explains the scripts organization and how to run diagnostic tools.

## Directory Structure

The project has two script directories with distinct purposes:

### `scripts/` (Root Level)
**Standalone scripts** for one-time setup, verification, and development tasks. These scripts:
- Require `sys.path.append` to import from `crypto_signals`
- Are NOT part of the installed package
- Are typically run once or occasionally
- Used for initial setup, migrations, and GCP verification

```
scripts/
├── setup_gcp.sh                # GCP initial setup
├── run_migration.py            # Schema migrations
├── schema_migration.sql        # SQL migration scripts
├── verify_firestore_config.py  # Configuration verification
├── verify_account_pipeline.py  # Account pipeline verification
├── verify_hardening.py         # Security hardening verification
├── analyze_firestore_schema.py # Schema analysis
├── inspect_firestore_signals.py# Signal inspection
├── purge_test_signals.py       # Test data cleanup
├── validate_assets.py          # Asset validation
├── generate_pattern_images.py  # Pattern image generation
├── parse_pr_comments.py        # PR comment visualization (rich output)
├── post_review.py              # Automated PR review posting (gh cli wrapper)
└── visual_discord_test.py      # Discord notification testing
```

**Run these with:**
```bash
poetry run python scripts/verify_firestore_config.py
```

### `src/crypto_signals/scripts/` (Package Module)
**Runtime scripts** that are part of the installed package. These scripts:
- Can be run with `python -m crypto_signals.scripts.*`
- Import from `crypto_signals` without path manipulation
- Are used for operational tasks during production

```
src/crypto_signals/scripts/
├── __init__.py
├── cleanup_firestore.py        # Firestore TTL cleanup (Legacy root script)
├── test_discord_notifications.py # Discord notification testing
├── diagnostics/                # System diagnostic tools
│   ├── __init__.py
│   ├── account_status.py       # Alpaca account summary
│   ├── book_balancing.py       # Full Ledger Reconciliation
│   ├── data_integrity_check.py # Firestore field audit
│   ├── forensic_analysis.py    # Order gap detection
│   ├── forensic_details.py     # Detailed position inspection
│   ├── health_check.py         # Connectivity verification
│   ├── schema_audit.py         # Pydantic schema audit
│   └── state_analysis.py       # Firestore state analysis
└── maintenance/                # Maintenance and cleanup utilities
    ├── __init__.py
    ├── cleanup_legacy_gaps.py  # Tag legacy orphans as resolved
    ├── fix_reverse_orphans.py  # Heal CLOSED_DB -> OPEN_ALPACA
    ├── migrate_schema.py       # BigQuery schema migration
    ├── purge_positions.py      # Purge positions (DEV/TEST only)
    ├── purge_signals.py        # Purge signals (DEV/TEST only)
    └── resurrect_positions.py  # Batch resurrect false-manual exits
```

**Run these with:**
```bash
poetry run python -m crypto_signals.scripts.cleanup_firestore
poetry run python -m crypto_signals.scripts.diagnostics.health_check
```

## Diagnostic Tools

The `diagnostics/` module provides comprehensive system health analysis:

### Available Diagnostics

| Script | Purpose | Output |
|--------|---------|--------|
| `account_status` | Alpaca account balance, positions, buying power | `temp/reports/account_status.txt` |
| `book_balancing` | Deep Ledger Audit (DB vs Alpaca History) | Console output |
| `state_analysis` | Firestore OPEN/CLOSED counts, active signals | `temp/reports/state_analysis.txt` |
| `forensic_analysis` | Cross-reference Firestore with Alpaca orders | Console output |
| `health_check` | Verify connectivity to all external services | Console output + Discord |

### Running Diagnostics

```bash
# Full diagnostic suite
poetry run python -m crypto_signals.scripts.diagnostics.account_status
poetry run python -m crypto_signals.scripts.diagnostics.state_analysis
poetry run python -m crypto_signals.scripts.diagnostics.forensic_analysis
poetry run python -m crypto_signals.scripts.diagnostics.book_balancing
# Check specific position ID with deep history lookback
poetry run python -m crypto_signals.scripts.diagnostics.book_balancing --target 70150867-... --limit 500
poetry run python -m crypto_signals.scripts.diagnostics.health_check
poetry run python -m crypto_signals.scripts.diagnostics.data_integrity_check
poetry run python -m crypto_signals.scripts.diagnostics.schema_audit

# All reports are written to temp/reports/ (gitignored)
```

### Using the `/diagnose` Workflow

If using the AI agent, simply run:
```
/diagnose
```

This will execute all diagnostics automatically and provide a summary.

## Output Location

All diagnostic outputs are written to `temp/reports/`:

```
temp/                           # Transient files (gitignored)
├── reports/                    # Diagnostic outputs
├── coverage/                   # Code coverage data (HTML/XML)
├── output/                     # Schema analysis and data exports
├── issues/                     # GitHub issue drafts (workflow: /implement)
├── plan/                       # Planning docs (workflow: /plan)
├── pr/                         # Pull request drafts (workflow: /pr)
├── review/                     # Code review outputs (workflow: /review)
└── verify/                     # Verification outputs (workflow: /verify)

```

These folders are used by AI agent workflows and keep transient files organized and out of version control.
