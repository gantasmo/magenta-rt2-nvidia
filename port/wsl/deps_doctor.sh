#!/usr/bin/env bash
# MRT2 dependency doctor.
#
# Goal: run the engine on the NEWEST package versions that actually work, and
# never get stuck on a broken "latest". It can upgrade the stack, then verifies
# a real GPU generation, and only falls back to a known-good floor if the
# upgrade fails that verification. This is "as up to date as possible" without
# ever leaving the user on a stack that cannot make audio.
#
# Used by setup_all.sh (fresh installs) and by the in-app "Check for updates"
# action. The model checkpoint must already be present before verify runs.
#
# Usage:
#   deps_doctor.sh <venv_dir>            # verify current stack; if it fails, restore the floor
#   deps_doctor.sh <venv_dir> --upgrade  # upgrade to latest, verify, fall back to floor on failure
#   deps_doctor.sh <venv_dir> --floor    # install the known-good floor and verify (recovery)
set -uo pipefail

VENV="${1:?usage: deps_doctor.sh <venv_dir> [--upgrade|--floor]}"
ACTION="${2:-verify}"
PY="$VENV/bin/python"
UV="$(command -v uv || echo "$HOME/.local/bin/uv")"
say(){ echo "[doctor] $*"; }

# Known-good floor: the last stack a human verified. Used only as a fallback,
# so a broken upstream release never bricks a fresh install. Bump deliberately.
FLOOR=( "magenta-rt==2.0.2" "jax[cuda12]==0.10.1" "numpy==2.3.5" "soundfile==0.14.0" )
# Latest line: same packages, unpinned, upgraded to the newest compatible build.
LATEST=( "magenta-rt" "jax[cuda12]" "numpy" "soundfile" )

install(){ "$UV" pip install --python "$PY" "$@"; }

verify(){
  # Import the stack and run ONE real GPU generation. Exit 0 only if the audio
  # is finite and non-silent. Requires the model checkpoint to be present.
  "$PY" - <<'PY'
import sys
try:
    import jax, numpy as np, soundfile  # noqa: F401
    from magenta_rt import MagentaRT2Jax
    if not jax.devices():
        print("VERIFY_FAIL: no JAX devices"); sys.exit(1)
    mrt = MagentaRT2Jax(size="mrt2_small")
    emb = mrt.embed_style("dependency doctor check", use_mapper=True)
    wav, _ = mrt.generate(style=emb, frames=25)
    s = np.asarray(wav.samples, dtype="float32")
    ok = s.size > 0 and bool(np.isfinite(s).all()) and float(np.abs(s).max()) > 1e-4
    print("VERIFY_OK" if ok else "VERIFY_FAIL: silent or NaN output")
    sys.exit(0 if ok else 1)
except Exception as e:
    print("VERIFY_FAIL:", type(e).__name__, e); sys.exit(1)
PY
}

record(){
  "$PY" - "$VENV" <<'PY' 2>/dev/null || true
import importlib.metadata as m, json, sys
venv = sys.argv[1]
d = {p: m.version(p) for p in ("magenta-rt", "jax", "numpy", "soundfile")}
open(venv + "/.engine_versions", "w").write(json.dumps(d))
print("[doctor] active stack:", ", ".join(f"{k} {v}" for k, v in d.items()))
PY
}

fallback(){
  say "restoring known-good floor"
  if install "${FLOOR[@]}" && verify; then record; say "floor verified OK"; return 0; fi
  say "FAILED: floor did not verify either"; return 1
}

case "$ACTION" in
  --upgrade)
    say "upgrading to the latest engine stack…"
    if install -U "${LATEST[@]}"; then
      say "verifying latest (loads the model + one GPU generation)…"
      if verify; then record; say "latest verified OK"; exit 0; fi
      say "latest failed verification"
    else
      say "upgrade install failed"
    fi
    fallback; exit $? ;;
  --floor)
    fallback; exit $? ;;
  verify|*)
    say "verifying current stack…"
    if verify; then record; say "current stack verified OK"; exit 0; fi
    fallback; exit $? ;;
esac
