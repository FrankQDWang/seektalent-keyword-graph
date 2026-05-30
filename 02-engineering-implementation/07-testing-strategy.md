# 07. 测试策略

## 测试目标

关键词包最容易出问题的不是接口能不能被调用，而是：

- 词面规范化错误。
- 别名错误合并。
- snapshot 不可复盘。
- runtime 误触 CTS 或读取 secret。
- SeekTalent 合同漂移。

测试要围绕这些风险设计。

## 测试分层

| 层级 | 目标 |
| --- | --- |
| Unit tests | 纯函数和策略正确 |
| Snapshot tests | SQLite snapshot schema、索引和回放稳定 |
| Contract tests | Pydantic / JSON schema 与 SeekTalent 合同稳定 |
| Builder integration tests | JD fixture -> fake CTS -> snapshot |
| Snapshot replay tests | 固定评估集回放 |
| Package smoke tests | wheel 安装、跨平台路径、只读 snapshot |

## Unit Tests

重点覆盖：

- surface normalization。
- recall bucket 判断。
- serving score。
- rejection reason。
- bundle builder。
- company_like / department_like 阻断规则。
- stale observation warning。

示例用例：

| 输入 | 期望 |
| --- | --- |
| `Ｋ８Ｓ` | 规范化为 `k8s`，保留 display |
| `沟通能力` | `too_generic`，不进 anchor |
| `k8s` + zero total | 不直接推荐，尝试 `Kubernetes` |
| `Python` + too_wide | 需要 companion term |

## Snapshot Tests

覆盖：

1. 打开只读 SQLite snapshot。
2. 校验 `snapshot_meta`。
3. 校验必要表和索引存在。
4. schema version 不兼容时明确失败。
5. 同一输入、同一 snapshot 输出稳定。
6. snapshot 不包含 CTS credentials、candidate list、简历正文。

## Builder Integration Tests

用本地 fixtures，不需要 Docker Compose：

1. 导入小批 JD fixture。
2. 抽取关键词。
3. fake CTS 返回 `data.total`。
4. 构建 runtime snapshot。
5. 通过 package API 调用 `build_query_plan()`。
6. 校验 lineage、warnings、rejected surfaces。

## Fake CTS

fake CTS 必须支持：

- 固定 query 返回固定 total。
- 模拟 timeout。
- 模拟 429。
- 模拟 5xx。
- 模拟 auth error。
- 记录请求数量，用于验证限速和 retry。

真实 CTS 不进入 CI。真实 CTS 只做内部手动 smoke 或受控构建任务。

## Contract Tests

合同测试包括：

- request / response example 校验。
- JSON schema 兼容性检查。
- enum 兼容性检查。
- SeekTalent 侧消费方测试。
- runtime 不依赖 builder / cts import。

破坏性 diff 必须失败。

## Snapshot Replay Tests

固定评估集示例：

```text
tests/fixtures/eval_jds/
  python_agent_engineer.md
  java_backend_payment.md
  recommendation_algorithm.md
  aigc_product_manager.md
  supply_chain_planner.md
```

每个样本保存期望：

- 应推荐的 concept。
- 不应推荐的 surface。
- 至少一个 anchor bundle。
- 不允许出现 company / department。

## CTS Probe Tests

只测试内部 builder 行为：

- RPS 不超过配置。
- concurrency 不超过配置。
- 429 后降速。
- auth error 后暂停。
- failed observation 不覆盖旧成功 observation。
- `pageSize=1` 且只读取 `data.total`。

## Package Smoke

验证：

- wheel 可安装。
- macOS / Windows 路径处理正确。
- snapshot 文件路径含空格也能打开。
- package import 不启动后台线程。
- package import 不读取 `.env`。
- read-only snapshot 运行通过。

## 测试数据原则

- 不使用真实简历正文。
- JD 样本可脱敏或来自公开样本。
- CTS response 使用合成 total。
- 敏感字段不要进入 fixtures。

## CI 必跑与可选

每个 PR 必跑：

- ruff format check。
- ruff lint。
- typecheck。
- unit tests。
- contract tests。
- snapshot schema smoke。
- builder integration with fake CTS。

main / release 跑：

- snapshot replay。
- wheel build and install smoke。
- snapshot artifact validation。
