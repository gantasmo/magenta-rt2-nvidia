# MRT2 audio generation in WSL2

Generate audio with Magenta RealTime 2 on an NVIDIA GPU through WSL2 Ubuntu and the
JAX/CUDA backend.

## Environment

- WSL2 Ubuntu, Python 3.12, a uv-managed venv at `~/mrt2/.venv`.
- JAX with the CUDA plugin (`jax.devices()` reports a `CudaDevice`).
- `magenta-rt` 2.0.2.
- Model assets in `~/Documents/Magenta/magenta-rt-v2/` (MusicCoCa + SpectroStream
  resources and `checkpoints/mrt2_small.safetensors`).

## Generate

From Windows PowerShell:

```powershell
wsl -d Ubuntu -- bash "/mnt/<drive>/path/to/port/wsl/generate.sh" "your prompt here" 15 mrt2_small
```

Arguments: `"<prompt>" <duration_seconds> <model>`. The script writes the `.wav` and copies
it to this folder's `output/`. Other parameters are on the CLI directly
(`--temperature`, `--top-k`, `--cfg-musiccoca`, `--cfg-notes`).

## Build it from scratch

Run the scripts in this folder in order:

1. `probe.sh`: checks GPU passthrough, Python, disk, and build tools.
2. `install.sh`: installs `uv`, creates the venv, installs `magenta-rt`, `jax[cuda12]`,
   and `numpy`, then prints `jax.devices()`.
3. `download.sh`: `mrt models init` (MusicCoCa + SpectroStream).
4. `download2.sh`: `mrt checkpoints download mrt2_small.safetensors`.
5. `generate.sh`: runs `mrt jax generate` and copies the output wav to `output/`.

## Notes

- GPU JAX runs on Linux and WSL2. The driver provides `/usr/lib/wsl/lib/libcuda.so` for
  passthrough.
- Pass the full checkpoint filename to the downloader:
  `mrt checkpoints download mrt2_small.safetensors` (the repo path includes the
  `.safetensors` extension).
- Pass `--model mrt2_small` to `mrt jax generate`. For `mrt2_base`, use a cloud GPU
  (see [../README.md](../README.md)).
- `generate.sh` sets `XLA_PYTHON_CLIENT_PREALLOCATE=false` and
  `XLA_PYTHON_CLIENT_ALLOCATOR=platform` to allocate GPU memory on demand.
- The model repo is public, so no `HF_TOKEN` is required.
