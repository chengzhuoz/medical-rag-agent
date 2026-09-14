from __future__ import annotations

import json
import os
from pathlib import Path

import requests


def ensure_server() -> str:
    return os.getenv("API_BASE_URL", "http://127.0.0.1:8000")


def make_sample_pdf(path: Path) -> None:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    with path.open("wb") as f:
        writer.write(f)


def main() -> None:
    base = ensure_server().rstrip("/")
    sample = Path(__file__).resolve().parent / "sample.pdf"
    make_sample_pdf(sample)

    with sample.open("rb") as f:
        resp = requests.post(f"{base}/api/documents/", files={"file": ("sample.pdf", f, "application/pdf")})
    resp.raise_for_status()
    doc = resp.json()
    doc_id = doc["id"]
    print("uploaded", doc_id)

    resp = requests.post(f"{base}/api/documents/{doc_id}/parse/")
    resp.raise_for_status()
    print("parsed", resp.json())

    resp = requests.post(f"{base}/api/qa/embed/{doc_id}/")
    resp.raise_for_status()
    print("embedded", resp.json()["document"]["status"])

    payload = {"question": "这份文档包含什么内容？", "document_ids": [doc_id], "top_k": 3}
    resp = requests.post(f"{base}/api/qa/ask/", data=json.dumps(payload), headers={"Content-Type": "application/json"})
    if resp.status_code == 503:
        print("answer_unavailable", resp.json().get("detail", ""))
    else:
        resp.raise_for_status()
        answer = resp.json()["answer"]
        print("answer", answer[:160].replace("\n", " "))

    resp = requests.get(f"{base}/api/monitoring/tasks/")
    resp.raise_for_status()
    print("tasks", len(resp.json()))


if __name__ == "__main__":
    main()
