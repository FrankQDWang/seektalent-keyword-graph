# 09. 观测、评估与治理

## 观测目标

关键词包必须回答三类问题：

1. Snapshot 是否可用？
2. Query bundle 为什么这样生成？
3. 这个推荐是否真的改善了 SeekTalent 的检索？

第一阶段不做服务指标平台。观测主要来自 package response lineage、SeekTalent artifacts、内部构建报告和 snapshot replay。

## Runtime 观测字段

| 字段 | 说明 |
| --- | --- |
| `request_id` | 单次调用 ID |
| `seek_talent_run_id` | SeekTalent run ID |
| `kg_snapshot_id` | 使用的 snapshot |
| `snapshot_schema_version` | snapshot schema |
| `selection_policy_version` | 策略版本 |
| `latency_ms` | 本地调用耗时 |
| `warning_codes` | fallback / stale / no_match 等 |
| `selected_query_count` | 输出 query 数 |

这些字段由 SeekTalent artifact 记录，不需要关键词包自己运行服务端日志。

## 内部构建指标

| 指标 | 说明 |
| --- | --- |
| `snapshot_build_duration` | 快照构建耗时 |
| `surface_count` | 词面数 |
| `concept_count` | 概念数 |
| `relation_count` | 关系数 |
| `cts_probe_success_rate` | 内部 CTS 探测成功率 |
| `cts_p95_latency_ms` | 内部 CTS 探测 p95 延迟 |
| `cts_rate_limited_count` | CTS 限流次数 |
| `snapshot_size_bytes` | 发布文件大小 |
| `snapshot_secret_scan_result` | secrets / candidate 内容扫描结果 |

## 推荐质量指标

### 检索前指标

| 指标 | 说明 |
| --- | --- |
| `query_stability` | 同一 JD、同一 snapshot 下 query bundle 是否稳定 |
| `zero_recall_surface_rate` | 推荐词中零召回比例 |
| `too_wide_surface_rate` | 推荐词中过宽比例 |
| `unknown_observation_rate` | 缺 CTS 观察比例 |
| `rejected_company_like_count` | 被识别为公司 / 部门 / 非关键词的数量 |

### 检索层指标

| 指标 | 说明 |
| --- | --- |
| `cts_hit_count_by_bundle_type` | 各查询族被 SeekTalent 执行后的 CTS 命中数 |
| `unique_candidate_coverage` | 唯一候选覆盖数，由 SeekTalent 回写 |
| `rounds_to_first_healthy_recall` | 第几轮拿到健康召回 |
| `alias_probe_success_rate` | alias 是否改善零召回 |

### 业务层指标

| 指标 | 说明 |
| --- | --- |
| `opened_count_per_query` | 每个 query 带来的打开数 |
| `match_count_per_query` | 每个 query 带来的 Match 数 |
| `maybe_count_per_query` | Maybe 数 |
| `manual_edit_rate` | 顾问是否大量改写关键词 |
| `fallback_rate` | package fallback 比例 |

## 评估集

建立固定评估集：

- 典型岗位 JD。
- 长尾岗位 JD。
- 中英混写 JD。
- 新兴技术 JD。
- 容易过宽的岗位。
- 容易零召回的岗位。

每个样本保存：

- 原 JD 或脱敏引用。
- 期望关键词或人工认可关键词。
- 不应推荐的词。
- 历史 CTS 召回情况。
- SeekTalent 实际结果摘要。

## 回放评估

每个候选 snapshot 发布前运行：

1. 用固定评估集调用 package API。
2. 比较 query bundle 变化。
3. 检查 zero / too_wide / unknown 比例。
4. 检查公司 / 部门误判。
5. 对高风险 diff 进入小样本抽查；无人处理时按保守规则阻断或降级。

## 抽样治理

第一版不做大规模人工复核。人工时间按每天最多 10 分钟设计，主要用于抽查系统自己挑出的高风险样本。

抽样优先级：

1. 高频 surface 即将进入 serving。
2. 高频 concept 合并 / 拆分。
3. 被 SeekTalent 多次使用但效果差的 query。
4. CTS 召回异常的 surface。
5. LLM 提出的长尾新词。

抽样动作必须记录：

- 审核人。
- 审核时间。
- 修改对象。
- 修改前后值。
- 理由。

如果样本无人处理，系统不能卡住发布流程；对应高风险项应默认不进入 anchor，或进入低优先级 exploration。

## 数据治理

### 隐私边界

- 不保存原始简历全文。
- 不保存敏感个人信息。
- 默认只保存聚合数量。
- Runtime snapshot 不包含 CTS key 或 candidate list。
- 如果需要保存候选样本 ID，必须 hash 或使用内部不可逆 ID，并明确保留期限。

### 证据边界

JD 原文可以在内部构建环境保存 artifact 引用；runtime response 只返回必要证据片段或引用，不回传大段原文。

### 合规边界

关键词包只帮助生成检索词，不做最终录用判断，也不自动联系候选人。

## 风险监控

| 风险 | 监控方式 | 处理 |
| --- | --- | --- |
| 别名过度合并 | concept merge diff、抽样检查 | 拆分 concept，回滚 snapshot |
| 热门词偏置 | 高频词占比、too_wide rate | 降权过宽词，要求 companion term |
| CTS API 压力 | 内部 probe rate limited / latency / error | 降速、暂停 probe |
| 词面漂移 | stale observation rate | 下次内部构建刷新高频词 |
| 公司 / 部门误入图谱 | rejected_company_like_count、抽样检查 | 阻断规则和回滚 |
| 推荐不稳定 | query_stability | 固定 snapshot 和排序规则 |

## 审计日志

审计对象：

- 内部 CTS probe 启停。
- CTS 请求摘要。
- Snapshot 发布 / 回滚。
- 抽样检查记录。
- 配置变更。
- 内部构建数据导出。

审计日志必须可按 `builder_run_id`、`request_id`、`seek_talent_run_id`、`kg_snapshot_id` 串起来。
