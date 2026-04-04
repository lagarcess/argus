#!/bin/bash
# ==============================================================================
# Script: get_issue_details.sh
# Purpose: Fetch and format GitHub Issue details for agent implementation.
#
# Usage: & "C:\Program Files\Git\bin\bash.exe" ./.agent/scripts/github/get_issue_details.sh <ISSUE_NUMBER>
# Example: & "C:\Program Files\Git\bin\bash.exe" ./.agent/scripts/github/get_issue_details.sh 181
#
# Prerequisites:
#   1. GitHub CLI (`gh`) must be installed and authenticated (`gh auth login`).
#   2. Run from the project root.
# ==============================================================================

if [ -z "$1" ]; then
    echo "❌ Error: No issue number provided."
    echo "Usage: & \"C:\\Program Files\\Git\\bin\\bash.exe\" ./.agent/scripts/github/get_issue_details.sh <ISSUE_NUMBER>"
    exit 1
fi

ISSUE_NUM=$1
OUTPUT_DIR="temp/issues"
JSON_FILE="$OUTPUT_DIR/issue_${ISSUE_NUM}_raw.json"

echo "🔵 [1/2] Fetching Issue #$ISSUE_NUM via GitHub API..."

# Fetch issue data
mkdir -p "$OUTPUT_DIR"
gh issue view "$ISSUE_NUM" --json number,title,body,comments,labels > "$JSON_FILE" 2> "${JSON_FILE}.err"

# Check for GH CLI errors
if [ -s "${JSON_FILE}.err" ]; then
    echo "❌ Error: API request failed."
    cat "${JSON_FILE}.err"
    rm -f "$JSON_FILE" "${JSON_FILE}.err"
    exit 1
fi
rm -f "${JSON_FILE}.err"

# Validate fetch
if [ ! -s "$JSON_FILE" ]; then
    echo "❌ Error: Failed to fetch data. File is empty."
    echo "   - Check if Issue #$ISSUE_NUM exists."
    echo "   - Check your internet connection."
    rm -f "$JSON_FILE"
    exit 1
fi

echo "🟢 Issue data downloaded to: $JSON_FILE"
echo "🔵 [2/2] Formatting issue ..."

# Parse & Display
poetry run python .agent/scripts/github/parse_issues.py "$JSON_FILE"
