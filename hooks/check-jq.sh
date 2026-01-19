#!/bin/bash
# Session start hook: Check if jq is installed
# Warns user if jq is missing (required for directory protection)

if ! command -v jq &> /dev/null; then
    printf '{"systemMessage": "⚠️  jq is not installed. Directory protection (.block) requires jq. File operations in protected directories will be blocked until jq is installed."}\n'
fi

# Always exit 0 - don't block session start, just warn
exit 0
