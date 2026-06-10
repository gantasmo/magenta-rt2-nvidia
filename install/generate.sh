#!/usr/bin/env bash
# Generate a .wav with MRT2 (JAX backend) and copy it to this folder's output/ dir.
# Usage: generate.sh "prompt text" [duration_seconds] [model]
set -e
VENV="$HOME/mrt2/.venv"
export PATH="$VENV/bin:$PATH"
MRT="$VENV/bin/mrt"

# Allocate GPU memory on demand instead of reserving it all up front.
export XLA_PYTHON_CLIENT_PREALLOCATE=false
export XLA_PYTHON_CLIENT_ALLOCATOR=platform

PROMPT="${1:-warm analog synthwave with a driving bassline and dreamy pads}"
DUR="${2:-10}"
MODEL="${3:-mrt2_small}"
ASSETS="$HOME/Documents/Magenta/magenta-rt-v2"

OUT="$HOME/mrt2/out"
mkdir -p "$OUT"
cd "$OUT"

echo "[gen] prompt   : $PROMPT"
echo "[gen] duration : ${DUR}s"
echo "[gen] model    : $MODEL"

# Marker so we can find whatever file(s) generate writes, wherever it writes them.
MARKER="$OUT/.marker"; : > "$MARKER"; sleep 1

set -x
"$MRT" jax generate --prompt "$PROMPT" --model "$MODEL" --duration "$DUR"
set +x

echo "[gen] searching for freshly written .wav files…"
FOUND="$(find "$OUT" "$ASSETS" "$HOME/mrt2" -type f -name '*.wav' -newer "$MARKER" 2>/dev/null)"
if [ -z "$FOUND" ]; then
  FOUND="$(find "$HOME" -type f -name '*.wav' -newer "$MARKER" 2>/dev/null | head -20)"
fi
echo "[gen] new wav files:"; echo "$FOUND"

# Copy results next to this script (output/), wherever the repo lives.
DEST="$(cd "$(dirname "$0")" && pwd)/output"
mkdir -p "$DEST"
n=0
while IFS= read -r f; do
  [ -z "$f" ] && continue
  cp -f "$f" "$DEST/" && echo "[gen] copied -> $DEST/$(basename "$f")"
  n=$((n+1))
done <<< "$FOUND"
echo "[gen] copied $n file(s) to $DEST"
ls -la "$DEST" 2>/dev/null
