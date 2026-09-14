from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import requests


def _wait_port(host: str, port: int, timeout_s: int = 25) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except OSError:
            time.sleep(0.3)
    raise RuntimeError(f"服务未启动：{host}:{port}")


def _assert_200(resp: requests.Response, name: str) -> dict:
    if resp.status_code != 200:
        try:
            payload = resp.json()
        except Exception:
            payload = resp.text
        raise RuntimeError(f"{name} status={resp.status_code} payload={payload}")
    try:
        return resp.json()
    except Exception:
        return {"_text": resp.text}


def main() -> int:
    base = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    host = "127.0.0.1"
    port = 8000

    sample_pdf = Path(__file__).resolve().parent / "sample.pdf"
    if not sample_pdf.exists():
        raise RuntimeError(f"缺少样例 PDF：{sample_pdf}")

    env = os.environ.copy()
    env.setdefault("DJANGO_SETTINGS_MODULE", "ph_backend.settings")

    proc = subprocess.Popen(
        [sys.executable, "manage.py", "runserver", f"{host}:{port}", "--noreload"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(Path(__file__).resolve().parent.parent),
        env=env,
        text=True,
    )
    try:
        _wait_port(host, port, timeout_s=30)

        schema = requests.get(f"{base}/api/schema/")
        _assert_200(schema, "openapi_schema")

        with open(sample_pdf, "rb") as f:
            resp = requests.post(f"{base}/api/documents/", files={"file": (sample_pdf.name, f, "application/pdf")})
        doc = _assert_200(resp, "upload_document")
        doc_id = doc["id"]

        docs = _assert_200(requests.get(f"{base}/api/documents/"), "list_documents")
        if not any(d.get("id") == doc_id for d in docs):
            raise RuntimeError("list_documents 未包含新上传文档")

        _assert_200(requests.get(f"{base}/api/documents/{doc_id}/"), "get_document")

        parsed = _assert_200(requests.post(f"{base}/api/documents/{doc_id}/parse/"), "parse_document")
        if int(parsed.get("pages") or 0) <= 0:
            raise RuntimeError(f"parse_document pages 异常：{parsed}")

        _assert_200(requests.post(f"{base}/api/qa/embed/{doc_id}/"), "embed_document")

        ollama = _assert_200(requests.get(f"{base}/api/qa/ollama/status/"), "ollama_status")
        if not ollama.get("ok"):
            raise RuntimeError(f"Ollama 不可用：{ollama}")

        _assert_200(requests.post(f"{base}/api/kg/build/{doc_id}/"), "kg_build")

        kg_search = _assert_200(requests.get(f"{base}/api/kg/search/", params={"q": "糖尿病", "limit": 5}), "kg_search")
        entities = kg_search.get("entities") or []
        if not entities:
            entities = ["糖尿病"]

        _assert_200(requests.get(f"{base}/api/kg/subgraph/", params={"center": entities[0], "limit": 30}), "kg_subgraph")

        payload = {"question": "这份文档主要讲了什么？请列要点。", "document_ids": [doc_id], "top_k": 3}
        qa = _assert_200(
            requests.post(f"{base}/api/qa/ask/", data=json.dumps(payload), headers={"Content-Type": "application/json"}),
            "qa_ask",
        )
        if not qa.get("answer"):
            raise RuntimeError(f"qa_ask answer 为空：{qa}")

        tasks = _assert_200(requests.get(f"{base}/api/monitoring/tasks/"), "tasks_list")
        if not tasks:
            raise RuntimeError("tasks_list 为空，未产生任务记录")

        task_id = tasks[0]["id"]
        _assert_200(requests.get(f"{base}/api/monitoring/tasks/{task_id}/"), "task_detail")

        print("OK: all endpoints returned 200")
        return 0
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=8)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
