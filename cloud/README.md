# Cloud / RunPod launcher

The local Studio (Windows + NVIDIA + WSL2) lives in [`app/`](../app/) and is documented in
the project [README](../README.md). This folder is the **optional cloud path**: a small GUI
that probes your machine and runs Magenta RealTime 2 on a rented RunPod GPU (pay-per-use),
plus a local streaming "jam" server.

Run it: double-click `MRT2-Studio.command` (macOS / Linux) in the main folder, or
`python cloud/launcher.py`. It opens a localhost GUI.

| File | Role |
|---|---|
| `launcher.py` | standard-library GUI server: probes your GPU, runs RunPod, starts the jam server |
| `ui/` | the launcher's browser GUI (audio-reactive, Three.js / VFX-JS) |
| `runpod_client.py` | RunPod REST calls (run an endpoint, or deploy a new one) |
| `serverless/` | the RunPod worker image: `handler.py`, `Dockerfile`, `build_and_push.sh` |
| `server/` | streaming WebSocket "jam" server + a dependency-free browser client |
| `secrets.example.json` | template; your key goes in `secrets.local.json` (gitignored) |

## Larger model (`mrt2_base`) via RunPod

`mrt2_base` (2.4B params) runs on a rented cloud GPU, billed per second of inference. Build
and push the worker image once:

```bash
cd serverless && ./build_and_push.sh YOURUSER/mrt2-serverless:small mrt2_small
```

Then open the launcher, paste your RunPod API key, pick a GPU, and Deploy.

## Security

The RunPod API key is stored only in `secrets.local.json` (gitignored). The launcher binds
to 127.0.0.1. The `.gitignore` here excludes secrets, virtual environments, model weights,
and audio.
