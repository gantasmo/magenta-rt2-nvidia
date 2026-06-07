# Magenta RealTime 2 — streaming WebSocket server (backend-agnostic).
#
# Wraps the official `magenta_rt` streaming system and pushes audio chunks to
# any number of browser clients, accepting live control (prompt / params).
#
# Backend today: JAX (Layer 0 — runs on NVIDIA via `jax[cuda13]`, Google-official).
# The protocol + client are identical for the native C++ engine later (Layer 2),
# so only this file changes when you swap backends.
#
#   pip install "magenta-rt" "jax[cuda13]" websockets numpy
#   # one-time assets:  mrt models init  &&  mrt checkpoints download <model>
#   python mrt2_server.py --model mrt2_small --host 0.0.0.0 --port 8765
#
# Then open client.html (set the ws:// URL). On RunPod, expose the TCP port and
# point the client at the pod's public address.
import argparse
import asyncio
import json
import logging
import struct
import time

import numpy as np
import websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("mrt2_server")

FRAMES_PER_SECOND = 25          # model emits 25 frames/s (40 ms / 1920 samples each)
SAMPLE_RATE = 48000
CHANNELS = 2


class Session:
    """Single shared generation session broadcast to all connected clients."""

    def __init__(self, args):
        self.args = args
        self.clients = set()
        self.mrt = None
        self.embedding = None
        self.state = None                       # JAX streaming state (gapless continuity)
        self.running = False
        self.prompt = args.prompt
        self.pending_prompt = args.prompt       # re-embedded by the loop when it changes
        self.params = dict(
            temperature=args.temperature,
            top_k=args.top_k,
            cfg_musiccoca=args.cfg_musiccoca,
            cfg_notes=args.cfg_notes,
            cfg_drums=args.cfg_drums,
            drums=args.drums,                   # -1 auto / 0 off / 1 on
        )

    # --- model loading (blocking; done once at startup) --------------------
    def load_model(self):
        from magenta_rt import MagentaRT2Jax
        log.info("Loading %s (JAX) + compiling… this takes a bit", self.args.model)
        t0 = time.time()
        self.mrt = MagentaRT2Jax(
            size=self.args.model,
            temperature=self.params["temperature"],
            top_k=self.params["top_k"],
            cfg_musiccoca=self.params["cfg_musiccoca"],
            cfg_notes=self.params["cfg_notes"],
        )
        log.info("Embedding initial prompt: %r", self.prompt)
        self.embedding = self.mrt.embed_style(self.prompt, use_mapper=True)
        log.info("Model ready in %.1fs", time.time() - t0)

    # --- broadcast helpers --------------------------------------------------
    async def broadcast_bytes(self, payload):
        if not self.clients:
            return
        dead = []
        for ws in self.clients:
            try:
                await ws.send(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    async def broadcast_json(self, obj):
        await self.broadcast_bytes(json.dumps(obj))

    # --- the generation loop (one GPU stream, paced to ~real-time) ---------
    async def generation_loop(self):
        chunk_frames = self.args.chunk_frames
        chunk_seconds = chunk_frames / FRAMES_PER_SECOND
        audio_clock = None                      # wall time we are "playing up to"
        while True:
            if not self.running or not self.clients:
                await asyncio.sleep(0.05)
                audio_clock = None
                continue

            # Apply a pending prompt change (re-embed off the hot path).
            if self.pending_prompt != self.prompt:
                self.prompt = self.pending_prompt
                await self.broadcast_json({"type": "status", "state": "embedding",
                                           "msg": f"prompt → {self.prompt!r}"})
                self.embedding = await asyncio.to_thread(
                    self.mrt.embed_style, self.prompt, True)

            t0 = time.time()
            wav, self.state = await asyncio.to_thread(
                self.mrt.generate,
                style=self.embedding,
                frames=chunk_frames,
                state=self.state,
                temperature=self.params["temperature"],
                top_k=self.params["top_k"],
                cfg_musiccoca=self.params["cfg_musiccoca"],
                cfg_notes=self.params["cfg_notes"],
                cfg_drums=self.params["cfg_drums"],
                drums=[int(self.params["drums"])],
            )
            compute_s = time.time() - t0

            # Interleaved float32 stereo -> bytes.  samples: [N, 2] in [-1, 1].
            samples = np.ascontiguousarray(wav.samples, dtype=np.float32)
            await self.broadcast_bytes(b"AUD0" + samples.tobytes())
            rtf = chunk_seconds / compute_s if compute_s > 0 else 0.0
            await self.broadcast_json({"type": "rtf", "value": round(rtf, 2),
                                       "chunk_s": round(chunk_seconds, 3),
                                       "compute_s": round(compute_s, 3)})

            # Pace so we lead playback by at most ~1 chunk (bounds latency when RTF>1).
            now = time.time()
            if audio_clock is None:
                audio_clock = now
            audio_clock += chunk_seconds
            lead = audio_clock - now
            if lead > chunk_seconds:
                await asyncio.sleep(lead - chunk_seconds)

    # --- per-client control channel ----------------------------------------
    async def handle_client(self, ws):
        self.clients.add(ws)
        log.info("client connected (%d total)", len(self.clients))
        await ws.send(json.dumps({
            "type": "hello", "sample_rate": SAMPLE_RATE, "channels": CHANNELS,
            "frame_samples": SAMPLE_RATE // FRAMES_PER_SECOND,
            "model": self.args.model, "prompt": self.prompt,
            "params": self.params, "running": self.running,
        }))
        try:
            async for msg in ws:
                if isinstance(msg, bytes):
                    continue
                try:
                    m = json.loads(msg)
                except Exception:
                    continue
                t = m.get("type")
                if t == "prompt":
                    self.pending_prompt = str(m.get("text", "")).strip() or self.pending_prompt
                elif t == "params":
                    for k in ("temperature", "top_k", "cfg_musiccoca", "cfg_notes", "cfg_drums", "drums"):
                        if k in m and m[k] is not None:
                            self.params[k] = (int(m[k]) if k in ("top_k", "drums") else float(m[k]))
                    await self.broadcast_json({"type": "status", "state": "params",
                                               "params": self.params})
                elif t == "start":
                    self.running = True
                    await self.broadcast_json({"type": "status", "state": "generating"})
                elif t == "stop":
                    self.running = False
                    await self.broadcast_json({"type": "status", "state": "stopped"})
                elif t == "reset":
                    self.state = None            # drop continuity → fresh stream
        finally:
            self.clients.discard(ws)
            log.info("client disconnected (%d left)", len(self.clients))


async def amain(args):
    session = Session(args)
    await asyncio.to_thread(session.load_model)
    asyncio.create_task(session.generation_loop())
    log.info("serving ws://%s:%d  (chunk=%d frames ≈ %.2fs)",
             args.host, args.port, args.chunk_frames, args.chunk_frames / FRAMES_PER_SECOND)
    async with websockets.serve(session.handle_client, args.host, args.port,
                                max_size=None, ping_interval=20):
        await asyncio.Future()


def parse_args():
    p = argparse.ArgumentParser(description="MRT2 streaming WebSocket server")
    p.add_argument("--model", default="mrt2_small", help="mrt2_small | mrt2_base")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--prompt", default="warm analog pads")
    p.add_argument("--chunk-frames", type=int, default=25,
                   help="frames per generated chunk (25 = 1.0s; lower = snappier control)")
    p.add_argument("--temperature", type=float, default=1.3)
    p.add_argument("--top-k", type=int, default=40)
    p.add_argument("--cfg-musiccoca", type=float, default=3.0)
    p.add_argument("--cfg-notes", type=float, default=1.0)
    p.add_argument("--cfg-drums", type=float, default=1.0)
    p.add_argument("--drums", type=int, default=-1, help="-1 auto / 0 off / 1 on")
    return p.parse_args()


if __name__ == "__main__":
    try:
        asyncio.run(amain(parse_args()))
    except KeyboardInterrupt:
        pass
