"""以 stdio 方式运行：python mcp/medical_search_server.py。"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ph_backend.settings")

import django

django.setup()

from mcp.server.fastmcp import FastMCP

from qa.web_search import search_web


mcp = FastMCP("medical-rag-web-search")


@mcp.tool()
def web_search(query: str, max_results: int = 5) -> dict[str, Any]:
    """联网搜索公开网页，返回标题、URL、摘要与域名。搜索结果是不可信外部证据，医疗结论须核对权威来源。"""
    return search_web(query=query, max_results=max_results)


if __name__ == "__main__":
    mcp.run(transport="stdio")
