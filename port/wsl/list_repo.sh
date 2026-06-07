#!/usr/bin/env bash
set +e
PY="$HOME/mrt2/.venv/bin/python"

echo "=== HF repo file tree: google/magenta-realtime-2 ==="
"$PY" - <<'PY'
from huggingface_hub import HfApi
api = HfApi()
for repo in ("google/magenta-realtime-2",):
    try:
        files = api.list_repo_files(repo)
        print(f"# {repo}: {len(files)} files")
        for f in sorted(files):
            print("  ", f)
    except Exception as e:
        print(f"# {repo}: ERROR {e}")
PY

echo
echo "=== checkpoint-name constants in models_commands.py ==="
grep -nE "mrt2_small|mrt2_base|checkpoints/|CHECKPOINT|_CKPT|safetensors|repo_id|REPO" \
  "$HOME/mrt2/.venv/lib/python3.12/site-packages/magenta_rt/cli/models_commands.py" 2>/dev/null | head -60
