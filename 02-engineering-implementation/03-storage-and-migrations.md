# 03. 存储与迁移设计

## 存储分工

| 存储 | 职责 |
| --- | --- |
| SQLite build database | 内部构建阶段保存 JD、mention、surface、relation、probe observation |
| SQLite runtime snapshot | 用户本地只读查询；由 build database 投影生成 |
| JSONL staging | 大批量导入、审计和中间产物 |
| Release artifact | 分发压缩后的 versioned snapshot |

第一版不使用 PostgreSQL、Neo4j、Redis。

## 为什么 SQLite 足够

第一版 runtime 查询是短路径关键词扩展，不是任意图遍历：

1. 从输入 terms resolve 到 concept。
2. 从 concept 找 serving surfaces。
3. 沿 alias / abbreviation / translation / cooccurrence 做有限扩展。
4. 按 CTS recall bucket、specificity、ambiguity、requirement strength 排序。

这些都可以用 SQLite 索引和少量 join 完成。SQLite 单文件也更适合跨平台分发和本地使用。

## Runtime Snapshot 表设计草案

### `snapshot_meta`

- `key`
- `value`

必须包含：

- `kg_snapshot_id`
- `snapshot_schema_version`
- `selection_policy_version`
- `built_at`
- `source_corpus_version`
- `cts_probe_window_start`
- `cts_probe_window_end`
- `build_report_sha256`

### `concepts`

- `concept_id`
- `canonical_label`
- `concept_type`
- `description`
- `primary_surface_id`
- `review_status`
- `jd_df`
- `surface_count`
- `stability_score`

### `surfaces`

- `surface_id`
- `text_raw`
- `text_norm`
- `display_text`
- `language`
- `token_class`
- `query_safe`
- `is_exact_phrase_preferred`
- `ambiguity_score`
- `specificity_score`
- `jd_df`
- `jd_tf_total`
- `latest_cts_total`
- `latest_cts_status`
- `latest_cts_observed_at`
- `recall_bucket`
- `serving_status`

### `concept_surfaces`

- `concept_id`
- `surface_id`
- `confidence`
- `source`
- `status`

### `surface_relations`

- `relation_id`
- `from_surface_id`
- `to_surface_id`
- `relation_type`
- `confidence`
- `evidence_type`
- `status`

### `cooccurrence_edges`

- `edge_id`
- `surface_id_a`
- `surface_id_b`
- `window_type`
- `cooccur_count`
- `pmi`
- `jaccard`
- `support`

### `cts_recall_observations`

- `observation_id`
- `surface_id`
- `query_text`
- `query_hash`
- `query_mode`
- `total`
- `latency_ms`
- `status`
- `error_code`
- `observed_at`
- `cts_api_version`

只保存 CTS 聚合数量和请求摘要，不保存 candidate 列表或简历正文。

### `fts_surfaces`

可选 FTS5 表，用于输入 term 到 surface 的轻量 lookup。

## Builder-only 表

构建数据库可以额外包含：

- `jd_documents`
- `jd_sections`
- `keyword_mentions`
- `probe_jobs`
- `review_decisions`
- `build_events`

这些表不一定进入 runtime snapshot。

## 索引

最低索引：

- `surfaces(text_norm)`
- `surfaces(recall_bucket, serving_status)`
- `concept_surfaces(concept_id)`
- `concept_surfaces(surface_id)`
- `surface_relations(from_surface_id, relation_type)`
- `cooccurrence_edges(surface_id_a)`
- `cooccurrence_edges(surface_id_b)`
- `cts_recall_observations(surface_id, observed_at)`

## 迁移策略

SQLite snapshot 是发布物，不做用户侧在线迁移。新 schema 发布新 snapshot。

Runtime 规则：

- 只打开受支持的 `snapshot_schema_version`。
- 不在用户本地修改 snapshot。
- 需要升级时下载或安装新 snapshot。

Builder database 可以用显式 SQL migration 文件：

```text
migrations/sqlite/
  001_initial.sql
  002_probe_observations.sql
  003_snapshot_indexes.sql
```

## 快照重建

任何时候应能从公开 JD 样本、自动治理决策、抽样检查记录和 CTS observation 重建 runtime snapshot：

```text
JD samples + policy decisions + sampled review records + CTS totals -> build db -> runtime snapshot -> validation -> release artifact
```

这要求：

- CTS observations 保留内部构建记录。
- 抽样检查结果进入 build database 或 review JSONL。
- runtime snapshot 不保存唯一不可重建事实。

## 数据保留

| 数据 | 保留策略 |
| --- | --- |
| JD source samples | 按公开数据授权和内部政策保留 |
| KeywordMention | 内部长期保留，可重算 |
| CTS observation 明细 | 内部保留 6-12 个月，聚合进入 snapshot |
| Runtime snapshot | release 版本长期保留 |
| 用户本地 query artifacts | 由 SeekTalent 管理 |

用户本地不会保存 CTS key，也不会保存 CTS candidate 列表。
