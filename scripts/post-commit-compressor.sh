#!/bin/bash
# OMEGA CLAW - Auto-Compressor Hook
# This git hook runs compressor.py every time a commit is made, 
# capturing the live state of the repo into a single context file.

# Find the project root (where the commit happened)
PROJECT_ROOT=$(git rev-parse --show-toplevel)

# Define where the compressor script lives 
# (Assuming it's installed globally or accessible via PATH, or we use a firm relative path)
COMPRESSOR_SCRIPT="$PROJECT_ROOT/USER SPACE/omega-claw/ai/dev-mode/compressor.py"
OUTPUT_FILE="$PROJECT_ROOT/USER SPACE/logging/context.md"

if [ -f "$COMPRESSOR_SCRIPT" ]; then
    echo "[Omega] Automatically compressing repository state to $OUTPUT_FILE..."
    python3 "$COMPRESSOR_SCRIPT" "$PROJECT_ROOT/USER SPACE/project/src" "$OUTPUT_FILE"
    echo "[Omega] Context compression complete."
else
    echo "[Omega] Note: compressor.py not found. Skipping auto-compression."
fi
