# GOAL

把 SeekTalent 的“JD -> 检索词 -> 简历召回”从一次性 LLM 生成，升级为一个独立、轻量、可复盘、可评估、可持续演化的关键词图谱包。

第一阶段只做关键词，并以独立 Python package 的形式交付给 SeekTalent 作为依赖，而不是做常驻服务、UI 或重型图数据库系统。

核心产物分两层：

1. 我们离线构建并发布的 SQLite 图谱快照：从公开 JD 样本和历史查询证据中沉淀关键词、别名、共现关系，并使用内部 CTS key 离线探测每个词面的召回数量。
2. 用户本地运行的轻量查询包：接收 JD / RequirementSheet / notes，读取本地 SQLite snapshot，返回可解释的 query bundles。

用户本地不会持有 CTS key，也不会在运行 SeekTalent 时实时调用 CTS 做关键词探测。CTS 探测只发生在我们内部的 snapshot 构建与刷新流程中；发布给用户的是已经计算好的 concept-surface-recall snapshot。

长期目标不是做通用知识图谱，而是让同一份 JD 在不同时间、不同运行中都能稳定地产生可解释、不过宽、不漏召回的查询词组合。
