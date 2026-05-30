# 05. Package 合同实现计划

## 实现顺序

1. 定义 Pydantic request / response model。
2. 写 JSON schema 和 example payload。
3. 实现 `KeywordGraph.open(snapshot_path)`。
4. 实现 snapshot schema 校验。
5. 实现 `build_query_plan()`。
6. 写 contract tests，供 SeekTalent 侧复用。

第一阶段不实现 FastAPI routes，也不导出 OpenAPI。

## 模块分工

```text
src/seektalent_keyword_graph/__init__.py
src/seektalent_keyword_graph/engine.py
src/seektalent_keyword_graph/contracts/query_plan.py
src/seektalent_keyword_graph/domain/policies.py
src/seektalent_keyword_graph/runtime/sqlite_snapshot.py
src/seektalent_keyword_graph/runtime/errors.py
```

内部构建工具放在单独命名空间：

```text
src/seektalent_keyword_graph/builder/
src/seektalent_keyword_graph/cts/
```

Runtime 代码不能 import `builder` 或 `cts`。

## 版本策略

- request schema：`query-plan-request-v1`。
- response schema：`query-plan-response-v1`。
- snapshot schema：`snapshot-v1`。
- selection policy：`policy-v1`。
- package version：PEP 440，例如 `0.1.0`。

响应必须包含 `kg_snapshot_id`、`snapshot_schema_version` 和 `selection_policy_version`。

## `build_query_plan()` 实现边界

Public API 层：

- 校验 Pydantic request。
- 打开或复用 snapshot handle。
- 调用 runtime use case。
- 返回 Pydantic response。
- 将可恢复问题放进 `warnings`。

Use case 层：

1. 解析输入中的 title、JD、RequirementSheet terms、notes。
2. 从 snapshot resolve concepts。
3. expand surfaces。
4. 读取 recall summary 和 relation edges。
5. apply selection policy。
6. build query bundles。
7. return lineage。

Domain 层：

- surface scoring。
- rejection reason。
- bundle type decision。
- recall bucket decision。

Snapshot adapter：

- 只负责读取 SQLite。
- 不包含业务排序逻辑。
- 默认 read-only connection。

## 错误处理

Runtime 使用 Python exceptions 和 response warnings：

| 错误 | 处理 |
| --- | --- |
| snapshot 文件不存在 | raise `SnapshotUnavailableError` |
| snapshot schema 不支持 | raise `UnsupportedSnapshotError` |
| snapshot 校验失败 | raise `SnapshotIntegrityError` |
| 输入字段错误 | Pydantic validation error |
| 无可用 concept | 返回 fallback bundle + warning |
| CTS observation 过期 | 返回 stale warning |

SeekTalent 集成层决定 fail-open 还是 fail-closed。默认建议 fail-open：关键词包不可用时回退原策略。

## Contract Tests

测试内容：

- example request 能通过模型校验。
- example response 符合 JSON schema。
- 不允许删除 SeekTalent 已使用字段。
- 新字段必须 optional 或有默认值。
- 同一输入、同一 snapshot 输出稳定。
- runtime 不读取 CTS credential 环境变量。

## Backward Compatibility

破坏性变更包括：

- 删除字段。
- 改字段类型。
- 改 enum 语义。
- 必填字段新增。
- snapshot 表语义变化。

破坏性变更必须升级 schema version，并提供 SeekTalent 迁移说明。

## JSON Schema 发布

每次 release：

- 生成 request / response JSON schema。
- 生成 snapshot manifest schema。
- 上传为 release artifact。
- 和上一个 release 比较 diff。
- 若有破坏性 diff，CI fail。

## SDK 是否需要

不需要单独 SDK。这个项目本身就是 Python package，SeekTalent 直接 import。

## 幂等与追踪

`build_query_plan()` 是读型本地计算。它不写全局状态，但 response 必须带：

- `request_id`
- `seek_talent_run_id`
- `kg_snapshot_id`
- `input_hash`
- `selection_policy_version`

这些字段用于 SeekTalent artifact 复盘。

## 日志字段

默认 runtime 不主动写大日志。若 SeekTalent 集成层记录日志，只允许：

- `request_id`
- `seek_talent_run_id`
- `kg_snapshot_id`
- latency
- warning code
- selected query count

不得打印完整 JD、CTS credential 或候选人信息。
