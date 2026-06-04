# Draft Codex Goal Prompt

Use this as the starting point for the next Codex goal.

```text
请在 /Users/frankqdwang/MLE/seektalent-keyword-graph 工作。

目标：完整实现 GBrain-inspired production builder overhaul。不要做 MVP，不要做 demo，不要做占位实现。必须一次完成可发布产品路径。

重要流程边界：
- 不要新建 Superpowers spec。
- 不要新建 linked implementation plan。
- 不要更新 docs/superpowers/specs 或 docs/superpowers/plans 来冒充完成。
- 以 GOAL.md 和 04-gbrain-inspired-builder/ 作为本次目标上下文。

开始前必须阅读：
- AGENTS.md
- GOAL.md
- README.md
- 04-gbrain-inspired-builder/
- docs/readiness-report.md
- docs/query-recall-optimization.md
- 04-gbrain-inspired-builder/06-completion-criteria.md
- /Users/frankqdwang/MLE/gbrain-reference/docs/ethos/THIN_HARNESS_FAT_SKILLS.md
- /Users/frankqdwang/MLE/gbrain-reference/src/core/link-extraction.ts
- /Users/frankqdwang/MLE/gbrain-reference/src/core/by-mention.ts
- /Users/frankqdwang/MLE/gbrain-reference/src/core/extract-ner.ts
- /Users/frankqdwang/MLE/gbrain-reference/src/core/schema-pack/base/gbrain-base.yaml
- /Users/frankqdwang/MLE/gbrain-reference/src/core/schema-pack/link-inference.ts

核心要求：
- 将当前玩具式硬编码 keyword whitelist 从生产抽取路径移除或降级为测试 fixture。
- 建立 schema/config 驱动的 surface/entity taxonomy，覆盖 skill、tool、framework、language、platform、cloud service、database/storage、certificate、role/job family、domain、industry、method、business function、seniority、query modifier/precision companion。
- 建立 thin harness：CLI 只负责确定性执行，包括 import-jds、build-gazetteer、extract-mentions、infer-relations、llm-propose-candidates、review-candidates、probe-provider、build-snapshot、validate-snapshot。
- 建立 rich skills/docs：schema authoring、corpus import、surface taxonomy、relation rule authoring、LLM candidate review、provider recall probe、snapshot release。
- 支持从真实 JD corpus 和历史 query evidence 构建 clean build DB，不允许在 fixture DB 基础上伪装生产构建。
- 完成标准必须基于本机已经存在的 9000+ JD corpus。已确认路径：
  - source config: /Users/frankqdwang/MLE/jd-graph/config/sources/bytedance_jobs_2026_05_12.json
  - primary mainland JD JSONL: /Users/frankqdwang/MLE/jd-graph/data/derived/company=bytedance/source=jobs_bytedance/factual_jobs_mainland.jsonl
  - expected mainland JD count: 9530
  - canonical selected/dedup JSONL: /Users/frankqdwang/MLE/jd-graph/data/derived/company=bytedance/source=jobs_bytedance/normalized_factual_jobs_selected_dedup.jsonl
  - expected selected/dedup count: 9864
  只跑 fixture、小样本、mock 数据或合成样本不能标记目标完成。
- 每一轮新的生产构建、评估、回归验证都必须清除上一轮脏数据库，从 clean build DB 重新导入。禁止复用 dirty DB。
- 必须新增 production corpus manifest 机制，manifest 至少包含 corpus id/version、JD paths、historical query evidence paths、expected counts、source ownership、content hash policy、privacy scan policy、language/domain coverage、build mode。
- 支持 section-aware/window-aware evidence offsets/snippets。
- 支持 gazetteer/longest-match mention extraction。
- 支持 alias、abbreviation、equivalent、version variant、co-occurrence、precision companion、broader/narrower、provider recall risk、fallback/score-only relations。
- 每个 surface、relation、observation 必须有 provenance/evidence、confidence、rule/model version。
- 必须新增 graph quality eval gate，覆盖 extraction coverage、generic rejects、ambiguous/risky surfaces、merge samples、bad merge warnings、relation confidence distribution、provider observation coverage、query recall replay cases。
- 构建完成后必须使用 subagent-driven review，并且 reviewer 必须是空上下文/干净上下文 subagent。至少审查：提取关键词是否适合做简历搜索词、是否避免 hack/fixture shortcut、手写规则是否足够泛化且不是针对特定领域或特定名词。
- LLM 只能作为 offline builder 的候选生成/确认辅助，必须有 explicit config、dry-run、budget、eval、review gate。LLM candidate 必须有 source window、evidence span、model、prompt version、review/validation status；unreviewed candidate 不得进入 release snapshot。runtime 不得调用 LLM。
- Provider probing 开发阶段默认 fake 或 dry-run。但目标最终完成必须在显式人工 gate 后使用真实 CTS，对 release-candidate keyword surfaces 逐个检索并写入 total/status/recall_bucket/observed_at/provider/query_mode/provenance。最终完成证据绝对不能使用 mock/fake/dry-run/fixture CTS observation。
- Runtime 只读 bundled/local snapshot，不 import builder/cts，不读 KEYWORD_GRAPH_CTS_*，不执行网络 I/O，不 import SeekTalent。
- Package 不能 import SeekTalent，不能修改 SeekTalent 主项目。

禁止行为：
- 禁止 fixture-specific branch。
- 禁止 hardcoded examples 冒充生产抽取。
- 禁止 fixed constant output。
- 禁止 placeholder API 或空成功响应。
- 禁止假 graph edge、假 provider observation、假 readiness。
- 禁止 broad except 隐藏失败。
- 禁止只补文档就声称完成。
- 禁止无 production corpus manifest 就声称生产构建完成。
- 禁止跳过 graph quality eval gate。
- 禁止 unreviewed LLM candidate 进入 bundled snapshot。
- 禁止复用脏 build DB 继续测试或伪装 clean import。
- 禁止不经过空上下文 subagent review 就声称图谱构建正常。
- 禁止用 mock/fake/dry-run/fixture CTS observation 作为最终完成证据。
- 禁止跳过 wheel/install 后真实 bundled snapshot smoke test。

执行方式：
- 从最新 main 新建工作分支，不要直接在 main 上开发。
- 可以使用 subagent-driven-development。
- 不要创建或更新 Superpowers spec/plan；如需拆分任务，在本 goal 内维护短 checklist，必要时只更新 04-gbrain-inspired-builder/ 文档。
- 每个 slice 先写测试、跑红、实现、跑绿、再 commit。
- 所有 Python 测试、lint、build 通过 uv run 执行：
  uv run pytest
  uv run ruff check .
  uv run python -m build --wheel
- 完成前更新 docs/readiness-report.md，列出真实验证命令、数据来源、snapshot id、artifact 路径、已知风险。
- 完成实现和本地验证后可以开 PR，但必须停在 PR review 状态。
- 不要自动 merge PR，不要删除分支，不要发布 release；这些都需要明确人工确认。
```
