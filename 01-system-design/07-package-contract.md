# 07. Package 合同

## 合同设计原则

1. 本地调用：第一阶段不是 HTTP 服务，而是 Python package API。
2. 版本化：request / response / snapshot 都带 schema version。
3. 可回放：推荐响应必须包含 `kg_snapshot_id`。
4. 可解释：返回推荐词，也返回拒绝词和选择原因。
5. 可降级：package 或 snapshot 不可用时，SeekTalent 可以回退原策略。
6. 无 CTS key：runtime contract 不包含任何 CTS credential 字段。

## Python API

```python
from seektalent_keyword_graph import KeywordGraph, QueryPlanRequest

engine = KeywordGraph.open(snapshot_path)
response = engine.build_query_plan(
    QueryPlanRequest(
        request_id="req_01H...",
        seek_talent_run_id="run_2026_...",
        job_title="Python agent engineer",
        jd_text="...",
        notes="Shanghai preferred, avoid pure frontend profiles",
        requirement_terms=[
            {"text": "Python", "strength": "required"},
            {"text": "retrieval", "strength": "preferred"},
        ],
        max_query_bundles=4,
    )
)
```

## `QueryPlanRequest`

```json
{
  "schema_version": "query-plan-request-v1",
  "request_id": "req_01H...",
  "seek_talent_run_id": "run_2026_...",
  "kg_snapshot_id": "latest",
  "job_title": "Python agent engineer",
  "jd_text": "...",
  "notes": "Shanghai preferred, avoid pure frontend profiles",
  "requirement_terms": [
    {"text": "Python", "strength": "required"},
    {"text": "retrieval", "strength": "preferred"}
  ],
  "max_query_bundles": 4
}
```

## `QueryPlanResponse`

```json
{
  "schema_version": "query-plan-response-v1",
  "request_id": "req_01H...",
  "kg_snapshot_id": "kg_2026_05_30_001",
  "concept_sheet": [
    {
      "concept_id": "concept_python",
      "label": "Python",
      "confidence": 0.98,
      "evidence_refs": ["input:requirement_terms:0"]
    }
  ],
  "query_bundles": [
    {
      "bundle_id": "bundle_anchor_1",
      "bundle_type": "anchor",
      "priority": 1,
      "queries": [
        {
          "query_text": "Python agent engineer",
          "surfaces": ["surface_python", "surface_agent_engineer"],
          "expected_hit_count": 1280,
          "confidence": 0.86,
          "reason_codes": ["required_term", "healthy_recall", "stable_surface"]
        }
      ]
    }
  ],
  "rejected_surfaces": [
    {
      "surface_text": "AI公司",
      "reason_code": "company_like",
      "message": "第一阶段不处理公司实体"
    }
  ],
  "lineage": {
    "input_hash": "sha256:...",
    "snapshot_schema_version": "snapshot-v1",
    "selection_policy_version": "policy-v1"
  },
  "warnings": []
}
```

## Lookup API

Runtime 可以提供本地 lookup 函数，供调试和测试使用：

```python
surface = engine.lookup_surface("k8s")
concept = engine.get_concept("concept_kubernetes")
```

返回：

- surface 基本信息。
- 关联 concepts。
- 最新 CTS total。
- recall bucket。
- 是否 query_safe。
- 推荐替代词。

## Builder CLI

Builder CLI 是内部工具，不是用户 runtime API：

```text
keyword-graph import-jds ...
keyword-graph extract-surfaces ...
keyword-graph probe-cts ...
keyword-graph build-snapshot ...
keyword-graph validate-snapshot ...
```

`probe-cts` 只在内部构建环境可用，需要 CTS credentials。发布给用户的 package 可以包含命令入口，但没有 credentials 时不能执行真实 probe。

## 错误模型

Runtime 错误用 Python exceptions 和 response warnings 表达：

| 错误 | 处理 |
| --- | --- |
| snapshot 文件不存在 | raise `SnapshotUnavailableError` |
| snapshot schema 不支持 | raise `UnsupportedSnapshotError` |
| 输入字段错误 | Pydantic validation error |
| 无可用 concept | 返回 fallback bundle + warning |
| snapshot observation 过期 | 返回 stale warning |

## 兼容策略

- 新增 response 字段必须 optional 或有默认值。
- 删除字段或改变语义必须升级 schema version。
- Snapshot schema 变更必须带 migration notes 和兼容测试。
- SeekTalent 侧只依赖稳定字段，不读取实验字段。
