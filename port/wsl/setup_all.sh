#!/usr/bin/env bash
# Idempotent WSL-side setup for MRT2 Studio. Safe to run repeatedly.
# Installs uv + the Python engine + the model, then verifies. Each step is
# skipped when already satisfied, so re-runs are fast and never destructive.
# Emits a final line: "MRT2_SETUP_OK" or "MRT2_SETUP_FAILED: <reason>".
set -uo pipefail

say(){ echo "[mrt2-setup] $*"; }
fail(){ echo "MRT2_SETUP_FAILED: $*"; exit 1; }

WORK="$HOME/mrt2"; VENV="$WORK/.venv"; PY="$VENV/bin/python"; MRT="$VENV/bin/mrt"
ASSETS="$HOME/Documents/Magenta/magenta-rt-v2"
CKPT="$ASSETS/checkpoints/mrt2_small.safetensors"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # for deps_doctor.sh (sibling)
mkdir -p "$WORK"

# --- 0. GPU passthrough sanity (warn, don't fail; CPU still imports) ----------
if [ -e /usr/lib/wsl/lib/libcuda.so ] || [ -e /usr/lib/wsl/lib/libcuda.so.1 ]; then
  say "GPU passthrough: libcuda present"
else
  say "WARNING: /usr/lib/wsl/lib/libcuda.so not found. Update your NVIDIA driver on Windows."
fi

# --- 1. uv ---------------------------------------------------------------------
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/uv" ]; then
  say "installing uv"
  if command -v pip3 >/dev/null 2>&1; then
    pip3 install --user --break-system-packages -q uv 2>/dev/null || true
  fi
  if ! command -v uv >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/uv" ]; then
    curl -LsSf https://astral.sh/uv/install.sh | sh || fail "could not install uv (no pip3 and curl failed)"
  fi
fi
UV="$(command -v uv || echo "$HOME/.local/bin/uv")"
[ -x "$UV" ] || fail "uv not runnable at $UV"
say "uv: $("$UV" --version 2>/dev/null || echo '?')"

# --- 2. venv -------------------------------------------------------------------
if [ ! -x "$PY" ]; then
  say "creating venv (CPython 3.12) at $VENV"
  "$UV" venv --python 3.12 "$VENV" || fail "venv creation failed"
fi

# --- 3. python deps (only if a required import is missing) ---------------------
deps_ok(){ "$PY" - <<'PY' >/dev/null 2>&1
import importlib
for m in ("jax","jaxlib","magenta_rt","numpy","soundfile"):
    importlib.import_module(m)
PY
}
if deps_ok; then
  say "python deps already present"
else
  say "installing the latest engine stack (magenta-rt, jax[cuda12], numpy, soundfile), large download, please wait"
  "$UV" pip install --python "$PY" -U "magenta-rt" "jax[cuda12]" "numpy" "soundfile" || \
    fail "pip install failed (check internet connection and disk space)"
  deps_ok || fail "deps still missing after install"
fi

# --- 4. model assets -----------------------------------------------------------
if [ ! -d "$ASSETS" ] || [ -z "$(ls -A "$ASSETS" 2>/dev/null)" ]; then
  say "downloading shared resources (MusicCoCa + SpectroStream)"
  "$MRT" models init --source hf || fail "model resources download failed"
else
  say "shared resources present"
fi
if [ ! -f "$CKPT" ]; then
  say "downloading checkpoint mrt2_small.safetensors (~1.1 GB)"
  "$MRT" checkpoints download mrt2_small.safetensors --source hf || fail "checkpoint download failed"
else
  say "checkpoint present"
fi
[ -f "$CKPT" ] || fail "checkpoint missing after download"

# --- 5. verify on the GPU (real generation) and self-heal the deps if needed ---
# The doctor verifies a real generation and, only if the freshly installed stack
# fails, restores the known-good floor. Keeps installs on the newest working set.
say "verifying the engine on your GPU (loads the model once)…"
bash "$HERE/deps_doctor.sh" "$VENV" || fail "engine verification failed (see messages above)"

echo "MRT2_SETUP_OK"
