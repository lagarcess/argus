#!/bin/bash
# ==============================================================================
# Script: get_issue_details.sh
# Purpose: Fetch and format GitHub Issue details for Jules implementation.
#
# Usage: & "C:\Program Files\Git\bin\bash.exe" ./scripts/github/get_issue_details.sh <ISSUE_NUMBER>
# Example: & "C:\Program Files\Git\bin\bash.exe" ./scripts/github/get_issue_details.sh 181
#
# Prerequisites:
#   1. GitHub CLI (`gh`) must be installed and authenticated (`gh auth login`).
#   2. Run this script from the project root.
# ==============================================================================

# 1. Validate Input (Support stric  t int, #int, or GitHub URL)
if [[ "$1" =~ ([0-9]+)/?$ ]]; then
    ISSUE_NUM="${BASH_REMATCH[1]}"
else
    echo "❌ Error: Issue must be a positive integer, '#<num>', or a valid GitHub URL."
    echo "Usage: & \"C:\\Program Files\\Git\\bin\\bash.exe\" ./scripts/github/get_issue_details.sh <ISSUE_NUMBER_OR_URL>"
    exit 1
fi
OUTPUT_DIR="temp/issues"
JSON_FILE="$OUTPUT_DIR/issue_${ISSUE_NUM}_raw.json"

# 2. Setup Workspace
mkdir -p "$OUTPUT_DIR"

echo "🔵 [1/2] Fetching issue #$ISSUE_NUM via GitHub API..."

# 3. Fetch Data
# Redirect stderr to a temp log to show the actual GH CLI error if it fails
if ! gh issue view "$ISSUE_NUM" --json number,title,body,comments,labels > "$JSON_FILE" 2> "${JSON_FILE}.err"; then
    echo "❌ Error: API request failed."
    cat "${JSON_FILE}.err"
    rm -f "$JSON_FILE" "${JSON_FILE}.err"
    exit 1
fi
rm -f "${JSON_FILE}.err"

# 4. Validate Fetch
if [ ! -s "$JSON_FILE" ]; then
    echo "❌ Error: Failed to fetch data. File is empty."
    echo "   - Check if Issue #$ISSUE_NUM exists."
    echo "   - Check your internet connection."
    rm -f "$JSON_FILE"
    exit 1
fi

echo "🟢 Issue data downloaded to: $JSON_FILE"
echo "🔵 [2/2] Formatting issue ..."

# 5. Parse & Display
poetry run python scripts/github/parse_issues.py "$JSON_FILE"
