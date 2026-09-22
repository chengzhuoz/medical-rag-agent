from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

BASE_DIR = Path(__file__).resolve().parent.parent

if load_dotenv is not None:
    load_dotenv(BASE_DIR / ".env")


def _env_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
DEBUG = _env_bool("DEBUG", True)

ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    "documents",
    "monitoring",
    "qa",
    "kg",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "monitoring.middleware.PrometheusMetricsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "ph_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]
WSGI_APPLICATION = "ph_backend.wsgi.application"

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if DATABASE_URL:
    _database_url = urlparse(DATABASE_URL)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": (_database_url.path or "").lstrip("/"),
            "USER": _database_url.username or "",
            "PASSWORD": _database_url.password or "",
            "HOST": _database_url.hostname or "",
            "PORT": str(_database_url.port or 5432),
            "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
            "OPTIONS": {"sslmode": os.getenv("DB_SSLMODE", "require")},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": Path(os.getenv("SQLITE_PATH", str(BASE_DIR / "db.sqlite3"))),
        }
    }

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "data" / "uploads"

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = _env_bool("SECURE_SSL_REDIRECT", False)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "公共卫生知识图谱与检索问答 API",
    "DESCRIPTION": "文档上传、解析、向量检索与问答、任务日志。",
    "VERSION": "0.1.0",
    "ENUM_NAME_OVERRIDES": {
        "StatusBcdEnum": ("uploaded", "parsed", "embedded", "failed"),
        "TaskStatusEnum": ("running", "succeeded", "failed"),
    },
}

CORS_ALLOWED_ORIGINS = [o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]
if DEBUG:
    _dev_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]
    for _o in _dev_origins:
        if _o not in CORS_ALLOWED_ORIGINS:
            CORS_ALLOWED_ORIGINS.append(_o)
CORS_ALLOW_ALL_ORIGINS = _env_bool("CORS_ALLOW_ALL_ORIGINS", False)
CORS_ALLOW_CREDENTIALS = True

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-r1:8b")

# 多智能体（MAS）模型角色配置
# 思路：
#   - Qwen 8B 适合做轻量 Router/Retriever（意图识别、检索规划、实体抽取）
#   - DeepSeek 适合做 Reviewer/Answer（推理、校验、总结）
# 任一项为空时回退到 OLLAMA_MODEL
OLLAMA_ROUTER_MODEL = os.getenv("OLLAMA_ROUTER_MODEL", "qwen3:8b") or OLLAMA_MODEL
OLLAMA_RETRIEVER_MODEL = os.getenv("OLLAMA_RETRIEVER_MODEL", "qwen3:8b") or OLLAMA_MODEL
OLLAMA_REVIEWER_MODEL = os.getenv("OLLAMA_REVIEWER_MODEL", "deepseek-r1:8b") or OLLAMA_MODEL
OLLAMA_ANSWER_MODEL = os.getenv("OLLAMA_ANSWER_MODEL", "deepseek-r1:8b") or OLLAMA_MODEL

# 是否启用多智能体编排（关闭时退化为旧的单步 RAG）
MAS_ENABLED = _env_bool("MAS_ENABLED", True)
# Agent 工具执行治理：单请求最大工具数、线程池并发度和单工具超时（秒）
MAS_MAX_TOOL_CALLS = int(os.getenv("MAS_MAX_TOOL_CALLS", "4"))
MAS_TOOL_MAX_CONCURRENCY = int(os.getenv("MAS_TOOL_MAX_CONCURRENCY", "4"))
MAS_TOOL_TIMEOUT_SECONDS = float(os.getenv("MAS_TOOL_TIMEOUT_SECONDS", "12"))
WEB_SEARCH_ENABLED = _env_bool("WEB_SEARCH_ENABLED", True)
WEB_SEARCH_TIMEOUT_SECONDS = float(os.getenv("WEB_SEARCH_TIMEOUT_SECONDS", "8"))
# LangSmith：默认关闭；设置 API Key 后可追踪 Router、Retriever、Answer、Reviewer 和工具调用。
LANGSMITH_TRACING = _env_bool("LANGSMITH_TRACING", False)
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")
LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "medical-rag-agent")
LANGSMITH_DASHBOARD_URL = os.getenv("LANGSMITH_DASHBOARD_URL", "")
# 前端监控页使用这些公开地址；容器环境中通常指向宿主机端口。
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")

# LangChain/LangSmith SDK 读取环境变量；将 Django 配置归一化后同步给 SDK。
if LANGSMITH_TRACING and LANGSMITH_API_KEY:
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = LANGSMITH_API_KEY
    os.environ["LANGSMITH_ENDPOINT"] = LANGSMITH_ENDPOINT
    os.environ["LANGSMITH_PROJECT"] = LANGSMITH_PROJECT
# Cross-Encoder 重排序：Milvus/FAISS 先粗召回，模型再精排最终证据。
RERANKER_ENABLED = _env_bool("RERANKER_ENABLED", True)
RERANKER_MODEL_NAME = os.getenv("RERANKER_MODEL_NAME", "BAAI/bge-reranker-v2-m3")
RERANKER_CANDIDATE_K = int(os.getenv("RERANKER_CANDIDATE_K", "20"))
RERANKER_CANDIDATE_MULTIPLIER = int(os.getenv("RERANKER_CANDIDATE_MULTIPLIER", "5"))
RERANKER_BATCH_SIZE = int(os.getenv("RERANKER_BATCH_SIZE", "8"))
RERANKER_MAX_LENGTH = int(os.getenv("RERANKER_MAX_LENGTH", "512"))
# 会话记忆：短期窗口超过限制时压缩为摘要，长期记忆按前端 memory_scope_id 隔离。
MEMORY_ENABLED = _env_bool("MEMORY_ENABLED", True)
MEMORY_SHORT_TERM_MESSAGE_LIMIT = int(os.getenv("MEMORY_SHORT_TERM_MESSAGE_LIMIT", "8"))
MEMORY_SUMMARY_MAX_CHARS = int(os.getenv("MEMORY_SUMMARY_MAX_CHARS", "1200"))
MEMORY_CONTEXT_MAX_CHARS = int(os.getenv("MEMORY_CONTEXT_MAX_CHARS", "3000"))
MEMORY_LONG_TERM_TOP_K = int(os.getenv("MEMORY_LONG_TERM_TOP_K", "3"))
# GraphRAG 多跳深度（1~3）
GRAPH_HOPS = int(os.getenv("GRAPH_HOPS", "2"))

EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
USE_HASH_EMBEDDINGS = _env_bool("USE_HASH_EMBEDDINGS", False)
VECTORSTORE_DIR = os.getenv(
    "VECTORSTORE_DIR",
    os.getenv("CHROMA_PERSIST_DIR", str(BASE_DIR / "data" / "vectorstore")),
)
VECTOR_BACKEND = os.getenv("VECTOR_BACKEND", "milvus").strip().lower()
MILVUS_URI = os.getenv("MILVUS_URI", "http://127.0.0.1:19530")
MILVUS_TOKEN = os.getenv("MILVUS_TOKEN", "")
MILVUS_COLLECTION = os.getenv("MILVUS_COLLECTION", "public_health_chunks")
MILVUS_HNSW_M = int(os.getenv("MILVUS_HNSW_M", "32"))
MILVUS_HNSW_EF_CONSTRUCTION = int(os.getenv("MILVUS_HNSW_EF_CONSTRUCTION", "200"))
MILVUS_HNSW_EF = int(os.getenv("MILVUS_HNSW_EF", "64"))
MILVUS_FALLBACK_TO_FAISS = _env_bool("MILVUS_FALLBACK_TO_FAISS", True)

NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USER = os.getenv("NEO4J_USER", "")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

PDF_OCR_MAX_PAGES = int(os.getenv("PDF_OCR_MAX_PAGES", "30"))
PDF_OCR_SCALE = float(os.getenv("PDF_OCR_SCALE", "1.6"))
PDF_OCR_EARLY_STOP_LEN = int(os.getenv("PDF_OCR_EARLY_STOP_LEN", "2500"))
