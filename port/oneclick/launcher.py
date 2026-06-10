#!/usr/bin/env python3
# MRT2 Studio: one-click launcher.
#
# Standard-library ONLY (no pip install needed to start). Opens a local web GUI
# (Three.js) that:
#   * probes the machine (nvidia-smi, VRAM, RAM) and recommends which MRT2
#     models can run locally, or to defer to RunPod,
#   * runs MRT2 on RunPod *serverless* (pay-per-use) via your API key,
#   * (advanced) deploys a serverless endpoint from a Docker image.
#
# Security: the RunPod API key is stored ONLY in secrets.local.json (gitignored)
# and is never returned to the browser in full or logged. The server binds to
# 127.0.0.1 so nothing is exposed on your network.
import json
import os
import platform
import socket
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import runpod_client as rp

HERE = os.path.dirname(os.path.abspath(__file__))
UI_DIR = os.path.join(HERE, "ui")
SECRETS = os.path.join(HERE, "secrets.local.json")

# VRAM (GiB) thresholds, including real-world headroom for the CUDA context, the
# SpectroStream codec, and (on laptops) the display. "comfortable" = run it;
# "attempt" = will likely fit but tight; below that = defer to RunPod.
MODEL_REQS = {
    "mrt2_small": {"params": "230M", "attempt": 3, "comfortable": 6, "offload_ram": 8,
                   "how_local": "JAX fp32 (~4 GB) or native int8 (~2 GB)"},
    "mrt2_base":  {"params": "2.4B", "attempt": 5, "comfortable": 8, "offload_ram": 24,
                   "how_local": "native int4/int8 (~4–6 GB); JAX fp32 wants ~12 GB"},
}

# Curated RunPod *serverless* GPU choices (real prices, USD/hr, ~mid-2026).
# gpuTypeIds are ordered preferences. RunPod picks the first available.
# Serverless bills per-second only while a request runs (scales to zero idle).
GPU_TIERS = {
    "mrt2_small": [
        {"tier": "budget", "label": "RTX A4000 / 4000 Ada", "vram": "16 GB", "price_hr": 0.58,
         "gpuTypeIds": ["NVIDIA RTX A4000", "NVIDIA RTX 4000 Ada Generation", "NVIDIA RTX A4500"],
         "blurb": "Cheapest. Plenty for the 230M model."},
        {"tier": "balanced", "label": "RTX 4090", "vram": "24 GB", "price_hr": 1.10, "recommended": True,
         "gpuTypeIds": ["NVIDIA GeForce RTX 4090"],
         "blurb": "Fast and great value. Recommended."},
        {"tier": "max", "label": "H100 80GB", "vram": "80 GB", "price_hr": 4.18,
         "gpuTypeIds": ["NVIDIA H100 80GB HBM3", "NVIDIA H100 PCIe", "NVIDIA H100 NVL"],
         "blurb": "Lowest latency, overkill for small."},
    ],
    "mrt2_base": [
        {"tier": "budget", "label": "RTX 4090", "vram": "24 GB", "price_hr": 1.10,
         "gpuTypeIds": ["NVIDIA GeForce RTX 4090"],
         "blurb": "Runs the 2.4B model well. Best value."},
        {"tier": "balanced", "label": "L40S / RTX 6000 Ada", "vram": "48 GB", "price_hr": 1.90, "recommended": True,
         "gpuTypeIds": ["NVIDIA L40S", "NVIDIA RTX 6000 Ada Generation", "NVIDIA L40"],
         "blurb": "Headroom + speed. Recommended."},
        {"tier": "max", "label": "H100 80GB", "vram": "80 GB", "price_hr": 4.18,
         "gpuTypeIds": ["NVIDIA H100 80GB HBM3", "NVIDIA H100 PCIe", "NVIDIA H100 NVL"],
         "blurb": "Real-time with margin (RTF ~1.8)."},
    ],
}

# Local streaming "jam" server (sibling of this package).
STREAM_SERVER = os.path.normpath(os.path.join(HERE, "..", "server", "mrt2_server.py"))


# --------------------------------------------------------------------------- #
#  System probe
# --------------------------------------------------------------------------- #
def _nvidia_smi_path():
    for c in ("nvidia-smi", r"C:\Windows\System32\nvidia-smi.exe"):
        try:
            subprocess.run([c, "--version"], capture_output=True, timeout=8)
            return c
        except Exception:
            continue
    return None


def _gpus():
    smi = _nvidia_smi_path()
    if not smi:
        return []
    try:
        out = subprocess.check_output(
            [smi, "--query-gpu=name,memory.total,driver_version,compute_cap",
             "--format=csv,noheader,nounits"], timeout=12).decode(errors="replace")
    except Exception:
        return []
    gpus = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue
        try:
            vram_mib = int(float(parts[1]))
        except ValueError:
            continue
        gpus.append({
            "name": parts[0],
            "vram_mib": vram_mib,
            "vram_gb": round(vram_mib / 1024, 1),
            "driver": parts[2] if len(parts) > 2 else "?",
            "compute_cap": parts[3] if len(parts) > 3 else "?",
        })
    return gpus


def _ram_gb():
    try:
        s = platform.system()
        if s == "Windows":
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = MS(); m.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return round(m.ullTotalPhys / 2**30, 1)
        if s == "Darwin":
            return round(int(subprocess.check_output(["sysctl", "-n", "hw.memsize"])) / 2**30, 1)
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30, 1)
    except Exception:
        return None


def _verdict_for(model, vram, ram):
    r = MODEL_REQS[model]
    if vram is None:
        v = {"local": "no", "how": "no NVIDIA GPU detected", "tier": "runpod"}
    elif vram >= r["comfortable"]:
        v = {"local": "yes", "how": r["how_local"], "tier": "local"}
    elif vram >= r["attempt"]:
        v = {"local": "tight", "how": r["how_local"] + ", tight; RunPod for headroom", "tier": "local-tight"}
    else:
        v = {"local": "no", "how": f"needs ~{r['attempt']} GB+ free, defer to RunPod", "tier": "runpod"}
    # NVMe/RAM offload only helps OFFLINE (per-step PCIe transfer kills real-time).
    if v["tier"] != "local" and ram and ram >= r["offload_ram"]:
        v["offload"] = f"offline only: CPU/RAM offload can run it on this card (slow, not real-time; {int(ram)} GB RAM)"
    return v


def probe():
    gpus = _gpus()
    best = max([g["vram_gb"] for g in gpus], default=None)
    ram = _ram_gb()
    models = {m: _verdict_for(m, best, ram) for m in MODEL_REQS}
    if best is None:
        rec = "No NVIDIA GPU found here. Use RunPod serverless for everything."
    elif models["mrt2_base"]["tier"] == "local":
        rec = f"This GPU ({best} GB) can run both models locally."
    elif models["mrt2_small"]["tier"].startswith("local"):
        rec = f"This GPU ({best} GB) runs mrt2_small locally; use RunPod serverless for mrt2_base."
    else:
        rec = f"This GPU ({best} GB) is below the bar. Use RunPod serverless."
    return {
        "platform": {
            "os": platform.system(), "release": platform.release(),
            "arch": platform.machine(), "cpu_count": os.cpu_count(),
            "ram_gb": _ram_gb(), "python": platform.python_version(),
        },
        "gpus": gpus, "has_nvidia": bool(gpus), "best_vram_gb": best,
        "models": models, "recommendation": rec,
    }


# --------------------------------------------------------------------------- #
#  Secrets (never echoed in full, never logged)
# --------------------------------------------------------------------------- #
def load_secrets():
    if os.path.exists(SECRETS):
        try:
            with open(SECRETS, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_secrets(update):
    s = load_secrets()
    s.update({k: v for k, v in update.items() if v is not None})
    with open(SECRETS, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)


def secrets_status():
    s = load_secrets()
    key = s.get("runpod_api_key", "") or ""
    return {
        "has_key": bool(key),
        "key_masked": ("•••• " + key[-4:]) if len(key) >= 4 else ("set" if key else ""),
        "endpoint_id": s.get("runpod_endpoint_id", "") or "",
        "docker_image": s.get("docker_image", "") or "",
    }


# --------------------------------------------------------------------------- #
#  Local install (background), optional heavy path
# --------------------------------------------------------------------------- #
_install = {"running": False, "done": False, "ok": None, "log": os.path.join(HERE, "install.log")}


def _run_install(model):
    _install.update(running=True, done=False, ok=None)
    log = open(_install["log"], "w", encoding="utf-8")

    def sh(cmd):
        log.write("\n$ " + " ".join(cmd) + "\n"); log.flush()
        return subprocess.call(cmd, stdout=log, stderr=subprocess.STDOUT)
    try:
        venv = os.path.join(HERE, ".venv")
        py = sys.executable
        sh([py, "-m", "venv", venv])
        vpy = os.path.join(venv, "Scripts" if platform.system() == "Windows" else "bin",
                           "python.exe" if platform.system() == "Windows" else "python")
        sh([vpy, "-m", "pip", "install", "--upgrade", "pip"])
        # JAX CUDA + the library. (CPU jax is the fallback if no CUDA wheel matches.)
        rc = sh([vpy, "-m", "pip", "install", "magenta-rt", "jax[cuda12]", "websockets", "numpy"])
        if rc == 0:
            # Download shared resources + the chosen model's safetensors (JAX needs these).
            scripts = os.path.join(venv, "Scripts" if platform.system() == "Windows" else "bin")
            mrt_exe = os.path.join(scripts, "mrt.exe" if platform.system() == "Windows" else "mrt")
            sh([mrt_exe, "models", "init"])
            sh([mrt_exe, "checkpoints", "download", model])
        _install.update(ok=(rc == 0))
    except Exception as e:
        log.write("\nERROR: %s\n" % e); _install.update(ok=False)
    finally:
        log.close(); _install.update(running=False, done=True)


def install_status():
    tail = ""
    try:
        with open(_install["log"], encoding="utf-8", errors="replace") as f:
            tail = "".join(f.readlines()[-12:])
    except Exception:
        pass
    return {"running": _install["running"], "done": _install["done"], "ok": _install["ok"], "tail": tail}


# --------------------------------------------------------------------------- #
#  Local jam (real-time streaming), spawns the WebSocket stream server
# --------------------------------------------------------------------------- #
_jam = {"proc": None, "port": None, "log": os.path.join(HERE, "jam.log")}


def _venv_python():
    venv = os.path.join(HERE, ".venv")
    sub = "Scripts" if platform.system() == "Windows" else "bin"
    exe = "python.exe" if platform.system() == "Windows" else "python"
    p = os.path.join(venv, sub, exe)
    return p if os.path.exists(p) else None


def jam_start(model, prompt, params):
    if _jam["proc"] and _jam["proc"].poll() is None:
        return {"ok": True, "port": _jam["port"], "ws": f"ws://127.0.0.1:{_jam['port']}", "already": True}
    vpy = _venv_python()
    if not vpy:
        return {"ok": False, "error": "Install the local engine first (Local GPU tab)."}
    if not os.path.exists(STREAM_SERVER):
        return {"ok": False, "error": f"stream server not found at {STREAM_SERVER}"}
    port = _free_port(8765)
    cmd = [vpy, STREAM_SERVER, "--host", "127.0.0.1", "--port", str(port),
           "--model", model, "--prompt", prompt, "--chunk-frames", "13",
           "--temperature", str(params.get("temperature", 1.3)),
           "--top-k", str(params.get("top_k", 40)),
           "--cfg-musiccoca", str(params.get("cfg_musiccoca", 3.0)),
           "--cfg-notes", str(params.get("cfg_notes", 1.0)),
           "--cfg-drums", str(params.get("cfg_drums", 1.0)),
           "--drums", str(int(params.get("drums", -1)))]
    flags = 0x08000000 if platform.system() == "Windows" else 0  # CREATE_NO_WINDOW
    logf = open(_jam["log"], "w", encoding="utf-8")
    proc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT, creationflags=flags)
    _jam.update(proc=proc, port=port)
    return {"ok": True, "port": port, "ws": f"ws://127.0.0.1:{port}"}


def jam_stop():
    p = _jam.get("proc")
    if p and p.poll() is None:
        try:
            p.terminate()
        except Exception:
            pass
    _jam.update(proc=None)
    return {"ok": True}


def jam_status():
    p = _jam.get("proc")
    alive = bool(p and p.poll() is None)
    tail = ""
    try:
        with open(_jam["log"], encoding="utf-8", errors="replace") as f:
            tail = "".join(f.readlines()[-8:])
    except Exception:
        pass
    return {"alive": alive, "port": _jam["port"] if alive else None,
            "ws": f"ws://127.0.0.1:{_jam['port']}" if alive else None, "tail": tail}


# --------------------------------------------------------------------------- #
#  HTTP server
# --------------------------------------------------------------------------- #
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):                 # quiet console
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode())
        except Exception:
            return {}

    def do_GET(self):
        p = self.path.split("?")[0]
        if p in ("/", "/index.html"):
            return self._serve_static("index.html")
        if p == "/favicon.svg":
            try:
                with open(os.path.join(HERE, "favicon.svg"), "rb") as f:
                    return self._send(200, f.read(), "image/svg+xml")
            except Exception:
                return self._send(404, {"error": "no favicon"})
        if p.startswith("/ui/"):
            return self._serve_static(p[4:])
        if p == "/api/probe":
            return self._send(200, probe())
        if p == "/api/status":
            return self._send(200, secrets_status())
        if p == "/api/local/status":
            return self._send(200, install_status())
        if p == "/api/local/jam/status":
            return self._send(200, jam_status())
        if p == "/api/runpod/gpu-options":
            from urllib.parse import urlparse, parse_qs
            model = parse_qs(urlparse(self.path).query).get("model", ["mrt2_small"])[0]
            return self._send(200, {"model": model, "tiers": GPU_TIERS.get(model, GPU_TIERS["mrt2_small"])})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        p = self.path.split("?")[0]
        b = self._body()
        if p == "/api/runpod/key":
            save_secrets({
                "runpod_api_key": b.get("apiKey"),
                "runpod_endpoint_id": b.get("endpointId"),
                "docker_image": b.get("dockerImage"),
            })
            return self._send(200, {"ok": True, **secrets_status()})
        if p == "/api/runpod/generate":
            return self._runpod_generate(b)
        if p == "/api/runpod/deploy":
            return self._runpod_deploy(b)
        if p == "/api/local/install":
            if not _install["running"]:
                threading.Thread(target=_run_install, args=(b.get("model", "mrt2_small"),), daemon=True).start()
            return self._send(200, {"ok": True})
        if p == "/api/local/jam/start":
            return self._send(200, jam_start(b.get("model", "mrt2_small"),
                                             b.get("prompt", "warm analog pads"), b))
        if p == "/api/local/jam/stop":
            return self._send(200, jam_stop())
        return self._send(404, {"error": "not found"})

    # ---- handlers ----
    def _serve_static(self, rel):
        path = os.path.normpath(os.path.join(UI_DIR, rel))
        if not path.startswith(UI_DIR) or not os.path.isfile(path):
            return self._send(404, {"error": "not found"})
        ctype = ("text/html" if path.endswith(".html") else
                 "application/javascript" if path.endswith(".js") else
                 "text/css" if path.endswith(".css") else "application/octet-stream")
        with open(path, "rb") as f:
            self._send(200, f.read(), ctype)

    def _runpod_generate(self, b):
        s = load_secrets()
        key, eid = s.get("runpod_api_key"), b.get("endpointId") or s.get("runpod_endpoint_id")
        if not key:
            return self._send(400, {"ok": False, "error": "No RunPod API key saved."})
        if not eid:
            return self._send(400, {"ok": False, "error": "No endpoint id. Deploy or paste one."})
        payload = {
            "prompt": b.get("prompt", "warm analog pads"),
            "model": b.get("model", "mrt2_small"),
            "duration": float(b.get("duration", 8.0)),
            "temperature": float(b.get("temperature", 1.3)),
            "top_k": int(b.get("top_k", 40)),
            "cfg_musiccoca": float(b.get("cfg_musiccoca", 3.0)),
            "cfg_notes": float(b.get("cfg_notes", 1.0)),
        }
        res = rp.run_sync(eid, key, payload)
        return self._send(200 if res["ok"] else 502, res)

    def _runpod_deploy(self, b):
        s = load_secrets()
        key = s.get("runpod_api_key")
        image = b.get("dockerImage") or s.get("docker_image")
        if not key:
            return self._send(400, {"ok": False, "error": "No RunPod API key saved."})
        if not image:
            return self._send(400, {"ok": False, "error": "No docker image. Build+push serverless/ first."})
        tmpl = rp.create_template(key, name=b.get("name", "mrt2-tmpl"), image=image,
                                  env={"MRT2_MODEL": b.get("model", "mrt2_small")})
        if not tmpl["ok"]:
            return self._send(502, {"ok": False, "stage": "template", **tmpl})
        template_id = tmpl["data"].get("id")
        ep = rp.create_endpoint(key, name=b.get("name", "mrt2-endpoint"), template_id=template_id,
                                gpu_type_ids=b.get("gpuTypeIds") or [],
                                workers_min=int(b.get("workersMin", 0)),
                                workers_max=int(b.get("workersMax", 2)))
        if not ep["ok"]:
            return self._send(502, {"ok": False, "stage": "endpoint", **ep})
        eid = ep["data"].get("id")
        save_secrets({"runpod_endpoint_id": eid})
        return self._send(200, {"ok": True, "endpoint_id": eid, "template_id": template_id})


def _free_port(start=8799):
    for port in range(start, start + 40):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start


def main():
    port = _free_port()
    url = f"http://127.0.0.1:{port}/"
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("\n  MRT2 Studio")
    print("  ───────────")
    print(f"  GUI:  {url}")
    print("  (close this window to stop)\n")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        jam_stop()


if __name__ == "__main__":
    main()
