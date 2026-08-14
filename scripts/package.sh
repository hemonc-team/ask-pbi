#!/usr/bin/env bash
# Сборка marketing skill: bootstrap zip + full zip (fallback).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
BOOT="$DIST/pbi-marketing-qa-bootstrap"
FULL="$DIST/pbi-marketing-qa"

rm -rf "$BOOT" "$FULL"
mkdir -p "$BOOT/pbi-marketing-qa" "$FULL/pbi-marketing-qa"

# Bootstrap: только loader для Upload once
cp "$ROOT/SKILL.bootstrap.md" "$BOOT/pbi-marketing-qa/SKILL.md"

# Full fallback zip (без bootstrap md, без __pycache__)
rsync -a \
  --exclude 'SKILL.bootstrap.md' \
  --exclude 'install.sh' \
  --exclude 'dist' \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  "$ROOT/" "$FULL/pbi-marketing-qa/"

chmod +x "$FULL/pbi-marketing-qa/scripts/pbi_run.sh"

(cd "$BOOT" && zip -r "$DIST/pbi-marketing-qa-bootstrap.zip" pbi-marketing-qa)
(cd "$FULL" && zip -r "$DIST/pbi-marketing-qa.zip" pbi-marketing-qa)

echo "Built:"
echo "  $DIST/pbi-marketing-qa-bootstrap.zip  (upload once в Claude)"
echo "  $DIST/pbi-marketing-qa.zip            (fallback без git)"
