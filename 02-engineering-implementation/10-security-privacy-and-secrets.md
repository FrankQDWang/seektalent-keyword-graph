# 10. 安全、隐私与 Secrets

## 数据边界

第一阶段 runtime package 只需要：

- JD / RequirementSheet 输入。
- 关键词 mention 和 surface 摘要。
- 预计算 CTS `data.total` 聚合数量。
- Query bundle lineage。

默认不需要：

- 原始简历全文。
- 候选人姓名。
- 联系方式。
- 身份证、邮箱、电话等敏感字段。
- 简历附件。
- CTS credentials。

## 原则

1. 用户侧 runtime 不持有 CTS key。
2. CTS probe 只在内部 snapshot 构建环境运行。
3. 发布的 wheel、snapshot、fixtures、logs 不包含 secrets。
4. Snapshot 只保存聚合数量，不保存 candidate list。
5. 任何候选人级数据写入都需要单独 RFC。
6. 日志不打完整 JD、大段 evidence 或敏感字段。

## Runtime 安全边界

Runtime package：

- 只读本地 SQLite snapshot。
- 不读取 CTS 相关环境变量。
- 不发起网络请求。
- 不启动后台线程。
- 不写入全局状态。

SeekTalent 集成层可以记录 query bundle artifact，但必须避免保存完整敏感输入。

## Builder Secrets 管理

禁止：

- secrets 写入 repo。
- secrets 写入 wheel。
- secrets 写入 SQLite snapshot。
- secrets 打进日志。
- secrets 放到 fixtures。

推荐：

- 内部构建环境使用本地 `.env` 或公司 secret manager。
- `.env` 永不提交。
- CI 默认只使用 fake CTS。
- 生产 CTS 凭证不进入公共 CI。

## 日志脱敏

日志中允许：

- `request_id`
- `seek_talent_run_id`
- `kg_snapshot_id`
- query hash
- `data.total`
- latency
- error code

日志中不允许：

- 完整 JD 文本。
- 原始简历文本。
- CTS tenant secret。
- 候选人联系方式。
- candidate list。
- 大段 evidence。

## Artifact 策略

发布 artifact：

- wheel / sdist。
- SQLite snapshot。
- snapshot manifest。
- JSON schema。
- replay report。

发布 artifact 不允许包含：

- CTS key。
- CTS response candidate 内容。
- 原始简历正文。
- 候选人 ID。
- 内部 `.env`。

JD artifact 只在内部构建环境按数据来源授权和公司政策保留。Runtime snapshot 不需要 JD 原文全文。

## 数据保留

| 数据 | 保留建议 |
| --- | --- |
| Internal build logs | 30-90 天，按公司标准 |
| CTS observation 明细 | 内部保留 6-12 个月 |
| Snapshot 聚合统计 | 可长期保留 |
| JD artifact | 按数据来源授权和公司政策 |
| probe job 明细 | 内部保留 3-6 个月 |
| Runtime artifacts | 由 SeekTalent 自身策略控制 |

## 权限模型

角色：

| 角色 | 权限 |
| --- | --- |
| package_reader | 使用发布的 package 和 snapshot |
| builder_operator | 运行内部构建任务 |
| probe_operator | 使用内部 CTS key 做 count-only probe |
| sample_reviewer | 抽样检查高风险 concept / surface，不承担大规模人工复核 |
| release_operator | 发布 snapshot artifact |
| admin | 管理 secrets、配置和权限 |

## 审计动作

以下动作必须审计：

- 开启真实 CTS probe。
- 修改 CTS probe RPS / concurrency / running window。
- 发布 snapshot。
- 回滚 snapshot。
- merge / split concept。
- 标记 surface query_safe。
- 导出任何内部构建数据。

## 安全测试

CI / release 前至少检查：

- `.env` 未提交。
- wheel 不含 secrets。
- snapshot 不含 secrets。
- snapshot 不含 candidate list 或简历正文。
- runtime import 不读取 `.env`。
- fake CTS 是默认测试模式。
- JSON schema / examples 不包含敏感样本。

## 特别注意：CTS API

CTS 是内部关键资源。关键词项目默认保守：

- 真实 probe 必须显式开启。
- 初始 `1 RPS / 并发 1`。
- 默认只在 09:00-21:00 运行，夜间暂停。
- 有退避和暂停机制。
- 只请求 `page=1`、`pageSize=1`。
- 只读取 `data.total`。
- 不保存 candidate 内容。

如果 CTS owner 没有给明确配额，不提高并发。
