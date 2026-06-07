# RunPod REST/serverless client — standard library only (no `pip install`).
#
# Used by launcher.py to: run a serverless endpoint, and (advanced) create a
# template + endpoint to deploy MRT2 as a pay-per-use serverless worker.
#
# The API key is passed in by the caller (loaded from the gitignored
# secrets.local.json). It is NEVER hard-coded or logged here.
import json
import urllib.request
import urllib.error

RUN_BASE = "https://api.runpod.ai/v2"        # per-endpoint run/stream/status
REST_BASE = "https://rest.runpod.io/v1"      # account-level management (create endpoint/template)


def _request(url, api_key, method="POST", body=None, timeout=120):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode()
            return {"ok": True, "status": r.status, "data": json.loads(raw) if raw else {}}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        return {"ok": False, "status": e.code, "error": detail}
    except Exception as e:                     # network/SSL/timeout
        return {"ok": False, "status": 0, "error": str(e)}


# ----- running an existing serverless endpoint ------------------------------
def run_sync(endpoint_id, api_key, input_dict, timeout=300):
    """POST /v2/{id}/runsync — wait for the worker and return its output."""
    return _request(f"{RUN_BASE}/{endpoint_id}/runsync", api_key,
                    body={"input": input_dict}, timeout=timeout)


def run_async(endpoint_id, api_key, input_dict):
    """POST /v2/{id}/run — returns a job id to poll with status()."""
    return _request(f"{RUN_BASE}/{endpoint_id}/run", api_key, body={"input": input_dict})


def status(endpoint_id, api_key, job_id):
    return _request(f"{RUN_BASE}/{endpoint_id}/status/{job_id}", api_key, method="GET")


def health(endpoint_id, api_key):
    return _request(f"{RUN_BASE}/{endpoint_id}/health", api_key, method="GET", timeout=30)


# ----- deploying a new serverless endpoint (advanced) -----------------------
def create_template(api_key, name, image, container_disk_gb=20, env=None, ports="8000/http"):
    """POST /v1/templates — a reusable image+config a serverless endpoint runs."""
    body = {
        "name": name,
        "imageName": image,
        "containerDiskInGb": container_disk_gb,
        "isServerless": True,
        "env": env or {},
        "ports": ports,
    }
    return _request(f"{REST_BASE}/templates", api_key, body=body)


def create_endpoint(api_key, name, template_id, gpu_type_ids=None,
                    workers_min=0, workers_max=2, idle_timeout=10,
                    flashboot=True, execution_timeout_ms=600000):
    """POST /v1/endpoints — pay-per-use endpoint. workers_min=0 => scale to zero."""
    body = {
        "name": name,
        "templateId": template_id,
        "computeType": "GPU",
        "gpuTypeIds": gpu_type_ids or [],      # [] = let RunPod pick; or e.g. ["NVIDIA GeForce RTX 4090"]
        "gpuCount": 1,
        "workersMin": workers_min,
        "workersMax": workers_max,
        "idleTimeout": idle_timeout,
        "flashboot": flashboot,                # faster cold starts
        "scalerType": "QUEUE_DELAY",
        "scalerValue": 4,
        "executionTimeoutMs": execution_timeout_ms,
    }
    return _request(f"{REST_BASE}/endpoints", api_key, body=body)
