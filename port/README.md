# Magenta RealTime 2 → NVIDIA port kit

Goal: run MRT2 on NVIDIA (RunPod **or** a local 4090), targeting the **native
C++ engine** (Path C), the same engine the macOS `.app` bundles in this folder
are built from.

## Why this is feasible (the short version)

The `.app` bundles you have are **arm64 + Metal/MLX**, not portable. But they're
built from the **open-source** [`magenta/magenta-realtime`](https://github.com/magenta/magenta-realtime)
repo, whose C++ inference library (`core/`) is **already cross-platform**:

- `mlx_engine.cpp` (2,658 lines) uses **only the portable MLX C++ API**, no Metal,
  no Objective-C. MLX now has a **native CUDA backend** (`-DMLX_BUILD_CUDA=ON`).
- The only Apple code in `core/` is an autorelease-pool shim that's already
  `#if defined(__APPLE__)` → a **no-op on Linux**.
- The headless `examples/hello_mrt2` CLI is pure C++ (writes a `.wav`).

The macOS lock is a **build-system guard** (`if(NOT APPLE) FATAL_ERROR`), not a
code limitation. This kit flips that guard plus a handful of related switches.

## What the kit does

`patch_cmake.py` makes these edits to a fresh clone:

| File | Change |
|---|---|
| `CMakeLists.txt` | `project()` drops `OBJCXX` off-Apple; remove macOS `FATAL_ERROR`; MLX `v0.31.1`→`v0.31.2`; `MLX_BUILD_CUDA=ON`; re-enable TFLite XNNPACK; gate Metal-preamble patch + npm UI + Apple GUI subdirs under `if(APPLE)` |
| `core/CMakeLists.txt` | `-framework Metal/Accelerate/Foundation` only on Apple; link `Threads`+`dl` on Linux |

MLX **v0.31.2** is a patch bump from the pinned 0.31.1 (≈no API drift) that adds
the two CUDA ops this model needs: **quantized matmul** (depthformer is exported
`--bits=8`/int4) and **FFT** (SpectroStream codec).

---

## Layer 0: prove the model on your GPU *today* (zero risk, Google-official)

No C++ build. Confirms the weights + your CUDA stack work.

```bash
uv venv --python 3.12 && source .venv/bin/activate
uv pip install "magenta-rt" "jax[cuda13]"     # use cuda12 if your driver is older
mrt models init && mrt models download mrt2_small
mrt jax generate --prompt "disco funk" --duration 4.0 --model=mrt2_small
```

## Layer 1: prove the *MLX graph* runs on CUDA (de-risks Path C)

The C++ engine runs the same MLX computation as the Python MLX backend. Testing
the Python MLX-CUDA path first tells us whether every op has a CUDA kernel,
*before* spending time on the C++ build:

```bash
uv pip install mlx-cuda                        # MLX python wheel w/ CUDA backend
mrt mlx generate --prompt "disco funk" --duration 4.0 --model=mrt2_small
```

If this works, Path C is essentially guaranteed. If a specific op errors, that's
exactly the op we patch or CPU-fallback in Layer 2 (see Risks).

## Layer 2: the native C++ engine on CUDA  ★ the prize

### On RunPod
1. Launch a pod with a **CUDA 12.x *devel*** template (needs `nvcc`), any NVIDIA GPU.
2. Upload this `port/` folder (or `git clone` your fork containing it).
3. Build:
   ```bash
   export CMAKE_CUDA_ARCHITECTURES=90      # H100=90, A100=80, 4090=89, 5090=120
   ./build_cuda.sh                          # clones, patches, builds (slow first time)
   ./run_demo.sh "a jazz piano trio" mrt2_small 100
   ```
   …or just `docker build -t mrt2-cuda -f Dockerfile . && docker run --gpus all -it mrt2-cuda`.

### On a local 4090 (Linux or WSL2)
Same commands with `CMAKE_CUDA_ARCHITECTURES=89`. Local is the better target for
**true real-time** later (no network latency in the audio loop).

### Validate correctness vs. the Mac build
The repo ships its own oracle. Generate the same prompt/seed and diff:
```bash
python scripts/compare_python_n_cpp.py     # compares Python ref vs C++ engine output
```

## Layer 3: the product (interactive, browser-based)

Built and ready in [`server/`](server/): a **backend-agnostic streaming server** +
a dependency-free **browser client**. It wraps the official `magenta_rt`
streaming system (`MagentaRT2Jax.generate(style, frames, state)` → gapless 48 kHz
chunks) and pushes audio to the browser over WebSocket, with live prompt + param
control. Runs on the **JAX backend today** (Layer 0, works on any NVIDIA pod);
the protocol and client are unchanged when you later swap in the native C++ engine.

```bash
# On the GPU box (RunPod / local 4090):
uv pip install "magenta-rt" "jax[cuda13]" websockets numpy
mrt models init                       # MusicCoCa + SpectroStream resources
mrt checkpoints download mrt2_small   # JAX needs the *safetensors* checkpoints
python server/mrt2_server.py --model mrt2_small --host 0.0.0.0 --port 8765
```

Then open [`server/client.html`](server/client.html) in a browser, set the
`ws://` URL (on RunPod use the pod's public address + exposed TCP port), hit
**Connect → Start**, and type prompts live. The client schedules chunks gaplessly
via Web Audio and shows the real-time factor.

- **Lower latency:** `--chunk-frames 10` (~0.4 s) makes control snappier.
- **Local 4090:** same command; localhost has no network latency in the loop.
- **Native engine later:** point the same `generate()`-style loop at `magentart::core`
  (`RealtimeRunner` already has the audio-thread ring buffer + MIDI gate). Only
  `mrt2_server.py`'s `load_model`/`generate` calls change. The client stays as-is.
- **Full original UI:** the React UI is in your bundle
  ([jam_ui/index.html](../MRT2%20Bundle/MRT2%20-%20Jam.app/Contents/Resources/jam_ui/index.html))
  and source (`examples/common/react_ui/`). It speaks a `window.webkit…postMessage`
  bridge; a shim that maps those messages to this WebSocket can drive it unmodified
  once the minimal client proves the pipe.

---

## Risks & fallbacks (honest)

- **MLX-CUDA op coverage**: *the* risk. Layer 1 surfaces it cheaply. If an op is
  missing on CUDA, options: bump MLX to a newer patch, run that op on the MLX CPU
  stream (`mx.cpu`), or add a small CUDA kernel. Quantized-matmul + FFT (the likely
  suspects) are covered as of v0.31.2.
- **`.mlxfn` was exported on a Mac**: it's a backend-agnostic op graph + weights,
  so it should load on CUDA. If it doesn't, re-export portably on the box:
  `mrt checkpoints download` then `mrt mlx export --output-name=mrt2_small --bits=8`
  (the exporter is pure MLX-Python and runs on CPU-MLX anywhere).
- **CUDA toolkit version**: MLX has had build friction on some CUDA minors. The
  Dockerfile pins **CUDA 12.6**; if MLX fails to compile, try a 12.4 or 12.8 devel
  base. Driver must satisfy the toolkit (CUDA 13 wheels want driver ≥ 580).
- **cmake version**: upstream pins `cmake<3.28`; the Dockerfile honors it.

## Files
- `patch_cmake.py`: idempotent, anchor-checked CMake patcher (aborts if upstream drifts)
- `build_cuda.sh`: clone → patch → configure → build `hello_mrt2`
- `run_demo.sh`: download weights → generate a `.wav`, prints an RTF (real-time factor) check
- `Dockerfile`: reproducible RunPod / local CUDA build environment
- `server/mrt2_server.py`: streaming WebSocket server (JAX backend now, C++ engine later)
- `server/client.html`: dependency-free browser client (gapless Web Audio + live controls)
