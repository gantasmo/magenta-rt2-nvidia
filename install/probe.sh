#!/usr/bin/env bash
# WSL2 environment probe for MRT2 install. No quoting traps.
set +e

echo "=== sudo ==="
if sudo -n true 2>/dev/null; then echo "passwordless sudo: YES"; else echo "passwordless sudo: NO"; fi

echo
echo "=== venv module ==="
if python3 -m venv --help >/dev/null 2>&1; then echo "venv: available"; else echo "venv: MISSING"; fi

echo
echo "=== ensurepip ==="
python3 - <<'PY'
try:
    import ensurepip
    print("ensurepip: ok")
except Exception as e:
    print("ensurepip: missing", e)
PY

echo
echo "=== pip3 ==="
pip3 --version 2>/dev/null || echo "no pip3"

echo
echo "=== build tools ==="
for t in gcc g++ make; do
  if command -v "$t" >/dev/null 2>&1; then echo "$t: $(command -v $t)"; else echo "$t: MISSING"; fi
done

echo
echo "=== pipx / uv ==="
command -v uv >/dev/null 2>&1 && echo "uv: $(command -v uv)" || echo "uv: none"
