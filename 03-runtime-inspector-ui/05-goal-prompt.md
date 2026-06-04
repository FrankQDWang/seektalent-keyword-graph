# Draft Codex Goal Prompt

Use this as the starting point for the next Codex goal.

```text
请在 /Users/frankqdwang/MLE/seektalent-keyword-graph 工作。

目标：实现 Local Snapshot Inspector UI。

背景：
当前包已经支持 JD -> keyword graph -> provider-aware runtime snapshot -> Query Recall Optimization。下一步需要一个本地只读 UI，用于人工输入 query 词并查看 snapshot 中已有的 recall observation、相近词、关系 provenance 和推荐动作。

不要预先使用 docs/superpowers/specs 或 docs/superpowers/plans。你可以在 goal 执行中自行决定是否使用 workflow、subagent、TDD、review，但不要先创建 Superpowers spec/plan。请以仓库现有文档和 03-runtime-inspector-ui/ 目录作为目标上下文。

交付目标：
- 在当前包内提供本地 inspector UI。
- UI 使用纯静态 HTML/CSS/JS + Python 轻量 server。
- 默认监听 127.0.0.1。
- 命令接受 --snapshot 和 --manifest。
- UI 支持输入 query_text、选择 provider、选择 query_mode。
- UI 展示输入词的 provider-aware recall observation：total、status、recall_bucket、observed_at、provider、query_mode、observation_id、evidence_ref。
- UI 展示相近词/alias/equivalent/related alternatives 及其 recall observation、relation_type、confidence、source_concept_id、source_surface_id、target_surface_id、evidence/provenance。
- UI 展示 runtime recommendations：keep、replace、downrank、add_alias_probe、add_precision_companion、score_only、fallback。

边界：
- 不调用真实 CTS。
- 不调用 Liepin、Boss 或任何 live provider。
- UI 和 runtime 路径不读取 KEYWORD_GRAPH_CTS_*。
- UI 和 runtime 查询路径不 import builder/cts。
- 本包不 import SeekTalent。
- 不修改 SeekTalent 主项目。
- UI 只读 snapshot，不写 snapshot、manifest 或 gzip artifact。
- 第一版不引入 React/Vite/Streamlit/Gradio/FastAPI 等重依赖；优先 Python stdlib server。
- 不拆新包，除非你证明零重依赖方案不可行。

验收标准：
- 可以从源码和安装后的 wheel 启动 UI。
- 可以用 fixture snapshot 查询 React / Kafka / Kubernetes / LLMOps。
- React + cts 显示 zero recall，并显示 React.js alias alternative 的 healthy recall。
- Kafka + cts 显示 stale，并显示 Apache Kafka alternative。
- Kubernetes + cts 显示 too_wide，并能显示 precision companion 建议。
- LLMOps + cts 显示 unknown，并显示相关建议。
- unsupported provider、no match、matched without observation 有稳定错误/空状态展示。
- 测试覆盖 server command、static asset serving、JSON API、fixture snapshot query、runtime boundary、不读 CTS env、不调用 provider 网络。
- 运行 uv run pytest、uv run ruff check .、uv run python -m build --wheel。

行为控制：
- 开始前先读 GOAL.md、03-runtime-inspector-ui/、README.md、AGENTS.md。
- 从 main 新建分支开发。
- 每个实质 slice 先写测试、跑红、实现、跑绿、提交。
- 不要在无人值守时调用真实 CTS。
- 如果必须改变范围，先更新 03-runtime-inspector-ui/ 下的文档说明原因。
- 完成后开 PR、review，再合并。
```
