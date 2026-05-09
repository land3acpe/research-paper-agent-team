# Architecture（运行时架构）

> **定位**：本文档仅描述项目运行时的系统架构——即 Python Orchestrator 执行论文查新 pipeline 时的模块组成与数据流。开发协作流程不在此文档范围内，见 [development_workflow.md](./development_workflow.md)。

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
| **Screening Agent** | **Runtime LLM** | 相关性/评分/优先级/标签/筛选理由 |
| Quality Gate | 确定性 | 根据 Agent 输出 + 规则做 accept/reject/uncertain |
| Zotero Writer | 确定性 | pyzotero 调用，State Machine 管理状态 |
| **Digest Agent** | **Runtime LLM** | 周期总结/单篇摘要/趋势/推荐阅读 |
| Report Writer | 确定性 | Jinja2 渲染 Markdown + JSON |
| Feishu Notifier | 确定性 | webhook，幂等通知 |
| State Store | 确定性 | SQLite。MVP1 表：papers / runs / filter_decisions / dedup_candidates。MVP2 加：screening_results / llm_calls。MVP3 加：zotero_items + papers.zotero_state/zotero_last_error。MVP4 加：notifications。source_watermarks 推迟到 MVP1.5 或 MVP2 引入——MVP1 的时间窗口由 schedule.yaml 显式配置或 CLI 参数指定 |

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

## 14. 决策清单回填

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
| 19.4.4 | CLI 子命令 | ✅，按 CLI 契约矩阵 |
| 19.4.5 | 完整单测 | ✅，所有 fetcher mock |
| 19.4.6 | e2e fixture | ✅ MVP4 提供 |
| 19.5.1 | 自动入 Zotero | 默认 manual_approval；后续 auto_import_A_only |
| 19.5.2 | 默认只生成候选报告 | ✅ MVP1 |
| 19.5.3 | 人工审批默认 | ✅，MVP5 实现 |
| 19.5.4 | 多研究画像 | ✅ via `configs/profiles/`；MVP5+ 完善 |
| 19.5.5 | 多 Zotero collection | ✅，按 profile 配置 |

---

详细决策见 ADR-001 / ADR-002 / ADR-003；single source of truth 见 `docs/superpowers/specs/2026-05-10-research-paper-agent-team-design.md`。
