# Milvus 向量检索

项目默认通过 `MILVUS_URI` 连接 Milvus，首次调用“向量化文档”接口时自动创建 `public_health_chunks` 集合，并为 `vector` 字段创建 HNSW 索引。

## 启动 Milvus

可使用 Milvus 官方 Docker Compose 部署 Standalone 服务。服务启动后，在项目 `.env` 中配置：

```dotenv
VECTOR_BACKEND=milvus
MILVUS_URI=http://127.0.0.1:19530
MILVUS_COLLECTION=public_health_chunks
```

服务启动后，按项目流程上传 PDF、解析、调用 `/api/qa/embed/{document_id}/`，再调用问答接口。重新向量化同一文档时，服务会先删除该文档在 Milvus 中的旧 chunk，避免重复召回。

如果本地暂时没有 Milvus，可将 `VECTOR_BACKEND=faiss`；默认的 `MILVUS_FALLBACK_TO_FAISS=1` 也会在 Milvus 不可用时自动回退到原有 FAISS。
