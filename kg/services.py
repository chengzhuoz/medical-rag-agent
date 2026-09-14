from __future__ import annotations

import itertools
import re
from dataclasses import dataclass
from typing import Any

from django.conf import settings

from neo4j import GraphDatabase

from documents.models import Document, DocumentChunk
from monitoring.services import task_create, task_fail, task_info, task_succeed


class KgNotConfiguredError(RuntimeError):
    pass


def _neo4j_settings() -> tuple[str, str, str, str]:
    uri = settings.NEO4J_URI
    user = settings.NEO4J_USER
    password = settings.NEO4J_PASSWORD
    database = settings.NEO4J_DATABASE
    if not uri or not user or not password:
        raise KgNotConfiguredError("Neo4j 未配置，请设置 NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD")
    return uri, user, password, database


def _driver():
    uri, user, password, _ = _neo4j_settings()
    return GraphDatabase.driver(uri, auth=(user, password))


def ensure_schema() -> None:
    uri, user, password, database = _neo4j_settings()
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        
        with driver.session(database=database) as session:
            session.run("CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE")
            session.run("CREATE CONSTRAINT entity_name IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE")
            exists = session.run(
                "SHOW INDEXES YIELD name, type WHERE name=$name RETURN name, type LIMIT 1",
                name="entity_name_ft",
            ).single()
            if not exists:
                created = False
                for stmt in (
                    "CREATE FULLTEXT INDEX entity_name_ft FOR (e:Entity) ON EACH [e.name]",
                    "CALL db.index.fulltext.createNodeIndex('entity_name_ft', ['Entity'], ['name'])",
                ):
                    try:
                        session.run(stmt).consume()
                        created = True
                        break
                    except Exception:
                        continue
                if not created:
                    raise RuntimeError("无法创建 Neo4j FULLTEXT 索引 entity_name_ft（请检查 Neo4j 版本/权限）")
    finally:
        driver.close()


_re_cn_token = re.compile(r"[\u4e00-\u9fff]{2,12}")
_re_en_token = re.compile(r"[A-Za-z][A-Za-z0-9][A-Za-z0-9._/\-]{0,30}")

_stopwords = {
    "本标准",
    "国家标准",
    "中华人民共和国",
    "发布",
    "实施",
    "前言",
    "范围",
    "术语",
    "定义",
    "规范性引用文件",
    "附录",
    "以下",
    "图",
    "表",
    "章",
}


_bad_phrase_re = re.compile(
    r"(本标准|应当|应|可以|不得|规定|适用于|用于|采用|要求|说明|表示|由|提出|负责|负责起草|起草|批准|发布|实施|委托|可能|版本|最新|符合|建设|探讨|保障|改善|都会|方法|一项|的一项|是城市)"
)

_bad_prefixes = ("为", "在", "对", "及", "与", "和", "用", "通过", "使用", "本标准", "所有")


def _clean_entity(raw: str) -> str | None:
    if not raw:
        return None
    s = raw.strip().strip(".,;:()[]{}<>《》“”\"'`，。；：、")
    if not s:
        return None
    if len(s) < 2:
        return None
    if s in _stopwords:
        return None
    if s.isdigit():
        return None
    if _bad_phrase_re.search(s):
        return None
    if s.startswith(_bad_prefixes):
        return None

    is_cn = bool(re.search(r"[\u4e00-\u9fff]", s))
    if is_cn:
        if s.startswith("中华人民共和国"):
            return "中华人民共和国"
        if len(s) > 12:
            s = s[:12]
        if len(s) < 2:
            return None
        if s.endswith(("的", "了", "及", "和", "与", "在", "对", "为")):
            return None
    else:
        s = s.replace(" ", "")
        if len(s) > 18:
            return None
        if s.lower() in {"http", "https", "www"}:
            return None
    return s


def _is_displayable_entity(name: str) -> bool:
    cleaned = _clean_entity(name)
    return bool(cleaned) and cleaned == name


def extract_entities(text: str, limit: int = 20) -> list[str]:
    if not text:
        return []
    tokens = []
    tokens.extend(_re_cn_token.findall(text))
    tokens.extend(_re_en_token.findall(text))
    freq: dict[str, int] = {}
    for t in tokens:
        cleaned = _clean_entity(t)
        if not cleaned:
            continue
        freq[cleaned] = freq.get(cleaned, 0) + 1
    items = sorted(freq.items(), key=lambda kv: (-kv[1], -len(kv[0]), kv[0]))
    return [k for k, _ in items[:limit]]


def build_graph_for_document(document_id: str) -> dict[str, Any]:
    t = task_create(task_type="kg_build", document_id=document_id)
    try:
        ensure_schema()
        doc = Document.objects.get(id=document_id)
        chunks = list(DocumentChunk.objects.filter(document=doc).order_by("chunk_index"))
        uri, user, password, database = _neo4j_settings()
        driver = GraphDatabase.driver(uri, auth=(user, password))
        try:
            with driver.session(database=database) as session:
                session.run(
                    "MERGE (d:Document {id:$id}) "
                    "SET d.name=$name, d.updated_at=timestamp()",
                    id=str(doc.id),
                    name=doc.original_name,
                )

                entity_total = 0
                edge_total = 0
                for ch in chunks:
                    entities = extract_entities(ch.content, limit=18)
                    if not entities:
                        continue
                    entity_total += len(entities)
                    session.run(
                        "MATCH (d:Document {id:$doc_id}) "
                        "UNWIND $entities AS en "
                        "MERGE (e:Entity {name:en}) "
                        "SET e.updated_at=timestamp() "
                        "MERGE (d)-[:MENTIONS]->(e)",
                        doc_id=str(doc.id),
                        entities=entities,
                    )

                    pairs = []
                    uniq = sorted(set(entities))
                    for a, b in itertools.combinations(uniq, 2):
                        pairs.append([a, b])
                    if pairs:
                        edge_total += len(pairs)
                        session.run(
                            "UNWIND $pairs AS p "
                            "WITH p[0] AS a, p[1] AS b "
                            "MERGE (ea:Entity {name:a}) "
                            "MERGE (eb:Entity {name:b}) "
                            "MERGE (ea)-[r:CO_OCCURS]->(eb) "
                            "ON CREATE SET r.weight=1 "
                            "ON MATCH SET r.weight=r.weight+1",
                            pairs=pairs,
                        )

                task_info(t, message=f"kg_entities={entity_total} kg_edges={edge_total} chunks={len(chunks)}")
        finally:
            driver.close()
        task_succeed(t)
        return {"document_id": document_id, "chunks": len(chunks), "entities": entity_total, "edges": edge_total}
    except Exception as e:
        task_fail(t, error=str(e))
        raise


@dataclass(frozen=True)
class Subgraph:
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


def search_entities(q: str, limit: int = 20) -> list[str]:
    ensure_schema()
    uri, user, password, database = _neo4j_settings()
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session(database=database) as session:
            try:
                res = session.run(
                    "CALL db.index.fulltext.queryNodes('entity_name_ft', $q) "
                    "YIELD node, score "
                    "RETURN node.name AS name "
                    "ORDER BY score DESC "
                    "LIMIT $limit",
                    q=q,
                    limit=limit,
                )
                out = []
                for r in res:
                    name = r["name"]
                    if isinstance(name, str) and _is_displayable_entity(name):
                        out.append(name)
                return out
            except Exception:
                res = session.run(
                    "MATCH (e:Entity) "
                    "WHERE toLower(e.name) CONTAINS toLower($q) "
                    "RETURN e.name AS name "
                    "LIMIT $limit",
                    q=q,
                    limit=limit,
                )
                out = []
                for r in res:
                    name = r["name"]
                    if isinstance(name, str) and _is_displayable_entity(name):
                        out.append(name)
                return out
    finally:
        driver.close()


def fetch_subgraph(center: str, limit: int = 60) -> Subgraph:
    ensure_schema()
    uri, user, password, database = _neo4j_settings()
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session(database=database) as session:
            neighbor_rows = session.run(
                "MATCH (c:Entity {name:$name}) "
                "OPTIONAL MATCH (c)-[r:CO_OCCURS]-(n:Entity) "
                "RETURN n.name AS n, r.weight AS w "
                "ORDER BY w DESC "
                "LIMIT $limit",
                name=center,
                limit=min(max(limit, 1), 200),
            )
            if not _is_displayable_entity(center):
                return Subgraph(nodes=[], edges=[])

            nodes: dict[str, dict[str, Any]] = {center: {"id": center, "label": center, "type": "Entity"}}
            edges: list[dict[str, Any]] = []
            neighbors: list[str] = []
            for row in neighbor_rows:
                n = row["n"]
                w = row["w"]
                if not n:
                    continue
                if not isinstance(n, str) or not _is_displayable_entity(n):
                    continue
                if n not in nodes:
                    nodes[n] = {"id": n, "label": n, "type": "Entity"}
                    neighbors.append(n)
                edges.append({"source": center, "target": n, "type": "CO_OCCURS", "weight": int(w or 1)})

            if neighbors:
                pair_rows = session.run(
                    "UNWIND $names AS a "
                    "UNWIND $names AS b "
                    "WITH a, b WHERE a < b "
                    "MATCH (ea:Entity {name:a})-[r:CO_OCCURS]-(eb:Entity {name:b}) "
                    "RETURN a AS a, b AS b, r.weight AS w "
                    "ORDER BY w DESC "
                    "LIMIT $limit",
                    names=[center] + neighbors[: min(len(neighbors), 40)],
                    limit=min(max(limit * 3, 20), 300),
                )
                for row in pair_rows:
                    a = row["a"]
                    b = row["b"]
                    w = row["w"]
                    if not a or not b:
                        continue
                    edges.append({"source": a, "target": b, "type": "CO_OCCURS", "weight": int(w or 1)})

            uniq_edges = {}
            for e in edges:
                a = e["source"]
                b = e["target"]
                key = (a, b) if a <= b else (b, a)
                old = uniq_edges.get(key)
                if old is None or e.get("weight", 1) > old.get("weight", 1):
                    uniq_edges[key] = e
            return Subgraph(nodes=list(nodes.values()), edges=list(uniq_edges.values()))
    finally:
        driver.close()


def graph_context_for_question(question: str, limit_entities: int = 8, per_entity_edges: int = 8) -> dict[str, Any]:
    keywords = extract_entities(question, limit=limit_entities)
    if not keywords:
        return {"keywords": [], "nodes": [], "edges": [], "paths": []}
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    hits: list[str] = []
    for kw in keywords:
        hits.extend(search_entities(kw, limit=2))
    seeds = list(dict.fromkeys(hits))[:limit_entities]
    for name in seeds:
        sg = fetch_subgraph(name, limit=per_entity_edges)
        for n in sg.nodes:
            nodes[n["id"]] = n
        edges.extend(sg.edges)
    paths: list[dict[str, Any]] = []
    try:
        hops = int(getattr(settings, "GRAPH_HOPS", 2))
    except Exception:
        hops = 2
    if hops >= 2 and len(seeds) >= 2:
        paths = fetch_multihop_paths(seeds, hops=hops, limit=24)
        for p in paths:
            for n in p.get("nodes", []):
                nodes.setdefault(n, {"id": n, "label": n, "type": "Entity"})
            for e in p.get("edges", []):
                edges.append(e)
    return {
        "keywords": keywords,
        "nodes": list(nodes.values()),
        "edges": edges[:160],
        "paths": paths,
    }


def fetch_multihop_paths(seeds: list[str], hops: int = 2, limit: int = 24) -> list[dict[str, Any]]:
    """在多个种子实体之间查找 ≤hops 跳的路径，用于 GraphRAG 多跳推理。"""
    seeds = [s for s in seeds if _is_displayable_entity(s)]
    if len(seeds) < 2:
        return []
    hops = max(1, min(int(hops), 3))
    try:
        ensure_schema()
    except Exception:
        return []
    uri, user, password, database = _neo4j_settings()
    driver = GraphDatabase.driver(uri, auth=(user, password))
    out: list[dict[str, Any]] = []
    try:
        with driver.session(database=database) as session:
            cypher = (
                "UNWIND $seeds AS sa "
                "UNWIND $seeds AS sb "
                "WITH sa, sb WHERE sa < sb "
                "MATCH p = shortestPath((a:Entity {name:sa})-[:CO_OCCURS*1.." + str(hops) + "]-(b:Entity {name:sb})) "
                "WITH p, [r IN relationships(p) | coalesce(r.weight,1)] AS ws "
                "RETURN [n IN nodes(p) | n.name] AS ns, "
                "       [r IN relationships(p) | coalesce(r.weight,1)] AS ws, "
                "       length(p) AS L "
                "ORDER BY L ASC, reduce(s=0, x IN ws | s + x) DESC "
                "LIMIT $limit"
            )
            res = session.run(cypher, seeds=seeds, limit=int(limit))
            for row in res:
                ns = [n for n in (row["ns"] or []) if isinstance(n, str) and _is_displayable_entity(n)]
                if len(ns) < 2:
                    continue
                ws = list(row["ws"] or [])
                edges = []
                for i in range(len(ns) - 1):
                    w = int(ws[i]) if i < len(ws) and ws[i] is not None else 1
                    edges.append({"source": ns[i], "target": ns[i + 1], "type": "CO_OCCURS", "weight": w})
                out.append({"nodes": ns, "edges": edges, "length": int(row["L"] or len(edges))})
    except Exception:
        return out
    finally:
        driver.close()
    return out
