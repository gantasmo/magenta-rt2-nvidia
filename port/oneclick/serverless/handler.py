# RunPod serverless worker for Magenta RealTime 2.
#
# Loads MRT2 (JAX backend) once on cold start, then answers generate requests.
# Input  (job["input"]):  {prompt, model, duration, temperature, top_k, cfg_musiccoca, cfg_notes}
# Output: {audio_b64 (WAV), sample_rate, frames, compute_s, rtf}
#
# Pairs with the MRT2 Studio GUI: workers_min=0 means you pay only while a
# request is running (the worker scales to zero when idle).
import base64
import io
import os
import time
import wave

import numpy as np
import runpod

from magenta_rt import MagentaRT2Jax

_MODELS = {}


def get_model(size):
    if size not in _MODELS:
        _MODELS[size] = MagentaRT2Jax(size=size)
    return _MODELS[size]


def to_wav_b64(samples, sr):
    """samples: float32 [N, channels] in [-1, 1] -> base64 16-bit PCM WAV."""
    pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(int(samples.shape[1]))
        w.setsampwidth(2)
        w.setframerate(int(sr))
        w.writeframes(pcm.tobytes())
    return base64.b64encode(buf.getvalue()).decode()


def handler(job):
    i = job.get("input", {}) or {}
    size = i.get("model", os.environ.get("MRT2_MODEL", "mrt2_small"))
    duration = float(i.get("duration", 8.0))
    frames = max(1, int(round(duration * 25)))  # 25 frames/s

    mrt = get_model(size)
    emb = mrt.embed_style(i.get("prompt", "warm analog pads"), use_mapper=True)

    t0 = time.time()
    wav, _ = mrt.generate(
        style=emb, frames=frames,
        temperature=float(i.get("temperature", 1.3)),
        top_k=int(i.get("top_k", 40)),
        cfg_musiccoca=float(i.get("cfg_musiccoca", 3.0)),
        cfg_notes=float(i.get("cfg_notes", 1.0)),
        cfg_drums=float(i.get("cfg_drums", 1.0)),
        drums=[int(i.get("drums", -1))],
    )
    dt = time.time() - t0

    samples = np.asarray(wav.samples, dtype="float32")
    return {
        "audio_b64": to_wav_b64(samples, wav.sample_rate),
        "sample_rate": int(wav.sample_rate),
        "frames": frames,
        "compute_s": round(dt, 2),
        "rtf": round((frames / 25.0) / dt, 2) if dt > 0 else None,
    }


runpod.serverless.start({"handler": handler})
