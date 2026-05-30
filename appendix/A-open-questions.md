# A. 待确认问题

以下问题不会阻塞第一版 package + snapshot MVP，但会影响发布节奏、质量门禁和后续扩展。

## 已定案

- 新能力做成单独 GitHub repo：`seektalent-keyword-graph`。
- SeekTalent 通过普通 Python dependency 使用它，不把实现塞进 SeekTalent 主仓库。
- Snapshot 作为同 repo 的 versioned release artifact 发布，仓库只提交小型测试 snapshot。
- 第一版真实 CTS probe 按 `1 RPS / 并发 1` 起步。
- CTS probe 不设固定 daily cap，但只在 09:00-21:00 运行，夜间暂停；按 1 RPS 约 43200 次 / 天。
- 9530 条中国大陆公开 JD 样本作为第一版 bootstrap corpus。
- 不做大规模人工复核；只做极少量抽样检查，人工时间预算每天最多 10 分钟。
- SeekTalent 反馈先手动导出 query-level 聚合，不上传候选人级数据。
- LLM 辅助抽取只处理难例或抽样，不直接进入 serving。
- Snapshot 手动发布 candidate，稳定后目标两周一次；压缩后目标 `<50MB`，硬上限 `<100MB`。
- 抽样结果用 CSV 给人看、JSONL 给系统回填，不做 UI。
- query-level 反馈只生成本地导出文件，不自动上传；不含候选人级数据时不作为额外审批流程设计。

## Snapshot 分发

仍待确认：

1. SeekTalent 默认使用 bundled snapshot，还是要求用户显式配置路径？
2. 是否需要同时保留多个 snapshot 供回滚？

## CTS API

已确认：当前 CTS 接口可以用 `page=1`、`pageSize=1`，读取 `data.total` 做 count-only 观察；用户侧不持有 CTS key，也不实时 probe。

仍待确认：

1. `data.total` 是否精确，还是近似？
2. 是否按 tenant 限流？
3. 429 / 5xx / timeout 的错误码和响应格式是什么？
4. 是否有 staging / sandbox 环境？
5. 是否允许保存脱敏 result sample？默认设计是不保存。

## JD 语料

已确认：本机已有 9530 条中国大陆公开 JD 样本，可作为第一版 bootstrap corpus。

仍待确认：

1. 后续追加 JD 的来源和授权边界是什么？
2. 是否要保留岗位标题、发布时间、来源站点等元数据进入 build DB？
3. JD 原文的保留期限是什么？
4. LLM 辅助抽取使用哪个模型和数据边界？第一版只做难例或抽样。

## 抽样检查

1. 每天 10 分钟抽样检查希望看多少条？建议 10-20 条。
2. 哪些风险项必须默认阻断，而不是等待人工确认？

## SeekTalent 集成

1. 最合适的调用点是否就是 `RequirementSheet` 之后？
2. `RequirementSheet` 当前字段是否足够表达 required / preferred？
3. 现有 `term_surface_audit.json` 能否扩展，还是新增 artifact？
4. Query bundle 如何映射到当前 retrieval planning？
5. Package 不可用时默认 fail-open 的具体 artifact 表达是什么？

## 安全与反馈闭环

1. CTS 凭证由哪个内部 secret manager 或本地构建环境管理？
2. 内部 CTS observation 明细保留多久？
3. 若未来需要把 query-level 聚合反馈上传或跨机器传输，是否有数据导出审批流程？
