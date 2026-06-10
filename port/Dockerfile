# Magenta RealTime 2: native C++ engine on NVIDIA/CUDA.
# Builds `core` + the headless `hello_mrt2` CLI from the open magenta-realtime
# source with MLX's CUDA backend enabled.
#
# Works on RunPod (any NVIDIA pod) and on a local Linux box / WSL2 with a 4090.
#
# Build:  docker build -t mrt2-cuda -f Dockerfile .
# Run:    docker run --gpus all -it mrt2-cuda bash
#         then inside:  /opt/port/run_demo.sh "disco funk" mrt2_small
#
# NOTE: nvidia-container-toolkit / `--gpus all` required. On RunPod pick a
# "CUDA 12.x devel" template (the runtime-only images lack nvcc).

# cudnn-devel gives us nvcc + cuDNN headers that MLX's CUDA backend needs.
FROM nvidia/cuda:12.6.2-cudnn-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV CUDACXX=/usr/local/cuda/bin/nvcc
# Override at build/run time for your card: 4090=89, A100=80, H100=90, 5090=120.
ENV CMAKE_CUDA_ARCHITECTURES=89

RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl ca-certificates build-essential ninja-build \
        python3 python3-pip python3-venv \
        zlib1g-dev libomp-dev \
    && rm -rf /var/lib/apt/lists/*

# uv for the Python side (model download + JAX/MLX validation layers).
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Repo pins `cmake<3.28`; honor it for build-system parity with upstream.
RUN pip3 install --no-cache-dir "cmake<3.28"

WORKDIR /opt
COPY patch_cmake.py build_cuda.sh run_demo.sh /opt/port/
RUN chmod +x /opt/port/*.sh

# Clone + patch + build the native CUDA engine. Heavy step (MLX+TFLite from
# source). If you'd rather iterate, comment this out and run it interactively.
RUN /opt/port/build_cuda.sh

WORKDIR /opt/magenta-realtime
CMD ["bash"]
