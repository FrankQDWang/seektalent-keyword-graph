# 00. 技术栈选型

## 结论

第一版推荐技术栈：

| 层 | 选择 |
| --- | --- |
| 语言 | Python 3.12+ |
| 包管理 | uv |
| 包形态 | 可安装 Python package |
| Runtime 存储 | SQLite snapshot，只读为主 |
| 构建存储 | SQLite build database / JSONL staging |
| 数据模型 | Pydantic v2，用于输入输出 contract |
| HTTP 客户端 | httpx，仅内部离线 CTS probe 使用 |
| 图关系表达 | SQLite 表：concepts / surfaces / relations / cooccurrence |
| 全文 / 轻量检索 | SQLite FTS5，按需使用 |
| 离线任务 | CLI 命令 + asyncio batch |
| 测试 | pytest、ruff、ty 或 mypy |
| 分发 | wheel + versioned SQLite snapshot |
| SeekTalent 集成 | Python dependency + thin adapter |

第一版不采用：

- FastAPI / Uvicorn 常驻服务。
- Docker Compose 作为用户必需运行方式。
- PostgreSQL。
- Neo4j。
- Redis。
- Celery。
- Kubernetes。
- 用户侧 CTS key。

## 为什么做 package

SeekTalent 主仓库已经承担运行编排、LLM、CTS retrieval、评分、artifacts 和 UI/workbench。关键词能力继续直接塞进 SeekTalent 会增加主项目复杂度。

独立 package 的边界更清晰：

```text
SeekTalent: 何时搜索、如何执行 CTS、如何评分和产出结果
Keyword Graph package: 哪些词更适合搜、为什么
CTS probe builder: 我们内部离线计算词面召回统计
```

SeekTalent 只依赖稳定 contract，不读取构建流程内部细节。

## 为什么用 SQLite

第一版数据规模是关键词图谱，不是大规模在线图数据库：

- 约 9530 条公开 JD 样本足够启动第一版。
- surface / concept / relation / cooccurrence 是中小规模结构化数据。
- 用户 runtime 只做本地查表、短路径扩展、排序和解释。
- SQLite 跨 macOS / Windows / Linux，安装成本最低。
- SQLite snapshot 可以作为单文件版本化、校验、压缩和分发。

Neo4j 对第一版是过重依赖。它适合未来做交互式图探索或共享服务，不适合作为用户本地必需组件。

## Runtime 与 Builder 分离

### Runtime package

用户本地只需要：

```python
from seektalent_keyword_graph import KeywordGraph, QueryPlanRequest

engine = KeywordGraph.open("~/.seektalent/keyword-graph/snapshots/latest.sqlite3")
response = engine.build_query_plan(request)
```

Runtime 只读 snapshot，不调用 CTS，不持有 CTS key。

### Builder tools

我们内部使用 CLI 构建 snapshot：

```text
keyword-graph import-jds data/factual_jobs_mainland.jsonl
keyword-graph extract-surfaces
keyword-graph build-relations
keyword-graph probe-cts --page-size 1 --max-rps 1
keyword-graph build-snapshot
keyword-graph validate-snapshot
```

CTS 探测只发生在 builder tools 中，读取 `data.total` 作为 hit count。builder 可以使用内部 `.env` 或 secret manager；这些凭证不进入 wheel、snapshot、fixtures 或用户机器。

## 数据模型：Pydantic v2

用途：

- Runtime request / response。
- Snapshot metadata。
- Builder job payload。
- Contract test fixture。

原则：

- 对 SeekTalent 暴露的 contract model 必须稳定。
- Snapshot 内部 schema 可以演化，但必须带 `snapshot_schema_version`。
- 不把 SQLite row 直接暴露为 response。

## SQLite Snapshot

Snapshot 至少包含：

- `snapshot_meta`
- `concepts`
- `surfaces`
- `concept_surfaces`
- `surface_relations`
- `cooccurrence_edges`
- `cts_recall_observations`
- `selection_policy_meta`

Runtime 打开 snapshot 时必须校验：

- schema version 支持。
- snapshot checksum / build id 存在。
- 必要表和索引存在。
- active concepts 和 serving surfaces 可读。

## 观测

第一版不做 Prometheus 或 OpenTelemetry 服务指标。Runtime 以结构化 response 和 SeekTalent artifacts 为主：

- `kg_snapshot_id`
- `selection_policy_version`
- `input_hash`
- selected / rejected surfaces
- reason codes
- warnings

Builder 侧输出本地 JSONL logs 和 build report。

## 可替换点

为了避免锁死，以下边界保持清晰，但不提前抽象过度：

- Snapshot store：SQLite 第一版，未来可替换为服务端 API。
- CTS probe client：内部 builder 使用，runtime 不依赖。
- Extractor：规则、词典、统计、LLM 辅助都产出同一 mention/surface 中间格式。
