from __future__ import annotations

import os
import sys

import requests


def main() -> int:
    base = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    neo4j_uri = os.getenv("NEO4J_URI", "")
    neo4j_user = os.getenv("NEO4J_USER", "")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "")
    if not neo4j_uri or not neo4j_user or not neo4j_password:
        print("skip: Neo4j not configured (NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD)")
        return 0

    docs = requests.get(f"{base}/api/documents/").json()
    if not docs:
        print("skip: no documents, upload+parse first")
        return 0

    doc_id = docs[0]["id"]
    r = requests.post(f"{base}/api/kg/build/{doc_id}/")
    r.raise_for_status()
    print("kg_build", r.json())

    r = requests.get(f"{base}/api/kg/search/", params={"q": "糖尿病", "limit": 5})
    r.raise_for_status()
    entities = r.json().get("entities") or []
    print("kg_search", entities)
    if entities:
        r = requests.get(f"{base}/api/kg/subgraph/", params={"center": entities[0], "limit": 30})
        r.raise_for_status()
        sg = r.json()
        print("kg_subgraph", len(sg.get("nodes") or []), len(sg.get("edges") or []))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

