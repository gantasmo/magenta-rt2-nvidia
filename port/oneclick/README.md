# MRT2 Studio — one-click launcher

Double-click `MRT2-Studio.bat` (or `studio\MRT2-Studio.vbs`). The music engine starts in
WSL2 on your NVIDIA GPU and your browser opens to the Studio. Type a prompt, press
Generate, and a track plays. Tracks are saved to `studio\output\`.

New here? Read [START-HERE.md](START-HERE.md).

## Local generation

`MRT2-Studio.bat` → `studio\MRT2-Studio.vbs` → `studio\studio_server.py` (WSL2) →
`studio\index.html`.

The server loads `mrt2_small` once on the GPU and serves the GUI and a `/generate`
endpoint at `localhost:8777`. Generation runs at roughly 2× real-time. WSL2 setup is in
[../wsl/README.md](../wsl/README.md).

| File | Role |
|---|---|
| `MRT2-Studio.bat` | Windows double-click entry |
| `studio\MRT2-Studio.vbs` | starts the WSL engine and opens the browser |
| `studio\studio_server.py` | loads the model, serves the GUI and `/generate` |
| `studio\index.html` | the GUI: prompt, knobs, player, visualizer, history |
| `studio\output\` | saved tracks |

## Larger model via RunPod

`mrt2_base` (2.4B params) runs on a rented cloud GPU through RunPod, billed per second of
inference. Build and push the worker image once:

```bash
cd serverless && ./build_and_push.sh YOURUSER/mrt2-serverless:small mrt2_small
```

Open the RunPod GUI with `launcher.py`, paste your API key, pick a GPU, and Deploy.

| File | Role |
|---|---|
| `runpod_client.py` | RunPod REST calls (run and deploy) |
| `serverless/` | worker `handler.py`, `Dockerfile`, `build_and_push.sh` |
| `launcher.py` | GUI server with the RunPod tab |
| `ui/` | the RunPod GUI |
| `secrets.example.json` | template; your key goes in `secrets.local.json` |

## Security

The RunPod API key is stored only in `secrets.local.json` (gitignored). Servers bind to
localhost. `.gitignore` excludes secrets, virtual environments, model weights, and audio.
