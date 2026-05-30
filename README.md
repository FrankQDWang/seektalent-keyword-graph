# SeekTalent Keyword Graph 规划包

这个目录是一组规划文档，目标是在 SeekTalent 主仓库之外新建一个干净、轻量、跨平台的独立项目，用作 SeekTalent 的关键词图谱依赖包。

当前仓库和 Python distribution 名称：

```text
seektalent-keyword-graph
```

该能力会作为单独 GitHub repo 维护，SeekTalent 只把它当作普通依赖引入，不把实现继续塞进 SeekTalent 主仓库。

## 当前定案

第一阶段不做常驻服务，不做 UI，不要求用户本地配置 CTS key，不引入 Neo4j / PostgreSQL / Redis / Celery。

第一阶段做一个可安装的小包：

- 离线构建：我们使用内部 CTS key 对词面做低速、受控、count-only 探测，生成 SQLite snapshot。
- 本地运行：用户安装 package 和 snapshot 后，SeekTalent 调用本地函数，输入 JD / RequirementSheet / notes，输出 query bundles。
- 数据分发：同一个独立 repo 发布 Python package、压缩后的关键词图谱 snapshot、manifest 和 checksum。snapshot 不包含 CTS key，不包含原始简历正文，不要求用户实时访问 CTS。
- Snapshot 节奏：手动发布 candidate snapshot，稳定后目标两周一次；压缩后软目标 `<50MB`，硬上限 `<100MB`。
- CTS 节奏：真实 CTS count probe 第一版按 `1 RPS / 并发 1` 起步，只在 09:00-21:00 运行，夜间暂停；不设固定 daily cap。
- 人工参与：不设计大规模人工复核。第一版以自动规则、回放评估和极少量抽样检查为主，人工时间预算按每天最多 10 分钟设计。

## 范围

本包严格按第一阶段范围设计：

- 做：关键词、关键词别名、关键词共现、JD 中的关键词证据、CTS `data.total` 召回数量、关键词可搜性画像、对 SeekTalent 暴露本地 query bundle 推荐接口。
- 不做：公司图谱、行业 / 领域图谱、组织部门图谱、候选人关系图谱、完整简历语义索引、用户侧实时 CTS 探测、常驻 API 服务、后台 UI。
- 保留扩展点：后续可以增加服务化部署或更多节点类型，但第一阶段 package、snapshot schema、评估都不依赖这些扩展。

## 目录

```text
GOAL.md
README.md
01-system-design/
  00-context-scope-and-principles.md
  01-domain-model.md
  02-data-structures-and-fields.md
  03-jd-to-keyword-graph-flow.md
  04-cts-probe-and-rate-limit-design.md
  05-graph-building-and-refresh.md
  06-serving-decision-and-query-bundles.md
  07-package-contract.md
  08-seektalent-integration.md
  09-observability-evaluation-governance.md
  10-roadmap-and-risks.md
02-engineering-implementation/
  00-technology-stack.md
  01-repository-layout.md
  02-layering-and-decoupling.md
  03-storage-and-migrations.md
  04-internal-builder-and-scheduler.md
  05-package-contract-implementation.md
  06-runtime-topology-and-distribution.md
  07-testing-strategy.md
  08-ci-cd-pipeline.md
  09-pr-and-release-process.md
  10-security-privacy-and-secrets.md
  11-delivery-plan.md
appendix/
  A-open-questions.md
  B-glossary.md
  C-sources-and-assumptions.md
```

## 推荐阅读顺序

先读 `GOAL.md` 和 `01-system-design/00-context-scope-and-principles.md`，确认边界；再读 `01-system-design/04-cts-probe-and-rate-limit-design.md`，确认 CTS 只在内部离线构建时使用；最后读 `02-engineering-implementation/00-technology-stack.md` 与 `02-engineering-implementation/11-delivery-plan.md`，确认轻量 package 怎么落地。

## 核心判断

这个项目的第一性问题不是“更聪明地理解 JD”，而是“把语义正确的岗位需求稳定落到真实可搜的词面”。因此系统要把 `Concept` 和 `SurfaceForm` 分开，把 JD 语料统计和 CTS 召回统计分开，把离线 snapshot 构建和用户本地 query bundle 决策分开。
