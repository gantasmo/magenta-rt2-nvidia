#!/usr/bin/env bash
# Discover the actual `mrt` CLI surface so we use the right commands.
set +e
VENV="$HOME/mrt2/.venv"
export PATH="$VENV/bin:$PATH"
MRT="$VENV/bin/mrt"

echo "=== which mrt ==="; ls -la "$MRT" 2>/dev/null
echo
echo "=== mrt --help ==="; "$MRT" --help 2>&1 | head -60
echo
echo "=== mrt models --help ==="; "$MRT" models --help 2>&1 | head -40
echo
echo "=== mrt jax --help ==="; "$MRT" jax --help 2>&1 | head -40
echo
echo "=== mrt jax generate --help ==="; "$MRT" jax generate --help 2>&1 | head -60
