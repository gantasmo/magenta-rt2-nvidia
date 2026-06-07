#!/usr/bin/env bash
set +e
PY="$HOME/mrt2/.venv/bin/python"
WAV="$HOME/Documents/Magenta/magenta-rt-v2/outputs/output_audio_jax_mrt2_small.wav"
"$PY" - "$WAV" <<'PY'
import sys, soundfile as sf, numpy as np
p = sys.argv[1]
info = sf.info(p)
data, sr = sf.read(p)
data = np.asarray(data, dtype=np.float32)
peak = float(np.max(np.abs(data))) if data.size else 0.0
rms  = float(np.sqrt(np.mean(data**2))) if data.size else 0.0
dur  = data.shape[0]/sr
print(f"file        : {p}")
print(f"format      : {info.format} / {info.subtype}")
print(f"samplerate  : {sr} Hz")
print(f"channels    : {data.shape[1] if data.ndim>1 else 1}")
print(f"duration    : {dur:.2f} s  ({data.shape[0]} frames)")
print(f"peak amp    : {peak:.4f}   (1.0 = full scale)")
print(f"RMS level   : {rms:.4f}   ({20*np.log10(rms+1e-12):.1f} dBFS)")
print("VERDICT     :", "REAL AUDIO (non-silent)" if rms > 1e-3 else "SILENT / suspect")
PY
