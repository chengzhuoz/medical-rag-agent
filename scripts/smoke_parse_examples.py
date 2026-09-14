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


def _print_step(msg: str) -> None:
    print(msg, flush=True)


def _req_with_heartbeat(method: str, url: str, *, name: str, timeout_s: int = 60, heartbeat_s: int = 5, **kwargs) -> dict:
    t0 = time.perf_counter()
    _print_step(f"[->] {name}")
    result: dict | None = None
    error: Exception | None = None

    def _run():
        nonlocal result, error
        try:
            resp = requests.request(method, url, timeout=timeout_s, **kwargs)
            result = _assert_200(resp, name)
        except Exception as e:
            error = e

    import threading

    th = threading.Thread(target=_run, daemon=True)
    th.start()
    last = time.perf_counter()
    while th.is_alive():
        now = time.perf_counter()
        if now - last >= heartbeat_s:
            dt = now - t0
            _print_step(f"[..] {name} running ({dt:.0f}s)")
            last = now
        time.sleep(0.2)

    if error is not None:
        raise error
    dt = time.perf_counter() - t0
    _print_step(f"[OK] {name} ({dt:.2f}s)")
    return result or {}


def _req(method: str, url: str, *, name: str, timeout_s: int = 60, **kwargs) -> dict:
    t0 = time.perf_counter()
    _print_step(f"[->] {name}")
    resp = requests.request(method, url, timeout=timeout_s, **kwargs)
    data = _assert_200(resp, name)
    dt = time.perf_counter() - t0
    _print_step(f"[OK] {name} ({dt:.2f}s)")
    return data


def _upload(base: str, pdf_path: Path, timeout_s: int = 90) -> str:
    with open(pdf_path, "rb") as f:
        doc = _req(
            "POST",
            f"{base}/api/documents/",
            name=f"upload:{pdf_path.name}",
            timeout_s=timeout_s,
            files={"file": (pdf_path.name, f, "application/pdf")},
        )
    return doc["id"]


def main() -> int:
    base = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    host = "127.0.0.1"
    port = 8000

    root = Path(__file__).resolve().parent.parent
    pdfs = [root / "20141103152808754.pdf", root / "2023_PDF.pdf"]
    pdfs = [p for p in pdfs if p.exists()]
    if not pdfs:
        raise RuntimeError("未找到测试 PDF：请放置 20141103152808754.pdf（或 2023_PDF.pdf）到项目根目录。")
    for p in pdfs:
        if not p.exists():
            raise RuntimeError(f"缺少文件：{p}")

    env = os.environ.copy()
    env.setdefault("DJANGO_SETTINGS_MODULE", "ph_backend.settings")

    _print_step("[i] starting django server...")
    proc = subprocess.Popen(
        [sys.executable, "manage.py", "runserver", f"{host}:{port}", "--noreload"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(root),
        env=env,
        text=True,
    )
    try:
        _wait_port(host, port, timeout_s=30)
        _print_step("[i] server is up")

        ollama = _req("GET", f"{base}/api/qa/ollama/status/", name="ollama_status", timeout_s=20)
        if not ollama.get("ok"):
            raise RuntimeError(f"Ollama 不可用：{ollama}")

        for p in pdfs:
            _print_step(f"\n=== {p.name} ===")
            doc_id = _upload(base, p, timeout_s=120)
            parsed = _req_with_heartbeat(
                "POST",
                f"{base}/api/documents/{doc_id}/parse/",
                name=f"parse:{p.name}",
                timeout_s=900,
                heartbeat_s=6,
            )
            if int(parsed.get("chunks") or 0) <= 0:
                detail = _req("GET", f"{base}/api/documents/{doc_id}/", name=f"doc_detail:{p.name}", timeout_s=30)
                raise RuntimeError(f"{p.name} 解析后 chunks=0：{detail.get('error_message')}")

            _req_with_heartbeat("POST", f"{base}/api/qa/embed/{doc_id}/", name=f"embed:{p.name}", timeout_s=1200, heartbeat_s=6)

            payload = {"question": "请概括本文件的主题与关键术语（要点列表）。", "document_ids": [doc_id], "top_k": 3}
            qa = _req_with_heartbeat(
                "POST",
                f"{base}/api/qa/ask/",
                name=f"qa:{p.name}",
                timeout_s=600,
                heartbeat_s=6,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
            ctx = qa.get("contexts") or []
            if len(ctx) <= 0:
                raise RuntimeError(f"{p.name} 问答返回 contexts=0")

            print("OK", p.name, "chunks", parsed.get("chunks"), "contexts", len(ctx))

        print("OK: examples parsed + embedded + qa")
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
