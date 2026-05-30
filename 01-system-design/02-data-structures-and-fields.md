# 02. 数据结构与字段

本文件描述系统级数据结构，不绑定具体数据库实现。第一版 runtime snapshot 使用 SQLite，内部构建阶段也可使用 SQLite build DB。

## JDDocument

表示一份原始 JD 的登记信息。第一阶段可以保存公司等原始元数据，但不把公司建成图节点。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `jd_id` | string | 是 | 系统生成 ID |
| `source` | string | 是 | 数据来源，如 public_jd / uploaded / internal_review |
| `source_ref` | string | 否 | 外部引用，不直接暴露 |
| `title_raw` | string | 是 | 原始岗位标题 |
| `jd_text_ref` | string | 是 | 原文 artifact 引用，不建议放入 runtime snapshot |
| `content_hash` | string | 是 | 去重 hash |
| `language` | enum | 否 | zh / en / mixed / unknown |
| `captured_at` | datetime | 否 | 获取时间 |
| `created_at` | datetime | 是 | 入库时间 |
| `quality_flags` | list | 否 | empty / duplicated / malformed / too_short |

## JDSection

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `section_id` | string | 段落 ID |
| `jd_id` | string | 所属 JD |
| `section_type` | enum | title / responsibility / requirement / preferred / compensation / other |
| `text_ref` | string | 段落 artifact 引用 |
| `start_offset` / `end_offset` | int | 原文字符位置 |
| `confidence` | float | 分段置信度 |

## KeywordMention

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `mention_id` | string | 关键词证据 ID |
| `jd_id` | string | 所属 JD |
| `section_id` | string | 所在段落 |
| `surface_text_raw` | string | 原始词面 |
| `surface_text_norm` | string | 规范化词面 |
| `mention_type` | enum | skill / tool / framework / language / certificate / method / job_keyword / qualification |
| `requirement_strength` | enum | required / preferred / nice_to_have / unknown |
| `evidence_ref` | string | 原句或短窗口引用 |
| `extractor_name` | string | 抽取器名称 |
| `extractor_version` | string | 抽取器版本 |
| `confidence` | float | 抽取置信度 |
| `review_status` | enum | pending / accepted / rejected / corrected |

## SurfaceForm

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `surface_id` | string | 词面 ID |
| `text_raw` | string | 原始写法 |
| `text_norm` | string | 规范化写法 |
| `display_text` | string | 对外展示写法 |
| `language` | enum | zh / en / mixed / symbol / unknown |
| `token_class` | enum | skill / tool / framework / language / certificate / method / job_keyword / qualification |
| `query_safe` | bool | 是否允许进入查询推荐 |
| `is_exact_phrase_preferred` | bool | 是否建议精确短语搜索，第一版不假设 CTS 支持 |
| `ambiguity_score` | float | 歧义程度，越高越危险 |
| `specificity_score` | float | 专指程度，越高越窄 |
| `jd_df` | int | 出现在多少份 JD 中 |
| `jd_tf_total` | int | JD 总出现次数 |
| `latest_cts_total` | int | 最近一次内部 CTS `data.total` |
| `latest_cts_observed_at` | datetime | 最近内部探测时间 |
| `latest_cts_status` | enum | success / zero / too_wide / failed / stale / unknown |
| `serving_status` | enum | candidate / verified / serving / stale / blocked / rejected |
| `created_at` / `updated_at` | datetime | 生命周期时间 |

## Concept

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `concept_id` | string | 概念 ID |
| `canonical_label` | string | 推荐展示名 |
| `concept_type` | enum | 同 SurfaceForm 的 token_class |
| `description` | string | 简短定义，可为空 |
| `primary_surface_id` | string | 默认搜索词面 |
| `surface_count` | int | 词面数 |
| `jd_df` | int | 相关词面在 JD 中的去重覆盖 |
| `latest_cts_total_sum` | int | 可搜索词面的召回总量摘要，注意不等于候选人去重数 |
| `stability_score` | float | 词面选择稳定性 |
| `review_status` | enum | candidate / active / needs_review / deprecated / blocked |
| `created_at` / `updated_at` | datetime | 生命周期时间 |

## SurfaceRelation

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `relation_id` | string | 关系 ID |
| `from_surface_id` | string | 起点 |
| `to_surface_id` | string | 终点 |
| `relation_type` | enum | alias_of / abbreviates / translates_to / spelling_variant / version_variant |
| `confidence` | float | 置信度 |
| `evidence_type` | enum | rule / jd_cooccurrence / cts_similarity / human_review / seed_dict |
| `created_by` | string | 规则、模型或人工 |
| `status` | enum | candidate / active / rejected |

## CoOccurrenceEdge

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `edge_id` | string | 共现边 ID |
| `surface_id_a` | string | 词面 A |
| `surface_id_b` | string | 词面 B |
| `window_type` | enum | same_jd / same_section / same_sentence / title_plus_requirement |
| `cooccur_count` | int | 共现次数 |
| `pmi` | float | 点互信息 |
| `jaccard` | float | Jaccard 系数 |
| `support` | int | 支持度 |
| `last_computed_at` | datetime | 计算时间 |

## CTSProbeJob

内部构建字段，不进入用户 runtime API。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `probe_job_id` | string | 探测任务 ID |
| `surface_id` | string | 目标词面 |
| `query_text` | string | 实际发给 CTS 的查询词 |
| `query_mode` | enum | normal / exact_phrase / quoted / boolean_if_supported |
| `priority` | int | 优先级，数字越小越高 |
| `dedupe_key` | string | 去重键 |
| `scheduled_at` | datetime | 计划时间 |
| `not_before` | datetime | 最早执行时间 |
| `attempt_count` | int | 已尝试次数 |
| `status` | enum | pending / running / success / retry_wait / failed / canceled |
| `rate_limit_bucket` | string | 使用的限速桶 |
| `created_reason` | enum | new_surface / stale_refresh / manual / evaluation |

## CTSRecallObservation

内部构建字段；runtime snapshot 只保存必要摘要。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `observation_id` | string | 观察 ID |
| `probe_job_id` | string | 对应任务 |
| `surface_id` | string | 被探测词面 |
| `query_text` | string | 实际查询词 |
| `query_hash` | string | 查询 hash |
| `total` | int | CTS `data.total` |
| `latency_ms` | int | 响应耗时 |
| `status` | enum | success / zero / timeout / rate_limited / api_error / auth_error |
| `error_code` | string | 错误码 |
| `observed_at` | datetime | 探测时间 |
| `cts_api_version` | string | CTS 接口版本 |
| `builder_run_id` | string | 内部构建任务 ID |

不保存 `result_sample_ref`，除非另有隐私 RFC。

## QueryPlanRequest

SeekTalent 本地调用 package 时的请求对象。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `schema_version` | string | `query-plan-request-v1` |
| `request_id` | string | 请求 ID |
| `seek_talent_run_id` | string | SeekTalent run ID |
| `job_title` | string | 岗位标题 |
| `jd_text` | string | JD 文本，可传摘要或完整文本 |
| `requirement_terms` | list | SeekTalent 已抽取的需求词，可为空 |
| `notes` | string | 用户补充说明，可为空 |
| `kg_snapshot_id` | string | 指定快照，默认 latest |
| `max_query_bundles` | int | 返回查询族数量上限 |

## QueryPlanResponse

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `schema_version` | string | `query-plan-response-v1` |
| `request_id` | string | 回显请求 ID |
| `kg_snapshot_id` | string | 实际使用快照 |
| `concept_sheet` | list | 识别到的关键词概念 |
| `query_bundles` | list | 推荐查询族 |
| `rejected_surfaces` | list | 被拒绝词面及原因 |
| `lineage` | object | 选择链路摘要 |
| `warnings` | list | 低置信、snapshot 过期、观察过期等提示 |

## 字段设计底线

- 原始简历正文不进入这些结构。
- 候选人 ID 默认不保存。
- 用户本地没有 CTS key，也没有 probe 字段。
- 所有 runtime 响应都必须能用 `kg_snapshot_id` 复盘。
- `total` 是搜索结果数量，不等于真实可联系候选人数，也不等于质量。
