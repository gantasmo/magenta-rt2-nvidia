#!/usr/bin/env bash
# Clone, patch, and build the magenta-realtime native C++ engine for NVIDIA/CUDA.
# Produces: /opt/magenta-realtime/build/examples/hello_mrt2/hello_mrt2
#
# Env knobs:
#   MRT_SRC                 checkout dir          (default /opt/magenta-realtime)
#   CMAKE_CUDA_ARCHITECTURES  GPU arch  (4090=89, A100=80, H100=90, 5090=120)
#   JOBS                    parallel build jobs   (default: nproc)
set -euo pipefail

MRT_SRC="${MRT_SRC:-/opt/magenta-realtime}"
PORT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JOBS="${JOBS:-$(nproc)}"
ARCH="${CMAKE_CUDA_ARCHITECTURES:-89}"

echo "==> Magenta RT2 CUDA build"
echo "    src   = ${MRT_SRC}"
echo "    arch  = ${ARCH}    jobs = ${JOBS}"

if [ ! -d "${MRT_SRC}/.git" ]; then
  echo "==> Cloning magenta-realtime (no submodules: C++ core doesn't need them)"
  git clone --depth 1 https://github.com/magenta/magenta-realtime.git "${MRT_SRC}"
fi

echo "==> Patching CMake for Linux/CUDA"
python3 "${PORT_DIR}/patch_cmake.py" "${MRT_SRC}"

cd "${MRT_SRC}"
echo "==> Configuring (this fetches + builds MLX w/ CUDA, TFLite, sentencepiece — slow first time)"
cmake . -B build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DMLX_BUILD_CUDA=ON \
  -DCMAKE_CUDA_ARCHITECTURES="${ARCH}" \
  -DCMAKE_CUDA_COMPILER="${CUDACXX:-$(command -v nvcc)}"

echo "==> Building hello_mrt2 (pulls in magentart_core)"
cmake --build build --target hello_mrt2 -j"${JOBS}"

echo ""
echo "==> SUCCESS: $(ls -la "${MRT_SRC}/build/examples/hello_mrt2/hello_mrt2" 2>/dev/null || echo 'binary not found — check log above')"
echo "    Next: ${PORT_DIR}/run_demo.sh \"a jazz piano trio\" mrt2_small"
