#!/usr/bin/env bash
# Download MRT2 weights and generate audio with the native CUDA engine.
#
#   run_demo.sh "<prompt>" <model_name> [num_frames]
#   e.g.  run_demo.sh "disco funk" mrt2_small 100      # 100 frames = 4.0s
#
# Model assets land under ~/Documents/Magenta/magenta-rt-v2/ (per upstream).
set -euo pipefail

PROMPT="${1:-a jazz piano trio}"
MODEL="${2:-mrt2_small}"
FRAMES="${3:-100}"
MRT_SRC="${MRT_SRC:-/opt/magenta-realtime}"
ASSETS="${HOME}/Documents/Magenta/magenta-rt-v2"

# ---- Python env: only needed for the `mrt` model-downloader CLI -------------
if [ ! -d /opt/mrtvenv ]; then
  echo "==> Creating Python env for the model-downloader CLI"
  uv venv --python 3.12 /opt/mrtvenv
  # CPU JAX is plenty just to drive `mrt models download`.
  /opt/mrtvenv/bin/python -m pip install --quiet --upgrade pip
  /opt/mrtvenv/bin/pip install --quiet "magenta-rt"
fi
export PATH="/opt/mrtvenv/bin:${PATH}"

# ---- Download shared resources + the chosen streaming model ----------------
if [ ! -d "${ASSETS}/resources/musiccoca" ]; then
  echo "==> mrt models init (MusicCoCa + SpectroStream resources)"
  mrt models init
fi
if [ ! -f "${ASSETS}/models/${MODEL}/${MODEL}.mlxfn" ]; then
  echo "==> mrt models download (${MODEL}, pre-exported .mlxfn)"
  mrt models download "${MODEL}" || mrt models download
fi

# ---- Generate with the native engine ---------------------------------------
HELLO="${MRT_SRC}/build/examples/hello_mrt2/hello_mrt2"
[ -x "${HELLO}" ] || { echo "Build first: build_cuda.sh"; exit 1; }

echo "==> Generating: \"${PROMPT}\"  (${FRAMES} frames)"
time "${HELLO}" \
  "${ASSETS}/models/${MODEL}/${MODEL}.mlxfn" \
  "${ASSETS}/resources" \
  "${FRAMES}" \
  --prompt "${PROMPT}" \
  --output "out_${MODEL}.wav" --force

echo "==> Wrote out_${MODEL}.wav"
echo "    Real-time check: ${FRAMES} frames = $(awk "BEGIN{printf \"%.2f\", ${FRAMES}*0.04}")s of audio."
echo "    If 'real' time above is LESS than that, you're generating faster than real-time (RTF>1)."
