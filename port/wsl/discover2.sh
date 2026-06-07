#!/usr/bin/env bash
set +e
MRT="$HOME/mrt2/.venv/bin/mrt"
echo "=== mrt checkpoints --help ==="; "$MRT" checkpoints --help 2>&1 | head -30
echo; echo "=== mrt checkpoints download --help ==="; "$MRT" checkpoints download --help 2>&1 | head -30
echo; echo "=== mrt models download --help ==="; "$MRT" models download --help 2>&1 | head -30
