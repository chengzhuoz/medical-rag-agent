# Medical RAG Agent

> 基于 Neo4j + Milvus 的公共卫生知识图谱与医疗文档智能问答系统

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.x-092E20?logo=django&logoColor=white)
![Milvus](https://img.shields.io/badge/Milvus-HNSW-00A1EA?logo=milvus&logoColor=white)
![Neo4j](https://img.shields.io/badge/Neo4j-GraphRAG-4581C3?logo=neo4j&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF?logo=githubactions&logoColor=white)

## 项目简介

这是一个面向公共卫生和医疗文档场景的 RAG 问答项目，支持 PDF 文档解析、文本切分、向量化、知识图谱构建以及证据增强问答的完整链路。

项目重点解决医疗长文本中的两个问题：

- **语义检索容易丢失跨段关系**：使用 Milvus 召回语义相关文本片段。
- **实体关系和多跳逻辑难以从文本块恢复**：使用 Neo4j 存储实体、文档和关系，补充图谱证据。

模型负责理解问题、规划检索和组织答案；医疗规则、图谱和向量库负责提供可追溯证据。

## 系统架构

```mermaid
flowchart LR
    U[用户 / Vue3 前端] --> API[Django REST API]
    API --> R[Router Agent\n意图识别]
    R --> P[Retriever Agent\nQuery 规划与工具选择]
    P --> V[Milvus\n语义向量召回]
    P --> G[Neo4j\n实体关系与多跳路径]
    P --> T[规则引擎 / 药典 REST API]
    V --> F[证据融合]
    G --> F
    T --> F
    F --> A[Answer Agent\n结构化回答]
    A --> C[Reviewer Agent\n证据与医疗风险校验]
    C --> U
```

## 双路混合检索

```mermaid
sequenceDiagram
    participant Q as 用户问题
    participant R as Retriever Agent
    participant M as Milvus
    participant N as Neo4j
    participant A as Answer Agent
    Q->>R: 意图识别 / Query 规划
    par 向量检索
        R->>M: Embedding + HNSW 相似度搜索
    and 图谱检索
        R->>N: 实体搜索 + 关系 / 多跳路径
    end
    M-->>A: 文本证据 [1][2]
    N-->>A: 图谱证据 (G)
    A-->>Q: 带引用的结构化答案
```

- **Milvus**：保存文档 chunk 的高维向量，自动创建集合并使用 HNSW 索引。
- **Neo4j**：保存实体、文档关联、共现关系和多跳路径。
- **Retriever Agent**：根据问题意图生成检索计划。
- **Answer Agent**：融合文本证据、图谱证据和规则提示。

## 多智能体编排

| Agent | 职责 |
|---|---|
| Router | 判断事实、法规、多跳、风险等问题类型 |
| Retriever | 生成检索计划，选择向量、图谱和规则工具 |
| Answer | 融合双路证据，生成结构化中文答案 |
| Reviewer | 检查证据支撑、风险提示和不确定性 |

工具层通过统一注册表提供 Function Calling 能力：`search_vectorstore`、`search_graph`、`fetch_subgraph`、`local_rules`、`pharmacopoeia_api`。

独立工具调用使用 `asyncio.gather` 和 `asyncio.to_thread` 并发执行，适配 Neo4j、Milvus、规则引擎等同步 SDK。

## 文档处理链路

```text
PDF 上传 → 文本解析 / OCR → Recursive Chunking
      → Embedding → Milvus 入库
      → 实体抽取 → Neo4j 建图
      → Router / Retriever → 双路召回 → Answer / Reviewer
```

## 技术栈

| 层次 | 技术 |
|---|---|
| 后端 | Django、Django REST Framework、Gunicorn |
| 前端 | Vue3、Vite、Nginx |
| 大模型 | Ollama 本地模型，可配置 Qwen / DeepSeek；支持外部 LLM 网关 |
| 向量检索 | Milvus、HNSW、Sentence Transformers |
| 图谱检索 | Neo4j、Cypher、GraphRAG |
| Agent | Router、Retriever、Answer、Reviewer、Function Calling |
| 基础设施 | Docker Compose、Terraform、AWS ECS Fargate、ALB、ECR |
| 自动化 | GitHub Actions、AWS OIDC、CloudWatch Logs |

## 快速启动：本地 Python

Windows `cmd`：

```cmd
cd /d C:\1\工作\练手\20261\20261
copy .env.example .env
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py check
python manage.py runserver 0.0.0.0:8000
```

接口文档：`http://127.0.0.1:8000/api/docs/`；健康检查：`http://127.0.0.1:8000/healthz/`。

## 快速启动：Docker Compose

确保 Docker Desktop 已启动：

```cmd
docker compose up -d --build
```

该 Compose 环境包含 Django 后端、Vue3 + Nginx 前端、Milvus Standalone、Etcd、MinIO、Neo4j 和 Redis。

访问：

- 前端：`http://localhost/`
- 后端：`http://localhost:8000/healthz/`
- Neo4j Browser：`http://localhost:7474/`
- Milvus：`localhost:19530`

## Milvus 配置

```dotenv
VECTOR_BACKEND=milvus
MILVUS_URI=http://127.0.0.1:19530
MILVUS_COLLECTION=public_health_chunks
MILVUS_HNSW_M=32
MILVUS_HNSW_EF_CONSTRUCTION=200
MILVUS_HNSW_EF=64
MILVUS_FALLBACK_TO_FAISS=1
```

首次调用文档向量化接口时，服务会自动创建集合和 HNSW 索引。重新向量化同一文档时，会先清理旧 chunk，避免重复召回。Milvus 不可用时可切换 `VECTOR_BACKEND=faiss`，或使用 FAISS 降级配置。

## API 主流程

```text
POST /api/documents/                         上传 PDF
POST /api/documents/{id}/parse/              解析并切分
POST /api/qa/embed/{document_id}/            向量化入库
POST /api/kg/build/{document_id}/            构建 Neo4j 图谱
POST /api/qa/ask/                            双路检索问答
GET  /api/qa/ollama/status/                  模型服务状态
```

## CI/CD 与 AWS

```mermaid
flowchart LR
    G[git push main] --> C[GitHub Actions]
    C --> T[Django check / test]
    T --> F[Frontend build]
    F --> I[Docker build]
    I --> E[Push to AWS ECR]
    E --> S[Update ECS Fargate]
    S --> H[ALB /healthz/]
```

`.github/workflows/ci-cd.yml` 在 `main` 分支执行测试、前端构建、Docker 镜像构建、ECR 推送和 ECS 滚动发布。AWS 认证使用 OIDC 临时凭证，不在 GitHub 中保存长期 Access Key。

需要配置：

```text
Secret: AWS_DEPLOY_ROLE_ARN
Variables: AWS_REGION, ECR_REPOSITORY, ECS_CLUSTER, ECS_SERVICE, ECS_TASK_DEFINITION
```

详细 Terraform 配置见 `infra/`，部署说明见 `docs/aws_deployment.md`。

## 重点

- Milvus 负责语义召回，Neo4j 负责实体关系和多跳推理。
- Router / Retriever / Answer / Reviewer 按职责拆分多 Agent 流程。
- Function Calling 根据意图动态选择检索、规则和外部 API 工具。
- 同步 SDK 通过 `asyncio.to_thread` 放入线程池，并用 `asyncio.gather` 并发执行。
- 医疗知识通过 Milvus、Neo4j 和规则引擎保持可更新、可追溯，不直接固化到模型参数。
- 从本地 Docker Compose 迁移到 AWS ECS Fargate，并通过 GitHub Actions 实现持续交付。

项目当前代码提供可运行的工程基线；准确率、吞吐量和端到端延迟等指标需要基于真实测试集和压测结果填写。

## 目录结构

```text
.
├── documents/                PDF 文档、解析与 chunk 模型
├── qa/                       问答服务、Milvus 检索与 Agent 编排
├── kg/                       Neo4j 图谱构建与查询
├── monitoring/               任务状态和日志
├── frontend/                 Vue3 前端
├── Milvus/                   Milvus 使用说明
├── infra/                    AWS Terraform 基础设施
├── scripts/                  本地 Smoke Test 与部署脚本
├── Dockerfile                后端镜像
├── docker-compose.yml        本地完整服务栈
└── .github/workflows/        CI/CD 流水线
```

## License

本项目可用于学习、作品集和技术面试展示。医疗场景输出仅供研究和辅助参考。
