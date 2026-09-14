# 公共卫生知识图谱与检索问答（后端）

当前仓库提供 Django 后端、Vue3 前端、Neo4j 图谱检索与 Milvus 向量检索。

## 快速开始（Windows）

1) 配置环境变量：

- 复制 `.env.example` 为 `.env`，按需修改 `OLLAMA_MODEL`、`MILVUS_URI` 和 Neo4j 参数

2) 安装依赖：

```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
```

3) 初始化数据库：

```powershell
.\.venv\Scripts\python manage.py makemigrations
.\.venv\Scripts\python manage.py migrate
```

4) 启动服务：

```powershell
.\.venv\Scripts\python manage.py runserver 0.0.0.0:8000
```

5) API 文档：

- Swagger UI：`http://127.0.0.1:8000/api/docs/`
- OpenAPI Schema：`http://127.0.0.1:8000/api/schema/`

## 核心流程

1) 上传 PDF：`POST /api/documents/`
2) 解析与切分：`POST /api/documents/{id}/parse/`
3) 向量化入库：`POST /api/qa/embed/{document_id}/`
4) 提问：`POST /api/qa/ask/`

更多说明见 [backend_api.md](docs/backend_api.md)。Milvus 默认是向量后端，集合首次向量化时自动创建并使用 HNSW；本地开发时可将 `VECTOR_BACKEND=faiss`，或保留 `MILVUS_FALLBACK_TO_FAISS=1` 作为离线兜底。

MAS 中 Router/Retriever 先完成规划，随后工具执行阶段通过 `asyncio.gather` + `asyncio.to_thread` 并发调用独立的 Milvus、Neo4j、规则引擎和外部 API，最后由 Answer/Reviewer 汇总校验。

## Neo4j 与知识图谱

知识图谱基于 Neo4j（bolt）：

- 配置说明： [neo4j_setup.md](docs/neo4j_setup.md)
