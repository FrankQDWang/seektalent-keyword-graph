# 08. CI/CD 流水线

## 流水线目标

CI/CD 防止四类漂移：

1. 代码质量漂移。
2. Package 合同漂移。
3. Snapshot schema 漂移。
4. 图谱构建和文档漂移。

## Workflow 划分

```text
.github/workflows/
  ci.yml
  contract.yml
  snapshot.yml
  release.yml
```

第一阶段不需要 `docker.yml`。

## `ci.yml`

触发：PR、main push。

步骤：

1. checkout。
2. setup Python 3.12。
3. install uv。
4. uv sync。
5. ruff format check。
6. ruff lint。
7. typecheck。
8. unit tests。
9. architecture import boundary check。
10. wheel build smoke。

必过才能合并。

## `contract.yml`

触发：PR、main push。

步骤：

1. 生成 request / response JSON schema。
2. 与 `contracts/query-plan/*.schema.json` 比较。
3. 校验 examples。
4. 运行兼容性检查。
5. 生成 contract diff comment。

如果出现破坏性变更，CI fail。

## `snapshot.yml`

触发：PR 可选、main 必跑、release 必跑。

步骤：

1. 导入 fixture JD。
2. fake CTS probe。
3. 构建 test snapshot。
4. 校验 snapshot schema。
5. 跑 replay eval。
6. 校验 snapshot 不含 secrets、candidate list、简历正文。
7. 上传 report artifact。

## `release.yml`

触发：tag 或手动。

步骤：

1. 确认 main CI 通过。
2. build wheel / sdist。
3. 生成 JSON schema artifact。
4. 校验并打包 SQLite snapshot。
5. 生成 snapshot manifest 和 checksum。
6. 生成 release notes。
7. 发布 package 与 snapshot artifact。

## 必要检查项

| 检查 | PR 必过 | main 必过 | release |
| --- | --- | --- | --- |
| ruff | 是 | 是 | 是 |
| typecheck | 是 | 是 | 是 |
| unit tests | 是 | 是 | 是 |
| contract tests | 是 | 是 | 是 |
| snapshot schema smoke | 是 | 是 | 是 |
| builder integration fake CTS | 是 | 是 | 是 |
| snapshot replay | 可选 | 是 | 是 |
| wheel install smoke | 是 | 是 | 是 |
| snapshot secret scan | 可选 | 是 | 是 |

## 分支保护

main 分支要求：

- 至少 1 个 reviewer。
- CI 必过。
- contract diff 不破坏。
- snapshot schema 变更需要指定 reviewer。
- CTS builder 适配器和 secrets 边界变更需要 owner review。

## Secrets

CI 不持有真实 CTS 生产凭证。

允许：

- fake CTS。
- 内部 package registry token。
- 只读 release artifact token。

真实 CTS probe 由内部构建环境控制，不由公共 CI 调用。

## Artifact

CI 上传：

- junit test report。
- coverage report。
- JSON schema。
- contract diff。
- snapshot replay report。
- wheel / sdist build artifact。
- snapshot manifest。

## 回滚策略

Package 回滚：

- 降级到上一 Python package 版本。

Snapshot 回滚：

- SeekTalent 配置指向上一 snapshot。
- 保留上一 snapshot manifest 和 checksum。

Snapshot schema 不做用户侧在线迁移。新 schema 发布新 snapshot。

## 发布版本

建议版本格式：

```text
package: 0.1.0
request_schema: query-plan-request-v1
response_schema: query-plan-response-v1
snapshot_schema: snapshot-v1
selection_policy: policy-v1
snapshot: kg_2026_05_30_001
```

Package 版本和 snapshot 版本不要混为一谈。
