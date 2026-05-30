# 00. 背景、范围与设计原则

## 背景

SeekTalent 当前已经有 JD 输入、需求抽取、CTS 检索、简历评分、反思与最终输出等主流程。这个新项目不替代 SeekTalent，也不继续塞进 SeekTalent 主仓库，而是作为一个独立轻量 package，专门负责：

1. 从公开 JD 样本和历史查询证据中发现、归并关键词。
2. 在我们内部环境中使用 CTS API 离线探测关键词 surface 的召回数量。
3. 把关键词、别名、共现、召回分布沉淀为一个可分发的 SQLite snapshot。
4. 在用户本地为一份 JD 返回稳定、可解释、可回放的 query bundles。

## 第一阶段边界

第一阶段只做关键词，不做公司、领域、组织部门，不做常驻服务。

| 项目 | 第一阶段处理方式 |
| --- | --- |
| 技能词、工具词、框架词、证书词、岗位关键词 | 作为核心对象建模 |
| 关键词别名、中英混写、缩写、俗称 | 作为 `SurfaceForm` 建模 |
| JD 中的关键词出现位置、频率、必选 / 加分属性 | 作为证据与统计建模 |
| CTS 搜索 API 返回的 `data.total` | 由我们内部离线探测后写入 snapshot |
| 用户本地 CTS key | 不需要，不分发，不读取 |
| 用户本地 CTS 探测 | 不做；本地 runtime 只读 snapshot |
| 公司 | 不建节点，不参与推荐，仅可作为原始 JD 元数据保存 |
| 领域 / 行业 | 不建节点，不参与推荐 |
| 组织部门 | 不建节点，不参与推荐 |
| 原始简历全文 | 不入图、不落库；snapshot 只保存聚合召回统计 |

## 核心原则

### 1. Package 优先，不做服务优先

第一阶段交付一个独立 Python package 和 SQLite snapshot。SeekTalent 把它作为依赖调用本地函数，不通过 HTTP 服务调用，不需要 Docker，不需要用户部署数据库。

### 2. Concept 与 Surface 分离

`Concept` 表示抽象关键词概念，例如“推荐系统工程”“Kubernetes”“AIGC 产品经理”。`SurfaceForm` 表示真实搜索框里要输入的词面，例如 `k8s`、`Kubernetes`、`容器编排`、`推荐算法`、`召回排序`。

这是整个系统最重要的分离。LLM 或规则从 JD 里抽到的词，不等于候选人简历里真实写的词，也不等于 CTS 搜索框里最稳定的词。

### 3. 语义判断和可搜性判断分离

一个词语义上正确，不代表它能召回足够简历；一个词召回多，也不代表它精确。系统必须同时保存：

- JD 侧出现频率。
- CTS 侧简历召回数量。
- 词面别名关系。
- 和其他关键词的共现强度。
- 被 SeekTalent 使用后的真实效果。

### 4. 内部离线构建，用户本地只读

公开 JD 处理、关键词归并、CTS 探测、snapshot 构建都发生在我们自己的构建环境。用户本地只拿到已经构建好的 SQLite snapshot，并在 SeekTalent runtime 中做低延迟本地查询、打分、解释和 query bundle 返回。

这条边界是硬要求：用户本地不会持有 CTS key，也不会实时调用 CTS 来给词面查召回数量。

### 5. 可回放优先

每次返回给 SeekTalent 的结果必须带上：

- `kg_snapshot_id`
- `request_id`
- 输入摘要 hash
- 选中的关键词和拒绝的关键词
- 每个关键词的选择原因
- 使用的 CTS 召回观测时间

这样才能复盘“为什么当时搜了这些词”。

### 6. 对 CTS API 温和

CTS 是内部关键资源。所有 CTS 探测只能在内部构建流程中发生，默认 `pageSize=1`，只读取 `data.total`、状态、延迟和观测时间，不保存 candidate 列表，不保存简历正文。

构建流程必须支持限速、去重、缓存、退避和可暂停。用户侧 runtime 不接触 CTS。

### 7. SeekTalent 可降级

关键词 package 或 snapshot 不可用时，SeekTalent 不应中断。它应退回原有本地关键词策略，并在 artifacts 中记录 `keyword_graph_unavailable`。

## 非目标

第一阶段明确不做：

- 通用 GraphRAG。
- 全量简历向量检索。
- 公司 / 部门 / 行业实体清洗。
- 候选人画像图谱。
- 常驻 API 服务。
- 后台管理 UI。
- Docker / Kubernetes 部署。
- 用户侧 CTS key 配置。
- 用户侧实时 CTS 探测。
- 自动替代顾问最终判断。
- 对外招聘平台自动化作为上线主依赖。

## 成功标准

第一阶段验收不是“图谱有多大”，而是：

1. 同一 JD、同一 snapshot、同一配置，多次运行产生相同 query bundle。
2. 低召回词能被替换或扩展为 snapshot 中已知的更可搜别名。
3. 过宽关键词能被识别并给出收窄组合。
4. SeekTalent 的 artifacts 可以记录关键词 package 的选择链路。
5. 用户本地无需 CTS key，无需数据库服务，无需常驻进程。
6. SQLite snapshot 可以重新构建、版本化、校验和回滚。
