#!/usr/bin/env bash
# Download MRT2 shared resources + mrt2_small safetensors (for the JAX backend).
set -e
MRT="$HOME/mrt2/.venv/bin/mrt"
say() { echo "[mrt2-download] $*"; }

say "1/2 mrt models init  (MusicCoCa + SpectroStream shared resources)"
"$MRT" models init --source hf

say "2/2 mrt checkpoints download mrt2_small  (safetensors for JAX backend)"
"$MRT" checkpoints download mrt2_small --source hf

say "DONE. Asset tree:"
du -sh "$HOME/Documents/Magenta/magenta-rt-v2" 2>/dev/null || true
find "$HOME/Documents/Magenta/magenta-rt-v2" -maxdepth 3 -type f 2>/dev/null | head -60
