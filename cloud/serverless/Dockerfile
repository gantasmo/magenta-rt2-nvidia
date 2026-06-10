# RunPod serverless image for Magenta RealTime 2 (JAX/CUDA).
#
# Build for a specific model (mrt2_small bakes a ~1.1 GB checkpoint; mrt2_base
# bakes ~9.8 GB, bigger image, slower cold start, but no per-run download):
#   docker build --build-arg MRT2_MODEL=mrt2_small -t USER/mrt2-serverless:small .
#   docker push USER/mrt2-serverless:small
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ARG MRT2_MODEL=mrt2_small
ENV MRT2_MODEL=${MRT2_MODEL}
ENV DEBIAN_FRONTEND=noninteractive PIP_NO_CACHE_DIR=1
ENV XLA_PYTHON_CLIENT_PREALLOCATE=false

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip git ca-certificates libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip3 install --upgrade pip && pip3 install -r requirements.txt

# Bake the model so cold starts only load from local disk (no network fetch).
RUN mrt models init && mrt checkpoints download ${MRT2_MODEL}

COPY handler.py .
CMD ["python3", "-u", "handler.py"]
