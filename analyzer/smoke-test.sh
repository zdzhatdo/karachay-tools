#!/usr/bin/env bash
# Smoke test: forms checked by a native speaker must still get these analyses.
# Run inside the analyzer image: bash smoke-test.sh
set -euo pipefail

check() {
  local form=$1 expected=$2 output
  output=$(echo "$form" | apertium -d /src/lexicon krc-morph)
  if [[ $output != *"$expected"* ]]; then
    echo "FAIL: $form -> $output (expected $expected)"
    exit 1
  fi
  echo "ok: $form -> $expected"
}

check киштигим 'киштик<n><px1sg><nom>'
check Тибр 'Тибр<np><top><nom>'
