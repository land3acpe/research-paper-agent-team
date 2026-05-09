# Research Paper Agent Team — 落地设计规格

> **状态**：待审 · 2026-05-10 · 基于 `research_paper_agent_team_architecture.md` 与用户决策反馈整合
> **路径**：`D:\projects\agents\research-paper-agent-team`
> **本文档定位**：架构层 single source of truth。后续 `docs/architecture.md`、`docs/runtime_agents.md`、`docs/development_workflow.md`、`docs/adr/*` 均从本文档拆分。

---

## 0. TL;DR

构建一个 **面向特定科研方向（首版：DTP-PMSM 谐波抑制）的论文查新与管理 Agent Team**：

- **形态**：定时工作流 + 多源论文检索 + 局部 LLM 决策 + Zotero/飞书工具集成。
- **架构**：纯 Python Orchestrator + 确定性 pipeline + 局部 LLM Runtime Agents（Screening + Digest）+ SQLite + JSON/Markdown 中间产物。
- **MVP 节奏**：MVP1→MVP5 严格顺序，每阶段有验收闸门。
- **核心原则**：`代码负责稳定性，Agent 负责研究判断`。

---

## 1. 关键概念区分（**必读**）

本项目内有两层 Agent，**必须严格分离**，文档/目录/代码不得混用。

### 1.1 Development Agent Team

用户使用 Claude Code / AI 工具辅助开发本项目时的开发协作团队：

```text
architect / coder / reviewer / tester / researcher / scribe / debug / explore
```

属性：
- **不属于运行时架构**
- 不进入 `src/` 业务代码
- 不由 Python Orchestrator 调用
- 不参与论文查新/筛选/入库/通知流程
- 仅记录在 `.claude/agents/` 与 `docs/development_workflow.md`

> **特别提示**：implementation plan 中出现的 "Development Agent Team DAG"（big-pickle 调度 / coder / reviewer / scribe / researcher / explore / debug 之间的任务依赖图）**仅用于 Claude Code 开发协作规划**——它不属于项目 runtime，不写入 `src/`，不作为 Python Orchestrator 的运行时模块，也不影响 runtime pipeline 的任何执行行为。

### 1.2 Runtime Agents

项目业务模块中由 Orchestrator 调用的 LLM 语义模块。MVP4 之前只保留两个：

```text
Screening Agent  → 相关性/评分/优先级/标签/筛选理由
Digest Agent     → 周期总结/单篇摘要/标签聚合/趋势/推荐阅读顺序
```

属性：
- 业务代码位于 `src/agents/`
- **只做语义判断**，不负责流程正确性
- 不直接操作 Zotero、不直接发飞书、不修改 paper metadata
- 输出必须经过 schema 校验

### 1.3 字段写权限矩阵

| 字段 | 数据源/normalizer 写 | Runtime Agent 写 |
|---|:---:|:---:|
| title / authors / venue / doi / published_date / abstract / url / source_id | ✅ | ❌ |
| decision / priority / score / reason / tags / collection_suggestion | ❌ | ✅ |
| summary / research_relation / new_tag_suggestions | ❌ | ✅ |
| zotero_item_key / status / imported_at | Zotero Writer 写 | ❌ |

---

## 2. 设计原则

| # | 原则 | 落地约束 |
|---|---|---|
| P1 | Workflow 优先，Agent 局部决策 | 流程稳定性由确定性 Python 模块负责 |
| P2 | 增量查新 + 重叠时间窗口 | daily=3d / weekly=14d / monthly=45d |
| P3 | 入库幂等 | 硬 ID 自动合并；软匹配进入人工确认队列 |
| P4 | 标签受控 | Agent 只能从 `allowed_tags` 选；新标签进入 `new_tag_suggestions` |
| P5 | metadata-first，不主动抓全文 | OA PDF 才入库附件，付费墙不绕过 |
| P6 | 全程可追踪 | 每次运行生成 run_id，记录所有计数与日志 |
| P7 | 写操作两阶段 | Zotero Import State Machine；飞书通知 idempotency_key |
| P8 | 写操作支持 dry-run | 所有 CLI 命令都有 `--dry-run` |
| P9 | Agent 不修改 metadata | 严格遵守 §1.3 写权限矩阵 |
| P10 | 单测不打真实 API | mock fixture 强制；真实 API 测试用 `--live-api` 或 `pytest -m live_api` |

---

## 3. 运行时架构

### 3.1 总体流程

```text
Scheduler: cron / APScheduler / manual CLI
        ↓
Python Orchestrator
        ↓
Source Fetchers
   ├─ Crossref                           [MVP1]
   ├─ arXiv                              [MVP1]
   ├─ Semantic Scholar enrichment        [MVP2+，仅做摘要/引用补充，不进 MVP1 主链路]
   ├─ RSS                                [MVP4+ 评估]
   └─ IEEE Xplore                        [MVP4+ 评估]
        ↓
Normalizer
        ↓
Deduplicator
   ├─ hard dedupe: DOI / arXiv ID / source_id     → 自动合并
   └─ soft dedupe: title hash / fuzzy / title+author+year → 进入 dedup_candidates 队列
        ↓
Rule Filter  ─→ filter_decisions 表（每条 reject 都记录原因）
        ↓
[LLM] Screening Agent  (batch_size=5，单篇失败降级)
        ↓
Quality Gate
        ↓
Zotero Import State Machine
   accepted → pending_zotero → importing_zotero → imported_zotero / zotero_failed
        ↓
[LLM] Digest Agent
        ↓
Report Writer:  Markdown + JSON
        ↓
Feishu Webhook Notifier  ─→ idempotency_key {run_id}:feishu:summary
        ↓
SQLite + data/raw + data/reports + data/logs
```

### 3.2 模块职责

| 模块 | 类型 | 职责 |
|---|---|---|
| Scheduler | 确定性 | cron / APScheduler / 手动触发 |
| Orchestrator | 确定性 | 编排执行顺序、状态转换、异常处理 |
| Fetchers | 确定性 | 多源 API/RSS 调用，输出 raw + PaperCandidate |
| Normalizer | 确定性 | 字段统一、title 标准化、hash 生成 |
| Deduplicator | 确定性 | 硬去重自动合并；软去重写 dedup_candidates |
| Rule Filter | 确定性 | 黑名单/必含词/年份/语言初筛，写 filter_decisions |
| **Screening Agent** | **Runtime LLM** | **§1.2** |
| Quality Gate | 确定性 | 根据 Agent 输出 + 规则做 accept/reject/uncertain |
| Zotero Writer | 确定性 | pyzotero 调用，State Machine 管理状态 |
| **Digest Agent** | **Runtime LLM** | **§1.2** |
| Report Writer | 确定性 | Jinja2 渲染 Markdown + JSON |
| Feishu Notifier | 确定性 | webhook，幂等通知 |
| State Store | 确定性 | SQLite。MVP1 表：papers / runs / filter_decisions / dedup_candidates。MVP2 加：screening_results / llm_calls。MVP3 加：zotero_items + papers.zotero_state/zotero_last_error。MVP4 加：notifications。**source_watermarks 推迟到 MVP1.5 或 MVP2 引入**——MVP1 的时间窗口由 schedule.yaml 显式配置或 CLI 参数指定 |

---

## 4. 10 项关键补强

| # | 项 | 实现要点 | 落地阶段 |
|---|---|---|---|
| 1 | LLMClient 抽象 | OpenAI 兼容协议为主；provider/model 由 config 注入；不在 Agent 代码硬编码 | MVP2 |
| 2 | CLI 全局参数 | `--config-dir / --dry-run / --run-id / --log-level / --profile` 全命令共享 | MVP1 起 |
| 3 | Run ID 规则 | `{profile_slug}-{schedule_mode}-{YYYYMMDD-HHMMSS}-{shortuuid8}` | MVP1 |
| 4 | 去重置信度分级 | 硬去重自动合并；软匹配写 `dedup_candidates`，CLI 子命令复核 | MVP1 |
| 5 | filter_decisions 表 | 字段：run_id / paper_id / decision / reason_code / reason_text / created_at | MVP1 |
| 6 | Screening 批量 | batch_size=5；JSON 解析失败自动降级为单篇；单篇失败标 uncertain 不影响整批 | MVP2 |
| 7 | llm_calls 表 | run_id / agent_name / provider / model / input_tokens / output_tokens / total_tokens / estimated_cost / latency_ms / status / error / created_at | MVP2 |
| 8 | Zotero Import State Machine | 状态：accepted / pending_zotero / importing_zotero / imported_zotero / zotero_failed；启动时扫描非终态自动重试 | MVP3 |
| 9 | 飞书通知幂等 | `idempotency_key = {run_id}:feishu:summary`；`--force` 才能重发；retry_attempt 字段 | MVP4 |
| 10 | 测试 fixture 边界 | 所有 fetcher 单测 mock；CI 不调真实 API；`pytest -m live_api` 才打活 API | MVP1 起 |

---

## 5. CLI 契约

### 5.1 全局参数

```text
--config-dir <path>     # 默认 ./configs/
--profile <name>        # 默认 default，对应 configs/profiles/{name}/
--run-id <id>           # 子命令复用既有 run_id
--dry-run               # 不写 Zotero / 不发飞书 / 不改 SQLite 关键字段
--log-level <level>     # debug/info/warn/error
```

### 5.2 子命令矩阵

| 命令 | MVP | 作用 |
|---|---|---|
| `db-init` | MVP1 | 初始化 SQLite schema |
| `discover` | MVP1 | 仅查新（fetchers + normalize + dedupe + rule_filter），默认写 SQLite + raw + normalized + report；`--dry-run` 时仅生成临时报告，不写 SQLite |
| `run` | MVP1+ | 端到端执行（依据当前 MVP 能力，详见下方）。MVP1 等价 `discover`；`--dry-run` 同样不持久化 SQLite |
| `report` | MVP1 | 重新生成报告 |
| `screen` | MVP2 | 仅 Screening Agent |
| `import-zotero` | MVP3 | 仅 Zotero 写入。**默认只处理 status='pending_zotero'（已人工批准）的 items**；`--include-accepted` 才处理 accepted 但未批准的；`--auto-import-A-only` 才允许 priority=A 自动批准；启动时扫描非终态自动重试 |
| `digest` | MVP4 | 仅生成 digest |
| `notify` | MVP4 | 仅发飞书；`--force` 覆盖幂等 |
| `approve` | MVP5 | uncertain 队列复核（CLI/飞书交互）|

### 5.3 `run` 命令的渐进语义

| 阶段 | `run` 实际执行的链路 |
|---|---|
| MVP1 | discover → normalize → dedupe → rule_filter → report（无 LLM、无 Zotero、无飞书） |
| MVP2 | + screening_agent |
| MVP3 | + zotero_writer（默认 manual_approval；`import-zotero` 默认只处理 pending_zotero；dry-run 时跳过写入） |
| MVP4 | + digest_agent → notify |
| MVP5 | + approve（uncertain 队列） |

### 5.4 `--dry-run` 统一语义

所有支持 `--dry-run` 的命令必须遵循同一行为契约：

**禁止**：
- 写入或修改 SQLite 任何业务表（papers / screening_results / zotero_items / notifications 等）
- 调用 Zotero API 写操作（create/update/delete）
- 发送飞书消息

**允许**：
- 调用只读外部 API（fetcher 拉数据、Zotero 查询）
- 生成临时报告到 `data/reports/_dryrun/{run_id}/`
- 写日志到 `data/logs/_dryrun/{run_id}.log`
- stdout 预览（候选 paper 表、计划写入项、计划通知内容）
- 调用 LLM Runtime Agent（MVP2+，但 `llm_calls` 表也走临时路径，不污染主表）

**输出标识**：dry-run 产生的所有文件路径以 `_dryrun/` 前缀区分；run summary 中明示 `dry_run: true`。

---

## 6. 数据库 Schema 增量

在原文档 §7 基础上增加 4 张表（MVP 渐进引入）：

### 6.1 filter_decisions（MVP1）

```sql
CREATE TABLE filter_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    paper_id INTEGER,
    decision TEXT NOT NULL,           -- pass / reject
    reason_code TEXT,                 -- e.g. "missing_abstract", "year_too_old", "blacklist_keyword"
    reason_text TEXT,
    created_at TEXT
);
```

### 6.2 dedup_candidates（MVP1）

```sql
CREATE TABLE dedup_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id_a INTEGER NOT NULL,
    paper_id_b INTEGER NOT NULL,
    match_type TEXT,                  -- title_hash / fuzzy_title / title_author_year
    similarity REAL,
    status TEXT,                      -- pending / merged / rejected
    resolved_by TEXT,
    resolved_at TEXT,
    created_at TEXT
);
```

### 6.3 llm_calls（MVP2）

```sql
CREATE TABLE llm_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,         -- screening / digest
    provider TEXT,
    model TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER,
    estimated_cost REAL,
    latency_ms INTEGER,
    status TEXT,                      -- ok / parse_failed / api_error
    error TEXT,
    created_at TEXT
);
```

### 6.4 notifications（MVP4）

```sql
CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    channel TEXT NOT NULL,            -- feishu / email / ...
    idempotency_key TEXT NOT NULL,    -- 应用层而非 DB 层强制幂等；--force 时允许同 key 多行
    retry_attempt INTEGER DEFAULT 0,
    status TEXT,                      -- pending / sent / failed
    payload TEXT,
    error TEXT,
    sent_at TEXT,
    created_at TEXT
);
CREATE INDEX idx_notifications_idempotency ON notifications(idempotency_key, status);
```

幂等执行规则（应用层）：插入前先查 `idempotency_key` 是否已有 `status='sent'` 行；若有且未传 `--force` 则跳过。`--force` 时新插入一行并 `retry_attempt = 上次 + 1`。

papers 表新增字段（MVP3 引入）：

```sql
ALTER TABLE papers ADD COLUMN zotero_state TEXT;
-- accepted / pending_zotero / importing_zotero / imported_zotero / zotero_failed
ALTER TABLE papers ADD COLUMN zotero_last_error TEXT;
```

---

## 7. Runtime Agents 详细设计

### 7.1 Screening Agent

- **职责**：相关性判断 / 评分 / 优先级 / 受控标签 / 筛选理由
- **不做**：摘要生成、研究趋势分析（属于 Digest Agent）
- **批量**：默认 batch_size=5，输出 JSON array；解析失败时降级单篇
- **输出**：见原文档 §5.2 输出字段（decision/priority/score/topic_relevance/method_relevance/venue_quality/novelty_potential/tags/collection/reason/evidence/manual_review_required/fulltext_required/new_tag_suggestions）
- **评分上限**：score 合法范围 0–20；四个 sub-score 各 0–5
- **prompt 文件**：`prompts/screening_agent.md`，版本化

### 7.2 Digest Agent

- **职责**：周期入库论文摘要 / 标签聚合 / 趋势 / 推荐阅读顺序 / 与当前课题关系
- **不做**：单篇相关性判断（属于 Screening Agent）
- **输入**：本轮 imported papers + screening_results
- **输出**：Markdown 文档，含 §12 列出的 10 个 section
- **prompt 文件**：`prompts/digest_agent.md`，版本化

---

## 8. 配置文件结构

```text
configs/
├── schedule.yaml         # 定时与限额
├── sources.yaml          # 数据源 API key、查询、max_results
├── tag_schema.yaml       # allowed_tags
├── zotero.yaml           # collection_root / import_policy / duplicate_policy
├── feishu.yaml           # webhook_env / message_style
├── llm.yaml              # provider 配置（OpenAI 兼容协议）
└── profiles/
    └── dtp-pmsm/
        └── research_profile.yaml
```

LLM 配置示例：

```yaml
llm:
  default_provider: deepseek
  providers:
    deepseek:
      base_url: "https://api.deepseek.com"
      api_key_env: "DEEPSEEK_API_KEY"
      models:
        screening: "deepseek-v4-pro"
        digest: "deepseek-v4-pro"
    qwen:
      base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
      api_key_env: "DASHSCOPE_API_KEY"
      models:
        screening: "qwen3.5-plus"
```

---

## 9. 项目目录结构

```text
research-paper-agent-team/
├── .claude/
│   └── agents/                    # Development Agent Team 配置（如需要）
├── README.md
├── pyproject.toml                 # uv 管理
├── .env.example
├── .gitignore
├── configs/
│   ├── schedule.yaml
│   ├── sources.yaml
│   ├── tag_schema.yaml
│   ├── zotero.yaml
│   ├── feishu.yaml
│   ├── llm.yaml
│   └── profiles/dtp-pmsm/research_profile.yaml
├── prompts/
│   ├── screening_agent.md
│   └── digest_agent.md
├── src/
│   ├── main.py                    # CLI 入口（typer 或 click）
│   ├── orchestrator.py
│   ├── scheduler.py
│   ├── config.py
│   ├── logging_config.py
│   ├── models/                    # Pydantic
│   ├── fetchers/                  # base/crossref/arxiv/rss/semantic_scholar/ieee
│   ├── normalize/
│   ├── dedupe/
│   ├── filter/
│   ├── agents/                    # Runtime Agents：llm_client / screening / digest
│   ├── zotero/                    # client / writer / mapper / state_machine
│   ├── reports/                   # digest_writer / templates
│   ├── feishu/                    # notifier / card_builder
│   ├── storage/                   # db / migrations / repositories
│   └── utils/                     # time / hashing / retry / runid
├── data/                          # gitignored
│   ├── papers.db
│   ├── raw/{run_id}/
│   ├── normalized/{run_id}/
│   ├── reports/{run_id}/
│   └── logs/
├── tests/
│   ├── fixtures/                  # mock JSON 响应
│   ├── unit/
│   └── live/                      # pytest -m live_api
└── docs/
    ├── architecture.md            # 仅运行时
    ├── runtime_agents.md          # 仅 Screening + Digest
    ├── development_workflow.md    # 仅 Dev Agent Team
    ├── configuration.md
    ├── superpowers/
    │   ├── specs/                 # 本文档所在
    │   └── plans/                 # writing-plans 输出
    └── adr/
        ├── ADR-001-orchestrator-choice.md
        ├── ADR-002-agent-boundary.md
        └── ADR-003-zotero-import-state-machine.md
```

---

## 10. MVP 路线图

### MVP1 — 查新 + 去重 + Markdown 报告（**首期实现**）

**实现**：
- 项目骨架（pyproject.toml / `.env.example` / configs / .gitignore）
- 基础日志 + Run ID 生成器
- Pydantic 模型（PaperCandidate / RunSummary / SourceResult / DedupCandidate）
- **Crossref Fetcher + arXiv Fetcher（仅这两个）**
- Normalizer（title 标准化、hash）
- Deduplicator（硬去重 + 软匹配队列）
- Rule Filter + filter_decisions 表
- SQLite schema（papers / runs / filter_decisions / dedup_candidates）+ Repository 层
- Markdown / JSON Report Writer
- CLI 命令：`db-init / discover / run / report`，全部支持 `--dry-run`（按 §5.4 契约）
- mock fixtures + 单测覆盖核心模块

**不实现**：
- LLM Screening、Zotero、飞书、LangGraph、MCP
- Semantic Scholar enrichment、IEEE Xplore、RSS（推迟到 MVP2+ / MVP4+）
- source_watermarks 表（推迟到 MVP1.5 或 MVP2；MVP1 时间窗口由 schedule.yaml 或 CLI 显式指定）

**验收闸门**：
1. `discover`/`run` 重复运行同一篇论文不重复入 SQLite
2. 候选报告含 title/authors/venue/date/doi/abstract/url
3. Crossref 失败时 arXiv 仍能完成，run.status = partial
4. `pytest` 全绿，CI 不调真实 API
5. `--dry-run` 完全不写业务库、不发外部副作用，仅产出 `data/reports/_dryrun/` 与 `data/logs/_dryrun/`

### MVP2 — Screening Agent

- LLMClient 抽象（OpenAI 兼容）
- Screening Agent + prompt
- batch_size=5；解析失败降级
- screening_results + llm_calls 表
- CLI：`screen`
- 抽查 50 篇人工评估准确率

### MVP3 — Zotero 入库

- pyzotero client + mapper
- Zotero Import State Machine
- 默认 manual_approval；`--auto-import-A-only` 可选
- 启动时扫描非终态自动重试
- CLI：`import-zotero`

### MVP4 — Digest + 飞书

- Digest Agent + prompt
- Markdown digest（10 sections）
- Feishu webhook（不用 lark-cli）
- 通知幂等 + `--force` 覆盖
- CLI：`digest / notify`

### MVP5 — 人工审批与交互

- uncertain 队列 + dedup_candidates 复核 CLI/飞书
- 回滚/删除自动入库条目
- 多 profile / MCP 化等

---

## 11. ADR 摘要

### ADR-001：Orchestrator 选型 — 纯 Python

**决定**：MVP1-MVP4 用纯 Python Orchestrator。
**原因**：同类工具（arxiv-digest / zotero-arxiv-daily / research-assist / paper-distill-mcp / Scholar-Agent）均采用确定性 pipeline + CLI，未引入 LangGraph/CrewAI/Prefect/Dagster；首期工作流为单向 DAG，无需复杂调度。
**触发重新评估的条件**：出现多 Agent handoff、人工审批恢复、长任务 checkpoint、复杂分支需求。

### ADR-002：Agent 边界

**决定**：流程稳定性由确定性代码负责；Runtime Agents 仅负责语义判断，不修改 paper metadata，不操作外部副作用。
**Screening Agent**：相关性/评分/优先级/标签/理由。
**Digest Agent**：周期总结/单篇摘要/趋势/推荐阅读。
**严禁**：把摘要生成塞进 Screening Agent；让 Agent 直接调用 Zotero/飞书；让 Agent 写 paper metadata 字段。

### ADR-003：Zotero Import State Machine

**决定**：Zotero 写入采用状态机替代严格 two-phase commit。
**状态**：`accepted → pending_zotero → importing_zotero → imported_zotero | zotero_failed`。
**默认策略**：`manual_approval`——`accepted` 状态的 paper 不会自动进入 `pending_zotero`，必须由用户通过 `approve` 命令（MVP5）或显式标志批准。
**`import-zotero` 默认行为**：仅处理 `status='pending_zotero'` 的 items；`accepted` 但未批准的不会被写入 Zotero。
**自动批准**：必须通过显式参数 `--auto-import-A-only` 才允许将 `priority=A` 的 accepted items 自动转为 `pending_zotero`。
**重试**：启动时扫描所有非终态状态（`pending_zotero` / `importing_zotero` / `zotero_failed`），自动重试。
**幂等**：DOI/zotero_item_key 任一存在则更新而不创建。

---

## 12. 安全与合规

延续原文档 §18，强调：

- 不抓非法全文、不绕付费墙、不存敏感 key 到仓库（`.env` 必须 gitignore）
- 自动写 Zotero 必须先经过 dry-run；MVP3 默认 manual_approval
- 所有 Agent 输出经过 Pydantic schema 校验失败即降级
- 工具调用最小权限：飞书 webhook 只发不收，Zotero key 只给最小必要 scope

---

## 13. 范围之外（Out of Scope，第一版）

- 全文爬取付费墙论文 / Sci-Hub / 浏览器自动化
- 多用户 SaaS / Web UI
- LangGraph / CrewAI / Prefect / Dagster
- 完全自主多 Agent 协商
- MCP Server 化（MVP5+ 评估）
- BibTeX 自动生成 / Related Work 草稿（MVP5+ 评估）

---

## 14. 决策清单回填（对应原文档 §19）

| # | 问题 | 决定 |
|---|---|---|
| 19.1.1 | Workflow + 局部 Agent | ✅ |
| 19.1.2 | 查新/去重/Zotero/飞书 = 确定性 | ✅ |
| 19.1.3 | Screening + Digest 是核心 Agent | ✅，且严禁混淆职责 |
| 19.1.4 | LangGraph vs Python | Python，理由见 ADR-001 |
| 19.1.5 | SQLite 起步 | ✅ |
| 19.2.1 | Python 3.11+ | ✅ |
| 19.2.2 | uv vs poetry | uv |
| 19.2.3 | LLMClient 抽象 | ✅ MVP2 |
| 19.2.4 | pyzotero | ✅ |
| 19.2.5 | 飞书 webhook | ✅ MVP4 起，不用 lark-cli |
| 19.2.6 | Playwright | 不引入 |
| 19.3.1 | 数据源优先级 | Crossref + arXiv 先；IEEE/Semantic Scholar 后 |
| 19.3.2 | Crossref + arXiv 先 | ✅ |
| 19.3.3 | RSS 独立模块 | ✅ |
| 19.3.4 | Semantic Scholar 用于补充 | ✅ |
| 19.4.1 | Pydantic 统一模型 | ✅ |
| 19.4.2 | Alembic | MVP1 暂不引入，手写 SQL migration；MVP3+ 评估 |
| 19.4.3 | Repository 层 | ✅ |
| 19.4.4 | CLI 子命令 | ✅，按 §5 矩阵 |
| 19.4.5 | 完整单测 | ✅，所有 fetcher mock |
| 19.4.6 | e2e fixture | ✅ MVP4 提供 |
| 19.5.1 | 自动入 Zotero | 默认 manual_approval；后续 auto_import_A_only |
| 19.5.2 | 默认只生成候选报告 | ✅ MVP1 |
| 19.5.3 | 人工审批默认 | ✅，MVP5 实现 |
| 19.5.4 | 多研究画像 | ✅ via `configs/profiles/`；MVP5+ 完善 |
| 19.5.5 | 多 Zotero collection | ✅，按 profile 配置 |

---

## 15. 拆分到子文档的对应

本 spec 是 single source of truth。后续以下子文档由 scribe 子代理从本文档抽取：

| 子文档 | 内容来源 |
|---|---|
| `docs/architecture.md` | §3、§9、§14 |
| `docs/runtime_agents.md` | §1.2、§1.3、§7、§14 |
| `docs/development_workflow.md` | §1.1（独立扩写为开发协作流程） |
| `docs/configuration.md` | §8 |
| `docs/adr/ADR-001` | §11 ADR-001 |
| `docs/adr/ADR-002` | §11 ADR-002 + §1 |
| `docs/adr/ADR-003` | §11 ADR-003 + §6 papers 字段 + §3.1 状态机 |
