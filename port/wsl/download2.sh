#!/usr/bin/env bash
# Corrected checkpoint download: pass the full filename incl. .safetensors
set -e
MRT="$HOME/mrt2/.venv/bin/mrt"
echo "[dl2] mrt checkpoints download mrt2_small.safetensors"
"$MRT" checkpoints download mrt2_small.safetensors --source hf
echo "[dl2] DONE. checkpoints dir:"
ls -la "$HOME/Documents/Magenta/magenta-rt-v2/checkpoints/" 2>/dev/null
