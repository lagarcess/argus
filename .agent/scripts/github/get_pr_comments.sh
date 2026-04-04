#!/bin/bash
# ==============================================================================
# Script: get_pr_comments.sh
# Purpose: Fetch and parse Inline Review Comments from a GitHub Pull Request.
#
# Usage: & "C:\Program Files\Git\bin\bash.exe" .agent/scripts/github/get_pr_comments.sh <PR_NUMBER>
# Example: & "C:\Program Files\Git\bin\bash.exe" .agent/scripts/github/get_pr_comments.sh 175
#
# Prerequisites:
#   1. GitHub CLI (`gh`) must be installed and authenticated (`gh auth login`).
#   2. Run this script from the project root.
# ==============================================================================

# 1. Validate Input (Strict Integer Check)
if [[ ! "$1" =~ ^[0-9]+$ ]]; then
    echo "❌ Error: PR Number must be a positive integer."
    echo "Usage: & \"C:\\Program Files\\Git\\bin\\bash.exe\" .agent/scripts/github/get_pr_comments.sh <PR_NUMBER>"
    exit 1
fi

PR_NUM=$1
OUTPUT_DIR="temp/pr_comments"
JSON_FILE="$OUTPUT_DIR/pr_${PR_NUM}_comments.json"

# 2. Setup Workspace
mkdir -p "$OUTPUT_DIR"

echo "🔵 [1/2] Fetching comments for PR #$PR_NUM via GitHub API..."

# 3. Fetch Data
# Note: ':owner' and ':repo' are magic placeholders.
# `gh` replaces them automatically based on your current git remote.
gh api "/repos/:owner/:repo/pulls/$PR_NUM/comments" > "$JSON_FILE"

# 4. Validate Fetch
if [ ! -s "$JSON_FILE" ]; then
    echo "❌ Error: Failed to fetch data. File is empty."
    echo "   - Check if PR #$PR_NUM exists."
    echo "   - Check your internet connection."
    exit 1
fi

echo "🟢 Comments downloaded to: $JSON_FILE"
echo "🔵 [2/2] Parsing comments into readable format..."

# 5. Parse & Display
poetry run python .agent/scripts/github/parse_pr_comments.py "$JSON_FILE"
