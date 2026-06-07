# MRT2 Studio

A one-click app for generating music with Magenta RealTime 2 on an NVIDIA GPU.

## Quick start (Windows)

1. Open `port/oneclick/` and double-click `MRT2-Studio.bat`.
2. Your browser opens to the Studio. Type a prompt and press **Generate**.

See [port/oneclick/START-HERE.md](port/oneclick/START-HERE.md) for the walkthrough and
[port/wsl/README.md](port/wsl/README.md) for the one-time WSL2 GPU setup.

## Layout

| Path | Contents |
|---|---|
| `port/oneclick/` | the one-click Studio app and the RunPod cloud path |
| `port/wsl/` | WSL2 GPU setup and generation scripts |
| `port/server/` | streaming server |
| `port/` | CUDA port kit (Dockerfile, build scripts) |

## Requirements

- Windows with WSL2 Ubuntu and an NVIDIA GPU, or a Linux host with an NVIDIA GPU.
- The `mrt2_small` model runs locally. The larger `mrt2_base` model runs on a RunPod
  cloud GPU.

## Packaging

Run `package.ps1` to build a distributable zip into `dist/MRT2-Studio.zip`.
