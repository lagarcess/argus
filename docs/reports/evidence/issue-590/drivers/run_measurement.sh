#!/usr/bin/env bash
# The full live measurement on the current head (AGENTS.md Never-Violate 12
# comparison and the tests/evals README pre-merge gate). Both provider modes
# are forced on the command line: the env file pins synthetic market data and
# leaves the asset mode empty, and load_dotenv(override=False) keeps whatever
# the process environment already holds. The scorecard writer refuses a dirty
# worktree, so commit first. Paid: every measurement case, about 69 turns.
# Usage: I590_ENV_FILE=<env> bash run_measurement.sh
set -euo pipefail
ARGUS_RUN_LIVE_EVALS=1 \
ARGUS_EVAL_ENV_FILE="${I590_ENV_FILE:?}" \
ARGUS_MARKET_DATA_PROVIDER_MODE=live_provider \
ARGUS_ASSET_PROVIDER_MODE=live_provider \
ARGUS_RESEARCH_RAIL_ENABLED=true \
poetry run pytest tests/evals/test_measurement_eval_live.py -q --no-cov -p no:cacheprovider
