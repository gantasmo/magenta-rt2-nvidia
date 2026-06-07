#!/usr/bin/env bash
set +e
PY="$HOME/mrt2/.venv/bin/python"
SP="$HOME/mrt2/.venv/lib/python3.12/site-packages/magenta_rt"

echo "=== paths module values ==="
"$PY" - <<'PY'
from magenta_rt import paths
print(" DEFAULT_MODEL_NAME:", paths.DEFAULT_MODEL_NAME)
for fn in ("outputs_dir","checkpoints_dir","assets_dir","base_dir","models_dir","resources_dir"):
    f = getattr(paths, fn, None)
    if callable(f):
        try: print(f" {fn}():", f())
        except Exception as e: print(f" {fn}(): ERR {e}")
PY

echo
echo "=== where is MagentaRT2Jax defined ==="
grep -rnl "class MagentaRT2Jax" "$SP" 2>/dev/null

echo
echo "=== checkpoint=None resolution in jax model ==="
grep -rnE "checkpoint|safetensors|\.safetensors|size|default" "$SP/jax/"*.py 2>/dev/null | grep -iE "checkpoint|safetensors" | head -40
