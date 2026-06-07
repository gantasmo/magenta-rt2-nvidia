#!/usr/bin/env bash
# Install Magenta RealTime 2 (JAX/CUDA backend) inside WSL2 Ubuntu.
# No sudo required: uv manages its own Python + pip.
set -e
export DEBIAN_FRONTEND=noninteractive

LOG_PREFIX="[mrt2-install]"
say() { echo "$LOG_PREFIX $*"; }

WORK="$HOME/mrt2"
VENV="$WORK/.venv"
mkdir -p "$WORK"

say "1/5 ensuring uv is installed (via system pip --user)"
if ! command -v uv >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/uv" ]; then
  pip3 install --user --break-system-packages -q uv
fi
export PATH="$HOME/.local/bin:$PATH"
UV="$(command -v uv || echo "$HOME/.local/bin/uv")"
say "uv = $UV"; "$UV" --version

say "2/5 creating venv at $VENV (uv fetches a standalone CPython 3.12)"
"$UV" venv --python 3.12 "$VENV"
export VIRTUAL_ENV="$VENV"
PY="$VENV/bin/python"

say "3/5 installing magenta-rt + jax[cuda12] + numpy (this downloads ~3GB of CUDA wheels)"
"$UV" pip install --python "$PY" "magenta-rt" "jax[cuda12]" numpy

say "4/5 versions installed:"
"$PY" - <<'PY'
import importlib.metadata as m
for p in ("magenta-rt","jax","jaxlib","numpy"):
    try: print(" ", p, m.version(p))
    except Exception as e: print(" ", p, "MISSING", e)
PY

say "5/5 checking JAX sees the GPU:"
"$PY" - <<'PY'
import jax
print("  jax backend:", jax.default_backend())
print("  jax devices:", jax.devices())
PY

say "DONE. venv at $VENV"
