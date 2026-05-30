# B. 术语表

| 术语 | 含义 |
| --- | --- |
| SeekTalent | 现有本地优先的 JD-简历匹配工具 |
| Keyword Graph Package | 本规划中的独立轻量 Python package |
| Runtime Package | 用户本地被 SeekTalent import 的运行时，只读 snapshot，不调用 CTS |
| Builder Tools | 我们内部运行的离线构建工具，负责 JD 导入、关键词抽取、CTS count probe、snapshot 构建 |
| CTS | 内部简历库搜索系统 |
| CTS Count Probe | 内部构建阶段用 `pageSize=1` 调 CTS 并读取 `data.total` 的 count-only 探测 |
| JD | Job Description，岗位描述 |
| Concept | 抽象关键词概念，不等于搜索词面 |
| SurfaceForm | 真实可输入搜索框的词面 |
| KeywordMention | 某个关键词在某份 JD 中的证据 |
| CTSRecallObservation | 内部 CTS count probe 得到的召回数量观察 |
| QueryBundle | 返回给 SeekTalent 的查询词组合 |
| Anchor Query | 保守稳定的查询词 |
| Precision Query | 用于收窄过宽召回的查询词 |
| Alias Probe | 用同概念别名试探召回 |
| Exploration Query | 低置信新词或长尾探索 |
| Snapshot | 一版可回放的关键词图谱 SQLite 文件 |
| Snapshot Manifest | snapshot id、schema version、build time、checksum 等发布元数据 |
| Serving Surface | 可以被 runtime 推荐的词面 |
| Recall Bucket | zero / healthy / too_wide 等召回区间标签 |
| Lineage | 一个推荐结果的选择链路 |
| Probe Job | 内部构建阶段的一个 CTS 探测任务 |
| Token Bucket | 限速算法概念，用于控制单位时间请求量 |
| Circuit Breaker | 熔断器，依赖异常时暂停调用 |
| Artifact | 可复盘产物，如请求、响应、日志、snapshot、manifest |
