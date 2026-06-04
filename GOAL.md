# GOAL

把 SeekTalent 的“JD -> 检索词 -> 简历召回”从一次性 LLM 生成，升级为一个独立、轻量、可复盘、可评估、可持续演化的关键词图谱包。

第一阶段只做关键词，并以独立 Python package 的形式交付给 SeekTalent 作为依赖，而不是做常驻服务、面向最终用户的产品 UI 或重型图数据库系统。Local Snapshot Inspector UI 是本地只读的开发/验证工具，不改变包的轻量 runtime 形态。

核心产物分两层：

1. 我们离线构建并发布的 SQLite 图谱快照：从公开 JD 样本和历史查询证据中沉淀关键词、别名、共现关系，并使用内部 CTS key 离线探测每个词面的召回数量。
2. 用户本地运行的轻量查询包：接收 JD / RequirementSheet / notes，或接收 SeekTalent 已生成的 query term pool，读取本地 SQLite snapshot，返回可解释的 query bundles 和 provider-aware Query Recall Optimization 建议。

用户本地不会持有 CTS key，也不会在运行 SeekTalent 时实时调用 CTS 做关键词探测。CTS 探测只发生在我们内部的 snapshot 构建与刷新流程中；发布给用户的是已经计算好的 concept-surface-recall snapshot。

长期目标不是做通用知识图谱，而是让同一份 JD 和同一组已生成检索词在不同时间、不同运行中都能稳定地产生可解释、不过宽、不漏召回的查询词组合，并在实际调用 CTS / 猎聘 / Boss 等 provider 前给出可复盘的保留、降权、替换、alias probe、precision companion、score-only 或 fallback 建议。

## Previous Goal: Local Snapshot Inspector UI

最近一个目标是在当前包内增加一个本地只读的 snapshot inspector UI，用于人工查看和验证 runtime snapshot 中的关键词召回画像。

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

配套说明放在 `03-runtime-inspector-ui/`。该目录是 Local Snapshot Inspector UI 的目标上下文，不是逐 slice 实施计划。

## Next Goal: GBrain-Inspired Production Builder Overhaul

下一个目标是基于 GBrain 调研结果，完整重构离线 keyword graph builder，使它能够从真实 JD corpus、历史 query evidence、审阅后的 taxonomy/provider evidence 中构建生产可用的 graph snapshot，而不是继续依赖少量手写技术词或 fixture 行为。

这个目标必须采用 GBrain 的核心工程思想，但不能盲目复制 GBrain 代码：

- thin harness：本项目 builder 的 CLI 和命令执行器只做确定性执行、持久化、校验、导出；
- rich skills/schema/configs：本项目 builder 运行时使用的实体类型、关系规则、LLM 辅助流程、review 质量标准和 release gate 由版本化文档、schema、规则配置和 eval fixtures 承载；它们不是 Codex 开发技能；
- gazetteer/by-mention：从真实 surface inventory 和 corpus evidence 中做 longest-match mention extraction；
- sliding/context window：每个 alias、abbreviation、equivalent、co-occurrence、precision companion 等关系都必须有局部窗口证据；
- LLM 只作为本项目 offline builder 的候选生成和确认辅助，通过 builder-only OpenAI-compatible provider 配置调用；第一目标 provider 是阿里云百炼，必须有 dry-run、预算、eval、review gate；
- runtime 继续只读本地 bundled snapshot，不联网、不调 CTS、不调 LLM、不 import builder/cts、不 import SeekTalent。

这是完整产品目标，不是 MVP、demo、占位实现或只补文档。后续 goal 必须明确禁止以下偷懒行为：

- 用 fixture-specific branch 伪装生产行为；
- 用固定常量输出满足 contract；
- 用硬编码示例词表冒充真实抽取；
- 写 placeholder API 或空成功响应；
- 生成没有 evidence/provenance 的 graph edge；
- 生成没有真实来源标识的 provider observation；
- broad `except` 吞掉构建失败；
- 跳过 wheel/install 后 bundled snapshot smoke test；
- 只更新 README/readiness 就声称完成。

配套说明放在 `04-gbrain-inspired-builder/`。该目录是后续 Codex goal 的目标上下文，明确记录 GBrain 参考文件、产品范围、硬边界、禁止事项和可直接使用的 goal prompt。

该目标的完成标准必须使用 `04-gbrain-inspired-builder/06-completion-criteria.md`、`04-gbrain-inspired-builder/07-quality-gate-schema.md` 和 `04-gbrain-inspired-builder/08-execution-contract.md`：

- 必须从本机已经存在的 9000+ JD corpus 通过 production corpus manifest 导入；
- 已确认的本机 bootstrap corpus 是 `/Users/frankqdwang/MLE/jd-graph/data/derived/company=bytedance/source=jobs_bytedance/factual_jobs_mainland.jsonl`，9530 行；源配置是 `/Users/frankqdwang/MLE/jd-graph/config/sources/bytedance_jobs_2026_05_12.json`；
- 每次新的生产构建、评估或回归验证都必须从 clean build DB 重新导入，不能复用脏数据库；
- 图谱构建完成后必须使用空上下文 subagent-driven review 审查关键词是否适合作为简历搜索词、是否避免 hack/fixture shortcut、手写规则是否足够泛化；
- 如果图谱被确认可用，最终完成还必须在显式人工 gate 后使用真实 CTS 对 release-candidate keyword surfaces 做逐词检索并写入召回数量、状态、bucket、时间和 provenance；
- mock、fake、dry-run、fixture CTS observation 不能作为最终完成证据。
- `docs/superpowers/` 已删除且不得恢复；旧上下文承接关系以 `04-gbrain-inspired-builder/09-supersession-map.md` 为准。
