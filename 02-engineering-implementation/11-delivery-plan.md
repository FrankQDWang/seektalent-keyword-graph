# 11. 交付计划

## M0：项目开仓与文档落地

时间：第 1 周。

交付：

- 新独立 package 仓库初始化。
- `pyproject.toml` / `uv` / `ruff` / `pytest`。
- 基础 package import。
- Contract model 草案。
- SQLite snapshot schema 草案。
- README 写明：无 UI、无常驻服务、用户本地无 CTS key。

验收：

- `make test` 可运行。
- `python -c "import seektalent_keyword_graph"` 成功。
- 小型 fixture snapshot 可被打开。
- README 写明第一阶段只做关键词和本地 snapshot 查询。

## M1：Runtime Contract 与 SQLite Snapshot Reader

时间：第 2 周。

交付：

- `QueryPlanRequest` / `QueryPlanResponse`。
- `KeywordGraph.open(snapshot_path)`。
- snapshot metadata 校验。
- surface / concept lookup。
- fallback warning。

验收：

- 不需要 CTS key 即可运行 runtime。
- 不存在 snapshot 时可明确失败并让 SeekTalent 降级。
- Contract examples 通过测试。

## M2：JD 导入与关键词抽取

时间：第 3-4 周。

交付：

- 导入 9530 条中国大陆公开 JD 样本。
- content hash 去重。
- section splitter。
- rule / dictionary extractor。
- KeywordMention / SurfaceForm build database。

验收：

- 样本 JD 可导入。
- 每个 mention 可回溯到 JD 和 section。
- 抽取报告包含 top surfaces、噪声样本、失败样本。

## M3：Surface / Concept / 共现

时间：第 5-6 周。

交付：

- surface normalization。
- 初始 concept clustering。
- alias / abbreviation / translation relation。
- co-occurrence edge computation。
- 抽样检查报告，先用 CSV 给人看、JSONL 给系统回填。

验收：

- 能生成初始 concept-surface 图数据。
- 高频 surface 有自动 evidence / risk status。
- company / department-like 词被阻断。

## M4：内部 CTS Count Probe

时间：第 7 周。

交付：

- CTS count client。
- fake CTS response fixture。
- `pageSize=1` probe。
- 读取 `data.total`。
- SQLite probe job / observation 表。
- 限速、TTL、退避，真实 CTS 默认 `1 RPS / 并发 1`。

验收：

- fake CTS 测试通过。
- 真实 CTS 小流量 smoke 通过。
- observation 只保存 total / latency / status，不保存 candidate。
- runtime package 不读取 CTS credentials。

## M5：Snapshot Build 与 Query Bundle MVP

时间：第 8-9 周。

交付：

- runtime snapshot build。
- snapshot validate。
- recall bucket 计算。
- `build_query_plan` MVP。
- fixed replay eval。

验收：

- 固定输入固定 snapshot 输出稳定。
- SQLite snapshot 可校验。
- query bundles 有 lineage、reason codes、warnings。
- replay eval 有报告。

## M6：SeekTalent 接入

时间：第 10-11 周。

交付：

- SeekTalent dependency 接入。
- feature flag。
- snapshot path 配置。
- artifacts 写入。
- 降级路径。

验收：

- package 缺失或 snapshot 不可用时 SeekTalent 可正常跑。
- package 开启时 artifacts 完整。
- 评估集上 query 稳定性改善。
- 没有公司 / 部门节点进入第一阶段输出。

## M7：发布硬化

时间：第 12 周以后。

交付：

- snapshot manifest。
- checksum。
- release notes。
- rollback 指引。
- build report。
- 数据保留策略。

验收：

- snapshot 可版本化分发。
- 用户本地不需要 CTS key。
- 可按 request_id / input_hash / snapshot_id 复盘。
- 人工抽样检查不超过每天 10 分钟。
- snapshot 压缩后目标 `<50MB`，硬上限 `<100MB`。
- CTS probe 默认 `1 RPS / 并发 1`，09:00-21:00 运行。

## 首批 Issues 建议

1. `INIT-001`: Initialize standalone package repository。
2. `CONTRACT-001`: Define query plan request / response models。
3. `SNAPSHOT-001`: Define SQLite snapshot schema。
4. `RUNTIME-001`: Implement `KeywordGraph.open` and snapshot validation。
5. `RUNTIME-002`: Implement surface lookup。
6. `DATA-001`: Import public JD sample JSONL。
7. `EXTRACT-001`: Rule extractor for English / mixed technical terms。
8. `EXTRACT-002`: Section splitter for Chinese JD headings。
9. `SURFACE-001`: Surface normalization policy。
10. `GRAPH-001`: Concept / surface / relation builder。
11. `PROBE-001`: Fake CTS count client。
12. `PROBE-002`: Real CTS count probe using `data.total`。
13. `RATE-001`: Offline probe token bucket and TTL dedupe。
14. `BUILD-001`: Build runtime SQLite snapshot。
15. `QUERY-001`: Query bundle MVP。
16. `EVAL-001`: Fixed replay set and report。
17. `ST-001`: SeekTalent package integration behind feature flag。
18. `OBS-001`: Snapshot build report and runtime lineage artifacts。

## 不建议第一批做的事

- 做完整后台管理 UI。
- 做常驻 HTTP 服务。
- 做公司 / 领域 / 部门图谱。
- 做简历向量库。
- 做自动外呼 / 自动私信。
- 追求复杂 LLM agent 编排。
- 上 Neo4j / PostgreSQL / Redis / Celery。
- 上 Docker / Kubernetes 作为用户依赖。
- 让用户本地配置 CTS key。
- 用户运行时实时探测 CTS。
