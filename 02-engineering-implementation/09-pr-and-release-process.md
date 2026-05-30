# 09. PR、评审与发布流程

## 分支策略

- `main`: 永远可发布。
- `feature/<issue-id>-short-name`: 功能分支。
- `fix/<issue-id>-short-name`: bug 修复。
- `release/<version>`: 如需要稳定发布分支再创建。

## Issue 模板

每个 issue 至少包含：

- 背景。
- 目标。
- 非目标。
- 影响模块。
- 验收标准。
- 测试要求。
- 是否影响 package contract。
- 是否影响 snapshot schema。
- 是否影响内部 CTS builder。

## PR 模板

PR 必填：

```markdown
## Summary

## Scope
- [ ] Runtime package
- [ ] Contracts
- [ ] Domain policy
- [ ] Snapshot schema
- [ ] Builder CLI
- [ ] CTS count client
- [ ] Docs

## Compatibility
- [ ] No contract change
- [ ] Backward-compatible contract change
- [ ] Breaking contract change, linked RFC
- [ ] Snapshot schema unchanged
- [ ] Snapshot schema changed, migration notes included

## Testing
- [ ] Unit tests
- [ ] Contract tests
- [ ] Snapshot tests
- [ ] Builder fake CTS integration
- [ ] Manual smoke

## Risk and rollback
```

## Review 规则

| 变更类型 | Reviewer |
| --- | --- |
| Package contract | SeekTalent 集成 owner |
| Runtime selection policy | 关键词图谱 owner |
| CTS count client / rate limit | CTS owner 或平台 owner |
| Snapshot schema | 数据 / 图谱 owner |
| Security / secrets | 安全 owner |
| Docs only | 任一 owner |

## 合并策略

推荐 squash merge，保持 main 历史清晰。

合并前：

- 所有 required checks 通过。
- reviewer approve。
- PR 描述完整。
- 如有 breaking change，必须有 RFC 或版本升级。
- 如影响 SeekTalent 集成，必须有 consumer contract test 更新。

## Package 发布

发布步骤：

1. 确认 main 绿色。
2. 创建 tag。
3. build wheel / sdist。
4. 跑 wheel install smoke。
5. 发布 release notes。
6. 发布 JSON schema artifact。
7. 在 SeekTalent 试接入分支做 smoke。

## Release Notes 内容

- package 版本。
- request / response schema 变化。
- snapshot schema 变化。
- selection policy 变化。
- 兼容性说明。
- 回滚方式。

## Snapshot 发布

Snapshot 不是代码发布，必须单独门禁。

流程：

1. 内部构建 candidate snapshot。
2. 跑 snapshot replay。
3. 生成 diff report。
4. 校验不含 CTS key、候选人列表、简历正文。
5. 对高风险 diff 做极少量抽样检查；无人处理时默认阻断对应高风险项。
6. 发布 snapshot artifact 和 manifest。
7. SeekTalent 配置指向新 snapshot。
8. 异常时回滚到上一 snapshot。

## RFC 机制

以下变更必须先写 RFC：

- 新增公司 / 领域 / 部门节点。
- 修改 package contract 主语义。
- CTS 探测策略大幅提高 RPS。
- 引入向量数据库 / Kafka / Kubernetes 等重大依赖。
- 保存任何候选人级别数据。
- 改变隐私边界。
- 把用户侧 runtime 改成常驻服务。

RFC 最少包含：

- 背景。
- 方案。
- 替代方案。
- 风险。
- 迁移计划。
- 回滚计划。

## 事故处理

常见事故：

- 内部 CTS probe 被限流。
- 新 snapshot 推荐异常。
- package import 或 snapshot 打开失败。
- SeekTalent consumer contract 失败。
- snapshot artifact 体积异常增大。

处理原则：

1. 先止血：暂停 probe、回滚 snapshot、降级 package。
2. 保留现场：日志、request_id、snapshot_id、manifest。
3. 复盘：写事故记录。
4. 补测试：把事故变成回归测试。

## 文档要求

所有设计变化必须落文档。聊天里的结论不算正式决策。

至少更新：

- `GOAL.md`
- `README.md`
- `01-system-design/`
- `02-engineering-implementation/`
- `contracts/` 对应 schema
- ADR，如果是架构决策
