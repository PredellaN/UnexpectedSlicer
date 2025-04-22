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

cd "$TMPDIR"
blender \
  --command extension build --split-platforms \
  --output-filepath "$SCRIPT_DIR/release/UnexpectedSlicer_1.0.0.zip"

cd "$SCRIPT_DIR"
