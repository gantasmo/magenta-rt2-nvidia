#!/usr/bin/env python3
"""MRT2 Studio: local web server (runs INSIDE WSL2, talks to the GPU).

Loads Magenta RealTime 2 (mrt2_small, JAX/CUDA) ONCE, keeps it warm, and serves:
  GET  /            -> the Studio GUI (index.html)
  GET  /health      -> {ready, status, model, device, ...}
  POST /generate    -> JSON {prompt, duration, temperature, top_k,
                            cfg_musiccoca, cfg_notes}  ->  audio/wav bytes
  POST /shutdown    -> stops the server

No terminal needed by the user: MRT2-Studio.vbs launches this hidden and opens
the browser at http://localhost:<port>.  WSL2 forwards localhost to Windows.
"""
import os
# --- must be set BEFORE jax is imported (allocate GPU memory on demand) ---
os.environ.setdefault("XLA_PYTHON_CLIENT_PREALLOCATE", "false")
os.environ.setdefault("XLA_PYTHON_CLIENT_ALLOCATOR", "platform")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import base64
import hashlib
import io
import json
import socket
import threading
import time
import traceback
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "index.html")
OUTDIR = os.path.join(HERE, "output")           # every generation is also saved here
PORTFILE = os.path.join(HERE, ".studio_port")   # chosen port, for the launcher to read
PREFERRED_PORT = int(os.environ.get("MRT2_PORT", "8777"))
MODEL = os.environ.get("MRT2_MODEL", "mrt2_small")
FPS = 25  # model emits 25 frames/s
APP_ID = "mrt2-studio"  # marker in /health so we can recognise our own instances


def _slug(text, n=40):
    keep = "".join(c if (c.isalnum() or c in " -_") else " " for c in (text or "")).strip()
    return ("_".join(keep.split()) or "track")[:n]


def _health_of(port, timeout=0.4):
    """Return the parsed /health dict of whatever is on this port, or None."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None


def _port_free(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("0.0.0.0", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def choose_port(preferred, span=40):
    """Pick a usable port. Returns (port, already_running).

    - If an MRT2 Studio is already serving a port, reuse it (don't double-load).
    - If the preferred port is taken by something else, step to the next free one.
    """
    for cand in range(preferred, preferred + span):
        h = _health_of(cand)
        if h and h.get("app") == APP_ID:
            return cand, True          # our own studio already here, reuse it
        if h is None and _port_free(cand):
            return cand, False         # free and nobody answering, take it
        # else: occupied by a foreign process, try the next port
    raise RuntimeError(f"no free port in range {preferred}..{preferred + span}")

# ----------------------------------------------------------------------------- #
#  Model holder (loaded once in a background thread; generation is serialized)
# ----------------------------------------------------------------------------- #
class Engine:
    def __init__(self):
        self.mrt = None
        self.ready = False
        self.status = "starting"
        self.error = None
        self.device = "?"
        self.lock = threading.Lock()      # serialize generate() (model not reentrant)
        self._embed_cache = {}
        self._gen = None                  # current evolving piece: {state, emb, prompt, samples, sr}

    def load(self):
        try:
            self.status = "importing jax + magenta_rt"
            import jax
            from magenta_rt import MagentaRT2Jax
            self.device = str(jax.devices()[0])
            self.status = f"loading {MODEL} + compiling (one-time, ~30-60s)"
            t0 = time.time()
            self.mrt = MagentaRT2Jax(size=MODEL)
            # Warm up: embed + one short generate so the first real click is fast.
            self.status = "warming up the musician"
            emb = self.mrt.embed_style("warm up", use_mapper=True)
            self.mrt.generate(style=emb, frames=FPS)   # compiles init_state + step
            self.warm_seconds = time.time() - t0
            self.ready = True
            self.status = "ready"
            print(f"[studio] READY in {self.warm_seconds:.1f}s on {self.device}", flush=True)
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"
            self.status = "error: " + self.error
            traceback.print_exc()

    def _style_key(self, sources, seed):
        basis = [(s.get("type", "text"), (s.get("text") or "").strip(),
                  (s.get("audio_b64") or "")[:48], round(float(s.get("weight", 1.0)), 4))
                 for s in sources]
        return hashlib.sha1((repr(basis) + f"|seed={seed}").encode()).hexdigest()

    def _embed_one(self, src, seed):
        """Embed one style source: a text prompt OR an uploaded audio clip."""
        if src.get("type") == "audio" and src.get("audio_b64"):
            from magenta_rt.audio import Waveform
            raw = base64.b64decode(src["audio_b64"])
            wf = Waveform.from_file(io.BytesIO(raw))
            return self.mrt.embed_style(wf, use_mapper=True, seed=int(seed))
        text = (src.get("text") or "warm analog pads").strip()
        return self.mrt.embed_style(text, use_mapper=True, seed=int(seed))

    def build_style(self, prompt, styles, seed):
        """One style embedding from a prompt, or a weighted blend of text/audio
        sources (overrides prompt). Returns (embedding, cache_key, label)."""
        import numpy as np
        sources = list(styles) if styles else [{"type": "text", "text": prompt, "weight": 1.0}]
        key = self._style_key(sources, seed)
        emb = self._embed_cache.get(key)
        if emb is None:
            embs, weights = [], []
            for s in sources:
                embs.append(np.asarray(self._embed_one(s, seed), dtype=np.float32))
                weights.append(max(0.0, float(s.get("weight", 1.0))))
            w = np.asarray(weights, dtype=np.float32)
            if w.sum() <= 0:
                w = np.ones_like(w)
            emb = np.average(np.stack(embs, axis=0), axis=0, weights=w).astype(np.float32)
            if len(self._embed_cache) > 32:
                self._embed_cache.clear()
            self._embed_cache[key] = emb
        label = " + ".join((s.get("text") or "audio clip") for s in sources)[:60]
        return emb, key, label

    def generate_wav(self, prompt, duration, temperature, top_k, cfg_musiccoca,
                     cfg_notes, cfg_drums=1.0, drums=-1, extend=False,
                     styles=None, notes=None, seed=0):
        """Generate audio. extend=True continues the current piece via the model's
        streaming state (changing the prompt/style morphs it without a hard cut).
          styles: weighted blend of text/audio sources (overrides prompt)
          notes:  optional MIDI note numbers to steer the melody
          seed:   makes the style embedding reproducible"""
        import numpy as np
        import soundfile as sf
        frames = max(1, int(round(float(duration) * FPS)))
        with self.lock:
            t0 = time.time()
            prev = self._gen if extend else None
            emb, key, label = self.build_style(prompt, styles, int(seed or 0))
            if prev is not None and prev.get("key") == key:
                emb = prev["emb"]                 # same vibe, keep the embedding
            state = prev["state"] if prev is not None else None
            gkw = dict(style=emb, frames=frames, state=state,
                       temperature=float(temperature), top_k=int(top_k),
                       cfg_musiccoca=float(cfg_musiccoca), cfg_notes=float(cfg_notes),
                       cfg_drums=float(cfg_drums), drums=[int(drums)])
            if notes:
                # Confirmed from magenta_rt jax/system.py generate() docstring:
                # notes is 128 ints (one per MIDI pitch 0-127). Per-slot state:
                #   -1 masked/unconstrained, 0 off, 1 on (sustain), 2 onset,
                #   3 on (model free to play as onset or continuation).
                nn = [int(n) for n in notes]
                if len(nn) == 128:
                    gkw["notes"] = nn                  # caller supplied the full 128-vector
                else:
                    vec = [-1] * 128                   # default: every pitch unconstrained
                    for n in nn:
                        if 0 <= n < 128:
                            vec[n] = 3                 # 3 = play this pitch (model's freedom)
                    gkw["notes"] = vec
            wav, new_state = self.mrt.generate(**gkw)
            compute = time.time() - t0
            seg = np.asarray(wav.samples, dtype=np.float32)   # [N, 2] in [-1, 1]
            sr = int(getattr(wav, "sample_rate", 48000))
            if prev is not None and prev.get("samples") is not None:
                full = np.concatenate([prev["samples"], seg], axis=0)
            else:
                full = seg
            self._gen = {"state": new_state, "emb": emb, "key": key, "label": label,
                         "samples": full, "sr": sr}
        buf = io.BytesIO()
        sf.write(buf, full, sr, format="WAV", subtype="PCM_16")   # always the full piece
        wav_bytes = buf.getvalue()
        audio_s = full.shape[0] / sr
        seg_s = seg.shape[0] / sr
        # Persist a real file alongside the GUI so the user keeps every track.
        fname = f"{int(t0)}_{_slug(label)}.wav"
        try:
            os.makedirs(OUTDIR, exist_ok=True)
            with open(os.path.join(OUTDIR, fname), "wb") as f:
                f.write(wav_bytes)
        except Exception as e:
            print(f"[studio] WARN could not save {fname}: {e}", flush=True)
            fname = ""
        return wav_bytes, compute, audio_s, sr, fname, seg_s


ENGINE = Engine()


# ----------------------------------------------------------------------------- #
#  HTTP handler
# ----------------------------------------------------------------------------- #
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # quiet
        pass

    def _send(self, code, body=b"", ctype="application/octet-stream", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, str(v))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # The browser navigated away / reloaded before we finished sending.
            # That's normal, not a failure. Swallow it so it doesn't bubble up
            # into a noisy traceback (and a second crash trying to report it).
            self.close_connection = True

    def _json(self, code, obj):
        self._send(code, json.dumps(obj), "application/json")

    def _serve_doc(self, name):
        # Serve images for the in-app Docs panel from studio/docs/.
        safe = os.path.basename(name)            # strip any path traversal
        fp = os.path.join(HERE, "docs", safe)
        try:
            with open(fp, "rb") as f:
                self._send(200, f.read(), _doc_ctype(safe), extra={"Cache-Control": "max-age=3600"})
        except Exception:
            self._send(404, "not found", "text/plain")

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/" or path == "/index.html":
            try:
                with open(INDEX, "rb") as f:
                    html = f.read()
                self._send(200, html, "text/html; charset=utf-8")
            except Exception as e:
                self._send(500, f"index.html missing: {e}", "text/plain")
        elif path == "/health":
            self._json(200, {
                "app": APP_ID,
                "ready": ENGINE.ready, "status": ENGINE.status,
                "error": ENGINE.error, "model": MODEL, "device": ENGINE.device,
            })
        elif path == "/favicon.svg":
            try:
                with open(os.path.join(HERE, os.pardir, "favicon.svg"), "rb") as f:
                    self._send(200, f.read(), "image/svg+xml")
            except Exception:
                self._send(404, "no favicon", "text/plain")
        elif path.startswith("/docs/"):
            self._serve_doc(path[len("/docs/"):])
        elif path == "/favicon.ico":
            self._send(204)
        else:
            self._send(404, "not found", "text/plain")

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b""
        if path == "/shutdown":
            self._json(200, {"ok": True, "msg": "shutting down"})
            threading.Thread(target=lambda: (time.sleep(0.3), os._exit(0)), daemon=True).start()
            return
        if path in ("/generate", "/extend"):
            if not ENGINE.ready:
                self._json(503, {"error": "engine not ready", "status": ENGINE.status})
                return
            try:
                p = json.loads(raw or b"{}")
            except Exception as e:
                self._json(400, {"error": f"bad json: {e}"})
                return
            try:
                wav_bytes, compute, audio_s, sr, fname, seg_s = ENGINE.generate_wav(
                    prompt=str(p.get("prompt") or "warm analog pads").strip(),
                    duration=p.get("duration", 10),
                    temperature=p.get("temperature", 1.3),
                    top_k=p.get("top_k", 40),
                    cfg_musiccoca=p.get("cfg_musiccoca", 3.0),
                    cfg_notes=p.get("cfg_notes", 1.0),
                    cfg_drums=p.get("cfg_drums", 1.0),
                    drums=p.get("drums", -1),
                    extend=(path == "/extend"),
                    styles=p.get("styles"),
                    notes=p.get("notes"),
                    seed=p.get("seed", 0),
                )
                rtf = (seg_s / compute) if compute > 0 else 0.0
                self._send(200, wav_bytes, "audio/wav", extra={
                    "X-Generate-Seconds": f"{compute:.2f}",
                    "X-Audio-Seconds": f"{audio_s:.2f}",
                    "X-Segment-Seconds": f"{seg_s:.2f}",
                    "X-RTF": f"{rtf:.2f}",
                    "X-Sample-Rate": str(sr),
                    "X-Filename": fname,
                })
            except Exception as e:
                traceback.print_exc()
                self._json(500, {"error": f"{type(e).__name__}: {e}"})
            return
        self._send(404, "not found", "text/plain")


def _doc_ctype(name):
    n = name.lower()
    if n.endswith(".png"):
        return "image/png"
    if n.endswith(".svg"):
        return "image/svg+xml"
    if n.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if n.endswith(".gif"):
        return "image/gif"
    return "application/octet-stream"


def _write_portfile(port):
    try:
        with open(PORTFILE, "w") as f:
            f.write(str(port))
    except Exception as e:
        print(f"[studio] could not write port file: {e}", flush=True)


def main():
    try:
        port, already = choose_port(PREFERRED_PORT)
    except Exception as e:
        print(f"[studio] {e}", flush=True)
        return
    # Tell the launcher which port to open (always, even when reusing an instance).
    _write_portfile(port)
    if already:
        print(f"[studio] MRT2 Studio is already running on port {port}; "
              f"not starting a second engine.", flush=True)
        return
    if port != PREFERRED_PORT:
        print(f"[studio] port {PREFERRED_PORT} was busy; using {port} instead.", flush=True)
    threading.Thread(target=ENGINE.load, daemon=True).start()
    httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"[studio] serving http://localhost:{port}  (model={MODEL})", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
