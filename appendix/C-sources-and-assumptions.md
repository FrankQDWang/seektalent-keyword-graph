# C. 资料来源与假设

## 直接上下文

- 用户说明：第一阶段只做关键词，暂不做公司、领域、组织部门。
- 用户说明：这个能力应独立成新项目，作为 SeekTalent 的依赖，不继续增加主项目复杂度。
- 用户说明：用户本地不会有 CTS key，不能实时调用 CTS 给每个词查召回数量。
- 用户说明：CTS 召回数量由我们内部预先探测，构建好图谱 / snapshot 后再发给用户。
- 用户偏好：如果本地方案能保持小体积、轻占用、跨平台，则优先本地 package；避免 Neo4j 这类用户侧重依赖。
- 用户确认：新能力作为单独 GitHub repo 和普通依赖包维护。
- 用户确认：第一版真实 CTS probe 按 1 RPS 起步。
- 用户确认：CTS 没有官方日配额；第一版不设固定 daily cap，但只在 09:00-21:00 探测，夜间暂停。
- 用户确认：9530 条中国大陆公开 JD 样本可以作为第一版语料。
- 用户确认：不做大规模人工复核，只做极少量抽样检查，人工时间每天最多 10 分钟。
- 用户确认：SeekTalent 反馈回传和 LLM 辅助抽取按保守建议执行。
- 用户确认：其余边界按保守默认执行，包括 snapshot 手动发布、两周目标节奏、`<100MB` 硬上限、CSV/JSONL 抽样、query-level 本地反馈导出。

## 已查看的本机项目事实

- 主项目在 `~/Agents/SeekTalent-0.2.4`。
- `.env` 中有真实 CTS key，但文档和测试不能泄露 key。
- SeekTalent 主项目体积大主要来自 venv、runs、apps 和本地数据，源码本身约 MB 级。
- 现有 SeekTalent SQLite 文件体积在几十 MB 级，支持第一版 SQLite snapshot 策略。
- 旧 Codex 线程确认本机有 9530 条中国大陆公开 JD 样本，可作为第一版 bootstrap corpus。

## 已验证的 CTS 行为

本机真实 smoke 已验证：

| Query | 观察 |
| --- | --- |
| `Python` | HTTP 200，`data.total=336708` |
| `Kubernetes` | HTTP 200，`data.total=29829` |
| `k8s` | HTTP 200，`data.total=58692` |
| `Python Kubernetes` | HTTP 200，`data.total=9813` |
| `"Kubernetes"` | HTTP 200，`data.total=29829` |
| `AIGC` | HTTP 200，`data.total=14013` |

结论：

- 第一版可以用 `page=1`、`pageSize=1`、读取 `data.total` 做 count-only recall observation。
- 引号查询看起来与普通关键词返回相同 total，不能先假设 CTS 支持精确短语语法。
- 关键词包 runtime 不应暴露 CTS probe 能力。

## 技术栈判断

第一版采用：

- Python 3.12+。
- Pydantic v2 contracts。
- SQLite runtime snapshot。
- SQLite build DB / JSONL staging。
- httpx 仅用于内部 CTS count client。
- pytest、ruff、typecheck、uv。
- single GitHub repo + wheel + versioned snapshot artifact。

第一版明确不采用：

- 用户侧 FastAPI / Uvicorn 常驻服务。
- 用户侧 Docker Compose。
- PostgreSQL。
- Neo4j。
- Redis。
- Celery。
- Kubernetes。
- 用户侧 CTS key。

## 关键假设

1. CTS API 的 `data.total` 可作为关键词 surface 的召回数量观察。
2. CTS API 有限流或资源压力风险，因此 probe 必须内部、低速、可暂停。
3. 第一阶段不需要保存原始简历全文。
4. SeekTalent 可以通过 Python dependency 调用关键词包。
5. SeekTalent 可以在 artifacts 中新增 query bundle、lineage 和 warning。
6. 9530 条公开 JD 样本足够启动第一版关键词图谱，但后续需要持续追加公开 JD 和真实反馈。
7. 用户更重视可复盘、稳定、小体积、跨平台和工程可落地，而不是一次性复杂大图谱。
8. 人工时间是稀缺资源，系统必须默认自动治理和保守降级。

## 未确认但会影响实现的事项

- CTS API 的错误码、分页语义、tenant 限流和查询语法。
- 后续 JD 数据来源和授权保留期。
- LLM 辅助抽取的具体模型和数据边界。
- 若未来跨机器传输 query-level 反馈，是否需要数据导出审批。
