# GOAL

把 SeekTalent 的“JD -> 检索词 -> 简历召回”从一次性 LLM 生成，升级为一个独立、轻量、可复盘、可评估、可持续演化的关键词图谱包。

第一阶段只做关键词，并以独立 Python package 的形式交付给 SeekTalent 作为依赖，而不是做常驻服务、UI 或重型图数据库系统。

核心产物分两层：

1. 我们离线构建并发布的 SQLite 图谱快照：从公开 JD 样本和历史查询证据中沉淀关键词、别名、共现关系，并使用内部 CTS key 离线探测每个词面的召回数量。
2. 用户本地运行的轻量查询包：接收 JD / RequirementSheet / notes，或接收 SeekTalent 已生成的 query term pool，读取本地 SQLite snapshot，返回可解释的 query bundles 和 provider-aware Query Recall Optimization 建议。

用户本地不会持有 CTS key，也不会在运行 SeekTalent 时实时调用 CTS 做关键词探测。CTS 探测只发生在我们内部的 snapshot 构建与刷新流程中；发布给用户的是已经计算好的 concept-surface-recall snapshot。

长期目标不是做通用知识图谱，而是让同一份 JD 和同一组已生成检索词在不同时间、不同运行中都能稳定地产生可解释、不过宽、不漏召回的查询词组合，并在实际调用 CTS / 猎聘 / Boss 等 provider 前给出可复盘的保留、降权、替换、alias probe、precision companion、score-only 或 fallback 建议。

## Next Goal: Local Snapshot Inspector UI

下一个目标是在当前包内增加一个本地只读的 snapshot inspector UI，用于人工查看和验证 runtime snapshot 中的关键词召回画像。

这个目标不是新建 Superpowers spec/plan，也不是重做图谱构建流程。它应该作为 Codex goal 执行：Codex 在 goal 内自行决定是否使用工作流、如何拆分任务、如何测试和 review；仓库文档只提供清晰的交付目标、验收标准、边界和行为控制。

UI 的第一版范围很固定：

- 启动本地轻量 server，只监听 `127.0.0.1`。
- 使用当前包内能力读取本地 `keyword-graph.sqlite3` 和 `snapshot-manifest.json`。
- 提供纯静态 HTML/CSS/JS 页面，不引入 React、Vite、Streamlit、Gradio 或重型前端依赖。
- 支持手工输入一个 query 词，选择 provider 和 query mode。
- 返回输入词在 snapshot 中的 provider-aware recall observation，包括 `total`、`status`、`recall_bucket`、`observed_at`、`provider`、`query_mode`、`observation_id` 和 evidence/provenance。
- 返回图谱中相近的 alias / equivalent / normalized / related surfaces，并展示每个候选词自己的 recall observation、关系类型、confidence、source/target surface id、concept id 和 evidence。
- 展示 runtime 给出的建议动作，例如 keep、replace、downrank、add_alias_probe、add_precision_companion、score_only 或 fallback。

边界保持不变：

- UI 只读 snapshot，不写 snapshot。
- UI 不调用真实 CTS、猎聘、Boss 或任何 live provider。
- UI 不读取 `KEYWORD_GRAPH_CTS_*`。
- runtime 仍不得 import builder/CTS。
- 本包仍不得 import SeekTalent。
- 第一版不拆 shim/full 两个包；只要保持零重依赖和 lazy import，UI 可以随当前包一起发布。

配套说明放在 `03-runtime-inspector-ui/`。该目录是下一次 Codex goal 的目标上下文，不是逐 slice 实施计划。
