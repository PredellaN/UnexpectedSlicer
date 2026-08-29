#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

TMPDIR="$(mktemp -d)"
cleanup() { rm -rf "$TMPDIR"; }
trap cleanup EXIT

mapfile -t FILES < <(git ls-files -co --exclude-standard \
    | grep -v -xE '(\.gitignore|build\.sh)') 

tar -cf - "${FILES[@]}" | tar -xf - -C "$TMPDIR"

BLENDER_BIN="${BLENDER_BIN:-}"
if [ -z "$BLENDER_BIN" ]; then
    if command -v blender &>/dev/null; then
        BLENDER_BIN="blender"
    else
        for candidate in "$HOME/Applications"/blender-*/blender /usr/bin/blender /usr/local/bin/blender; do
            if [ -x "$candidate" ]; then
                BLENDER_BIN="$candidate"
                break
            fi
        done
    fi
fi

if [ -z "$BLENDER_BIN" ]; then
    echo "Error: blender executable not found" >&2
    exit 1
fi

cd "$TMPDIR"
"$BLENDER_BIN" \
  --command extension build --split-platforms \
  --output-filepath "$SCRIPT_DIR/release/UnexpectedSlicer.zip"

cd "$SCRIPT_DIR"
