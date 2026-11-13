#!/usr/bin/env bash
# Source this file to add project tools in cmd/ to your current shell PATH
# Usage: source cmd/env.sh  (or: . cmd/env.sh)

if [ -n "${BASH_SOURCE[0]}" ]; then
    SCRIPT_PATH="${BASH_SOURCE[0]}"
elif [ -n "${ZSH_VERSION}" ]; then
    SCRIPT_PATH="${(%):-%x}"
else
    SCRIPT_PATH="$0"
fi

CMD_DIR="$(cd "$(dirname "${SCRIPT_PATH}")" && pwd)"

if [[ ":$PATH:" != *":$CMD_DIR:"* ]]; then
    export PATH="${CMD_DIR}:${PATH}"
    echo "[✓] Added '${CMD_DIR}' to current PATH."
else
    echo "[✓] '${CMD_DIR}' is already in PATH."
fi
