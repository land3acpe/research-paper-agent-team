# MVP1 实现计划：论文查新 + 去重 + Markdown 报告

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。
> **规格来源**：`docs/superpowers/specs/2026-05-10-research-paper-agent-team-design.md`（**single source of truth**，遇到歧义查 spec）
> **DAG**：见末尾依赖图
> **Agent Team 路由**：每个任务标注 Owner / Reviewer

**目标：** 实现 research-paper-agent-team 的 MVP1：从 Crossref + arXiv 拉论文 → Normalize → Dedup → RuleFilter → 写 SQLite + Markdown/JSON 报告，端到端 CLI 可跑通且 mock 测试全绿。

**架构：** 纯 Python Orchestrator + 确定性 pipeline + SQLite + JSON/Markdown 中间产物。无 LLM、无 Zotero、无飞书。所有 fetcher 单测使用 mock fixture，不打真实 API。

**技术栈：** Python 3.11+ / uv（包管理）/ Pydantic v2（模型）/ httpx（HTTP）/ feedparser（arXiv Atom）/ rapidfuzz（fuzzy match）/ Jinja2（模板）/ typer（CLI）/ pytest + pytest-mock + pytest-httpx（测试）/ structlog（日志）

**Agent Team 路由（开发协作）：**
- `Build` (big-pickle)：调度任务、追踪 DAG 进度，**不写代码**
- `Plan` (kimi-k2.6)：MVP1 内部 DAG 拆分、跨任务影响分析，**只读**
- `coder` (deepseek-v4-pro)：实现所有 src/ 与 tests/ 代码
- `reviewer` (deepseek-v4-pro)：每个 Gate 的代码 + spec 一致性审查
- `researcher` (qwen3.5-plus)：Crossref/arXiv API 文档调研、字段映射调研
- `scribe` (minimax-m2.7)：从 spec 抽 docs/architecture.md / runtime_agents.md / dev_workflow.md / ADR-001/002/003，写 README
- `explore` (minimax-m2.5)：跨任务依赖定位、历史代码引用查找
- `debug` (glm-5.1)：fetcher 解析失败、SQLite 锁冲突、httpx 超时等疑难

> **重要**：上述 Agent Team 是开发协作工具链，**不属于项目 runtime**，**不写入 `src/`**，不被 Python Orchestrator 调用，不影响 runtime pipeline。

---

## 文件结构（决策锁定）

```text
D:\projects\agents\research-paper-agent-team\
├── .gitignore
├── .env.example
├── README.md
├── pyproject.toml
├── uv.lock                            # uv 自动生成
├── .python-version                    # 3.11
├── configs/
│   ├── schedule.yaml                  # 时间窗口与限额
│   ├── sources.yaml                   # Crossref + arXiv 查询
│   ├── tag_schema.yaml                # MVP1 占位（MVP2 才用）
│   └── profiles/dtp-pmsm/research_profile.yaml
├── docs/
│   ├── architecture.md                # 从 spec §3/§9/§14 抽
│   ├── runtime_agents.md              # 从 spec §1.2/§1.3/§7/§14 抽（MVP1 占位说明）
│   ├── development_workflow.md        # 从 spec §1.1 抽
│   ├── configuration.md               # 从 spec §8 抽
│   ├── superpowers/
│   │   ├── specs/2026-05-10-research-paper-agent-team-design.md
│   │   └── plans/2026-05-10-mvp1-implementation.md
│   └── adr/
│       ├── ADR-001-orchestrator-choice.md
│       ├── ADR-002-agent-boundary.md
│       └── ADR-003-zotero-import-state-machine.md
├── src/
│   ├── __init__.py
│   ├── main.py                        # typer CLI 入口
│   ├── orchestrator.py                # MVP1 pipeline
│   ├── config.py                      # YAML 加载 + Pydantic 校验
│   ├── logging_config.py              # structlog 配置
│   ├── models/
│   │   ├── __init__.py
│   │   ├── paper.py                   # PaperCandidate
│   │   ├── run.py                     # RunSummary, SourceResult
│   │   └── dedup.py                   # DedupCandidate
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── runid.py                   # Run ID 生成器
│   │   ├── time.py                    # 窗口计算
│   │   ├── hashing.py                 # title hash, normalized_title
│   │   └── retry.py                   # tenacity 装饰器封装
│   ├── fetchers/
│   │   ├── __init__.py
│   │   ├── base.py                    # 抽象基类 + DTO
│   │   ├── _http.py                   # 共享 httpx client
│   │   ├── crossref.py
│   │   └── arxiv.py
│   ├── normalize/
│   │   ├── __init__.py
│   │   ├── title.py                   # 大小写、标点、unicode
│   │   └── normalizer.py              # 字段统一
│   ├── dedupe/
│   │   ├── __init__.py
│   │   ├── hard.py                    # DOI / arXiv ID / source_id
│   │   ├── soft.py                    # title hash / fuzzy / title+author+year
│   │   └── deduplicator.py            # 编排，写 dedup_candidates
│   ├── filter/
│   │   ├── __init__.py
│   │   └── rule_filter.py             # 规则过滤 + 写 filter_decisions
│   ├── reports/
│   │   ├── __init__.py
│   │   ├── digest_writer.py           # Markdown/JSON 渲染
│   │   └── templates/
│   │       ├── candidates.md.j2
│   │       └── run_summary.md.j2
│   └── storage/
│       ├── __init__.py
│       ├── db.py                      # connection + schema 应用
│       ├── repositories.py            # PapersRepo / RunsRepo / FilterDecisionsRepo / DedupCandidatesRepo
│       └── migrations/
│           └── 001_initial.sql
├── data/                              # gitignored
│   ├── papers.db
│   ├── raw/{run_id}/
│   ├── normalized/{run_id}/
│   ├── reports/{run_id}/
│   └── logs/
└── tests/
    ├── __init__.py
    ├── conftest.py                    # 全局 fixture
    ├── fixtures/
    │   ├── crossref/
    │   │   ├── search_dtp_pmsm.json
    │   │   └── empty_response.json
    │   └── arxiv/
    │       ├── search_motor_control.xml
    │       └── empty_response.xml
    ├── unit/
    │   ├── test_runid.py
    │   ├── test_time.py
    │   ├── test_hashing.py
    │   ├── test_config.py
    │   ├── test_models.py
    │   ├── test_db.py
    │   ├── test_repositories.py
    │   ├── test_normalize_title.py
    │   ├── test_normalizer.py
    │   ├── test_fetcher_crossref.py
    │   ├── test_fetcher_arxiv.py
    │   ├── test_dedupe_hard.py
    │   ├── test_dedupe_soft.py
    │   ├── test_deduplicator.py
    │   ├── test_rule_filter.py
    │   └── test_report_writer.py
    └── integration/
        ├── test_orchestrator.py
        └── test_cli.py
```

**职责单元化检查**：
- 每个 fetcher 一个文件，共享 HTTP 在 `_http.py`
- dedupe 拆 hard/soft/编排 三层，便于独立测试
- normalize 拆 title 工具与字段编排两层
- repositories 一个文件容纳 4 个 repo，因为它们都很轻
- CLI 命令全部走 typer 子命令注入到 `main.py`

---

## Gate 节奏与 Reviewer 检查点

| Gate | 任务范围 | Reviewer 触发 | 验收 |
|---|---|---|---|
| G1 | T0-T1（项目骨架 + 文档） | scribe 完成 → reviewer | 文档无歧义，git 干净 |
| G2 | T2-T7（基础设施：日志/utils/config/models/db） | T7 完成 → reviewer | 单测全绿、覆盖率核心模块 ≥ 90% |
| G3 | T8-T10（normalize + fetchers） | T10 完成 → reviewer | mock fetcher 端到端可跑 |
| G4 | T11-T13（dedup + filter） | T13 完成 → reviewer | dedup 无重复入库、filter_decisions 完整 |
| G5 | T14-T15（报告 + orchestrator） | T15 完成 → reviewer | orchestrator dry-run 输出完整报告 |
| G6 | T16-T17（CLI + e2e） | T17 完成 → reviewer | 5 条 MVP1 验收闸门全过 |

每个 Gate **不通过则回到对应任务**，由 debug/coder 修复后重审。

---

## 任务

### 任务 0：项目骨架与依赖

**Owner：** coder | **Reviewer：** scribe（README 部分）| **BlockedBy：** 无

**文件：**
- 创建：`D:\projects\agents\research-paper-agent-team\.gitignore`
- 创建：`pyproject.toml`
- 创建：`.python-version`
- 创建：`.env.example`
- 创建：`README.md`
- 创建：`configs/schedule.yaml`、`configs/sources.yaml`、`configs/profiles/dtp-pmsm/research_profile.yaml`、`configs/tag_schema.yaml`

- [ ] **步骤 1：git init + 基础文件**

```bash
cd D:/projects/agents/research-paper-agent-team
git init
git branch -M main
```

- [ ] **步骤 2：写 `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
.venv/
.pytest_cache/
.coverage
htmlcov/
.mypy_cache/
.ruff_cache/

# uv
.uv/

# Project data (gitignored to avoid committing API responses / DB)
data/

# Secrets
.env
.env.local

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```

- [ ] **步骤 3：写 `.python-version`**

```text
3.11
```

- [ ] **步骤 4：写 `pyproject.toml`**

```toml
[project]
name = "research-paper-agent-team"
version = "0.1.0"
description = "Research paper discovery and management agent team for domain-specific literature review"
requires-python = ">=3.11,<3.13"
readme = "README.md"
dependencies = [
    "pydantic>=2.7,<3",
    "pydantic-settings>=2.3",
    "httpx>=0.27,<1",
    "feedparser>=6.0",
    "rapidfuzz>=3.9",
    "jinja2>=3.1",
    "typer>=0.12",
    "structlog>=24.1",
    "pyyaml>=6.0",
    "tenacity>=8.3",
    "python-slugify>=8",
    "shortuuid>=1.0",
]

[project.scripts]
rpat = "src.main:app"

[dependency-groups]
dev = [
    "pytest>=8.2",
    "pytest-mock>=3.14",
    "pytest-httpx>=0.30",
    "pytest-cov>=5",
    "ruff>=0.5",
    "mypy>=1.10",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "live_api: tests that hit real external APIs (excluded by default)",
    "integration: end-to-end orchestrator tests",
]
addopts = "-m 'not live_api'"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "N"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
```

- [ ] **步骤 5：写 `.env.example`**

```dotenv
# Crossref polite pool: provide an email to get higher rate limits
CROSSREF_MAILTO=

# arXiv has no auth in MVP1

# Future MVPs (do NOT use in MVP1):
# DEEPSEEK_API_KEY=
# ZOTERO_API_KEY=
# ZOTERO_LIBRARY_ID=
# FEISHU_WEBHOOK_URL=
```

- [ ] **步骤 6：写 `configs/schedule.yaml`**

```yaml
schedule:
  enabled: false
  mode: weekly
  day: sunday
  time: "09:00"
  timezone: "Asia/Shanghai"

window:
  daily_days: 3
  weekly_days: 14
  monthly_days: 45

limits:
  max_candidates_per_source: 100
  max_total_candidates: 300
  max_runtime_minutes: 30
```

- [ ] **步骤 7：写 `configs/sources.yaml`**

```yaml
sources:
  crossref:
    enabled: true
    mailto_env: "CROSSREF_MAILTO"
    queries:
      - name: "dtp_pmsm"
        query: "dual three-phase PMSM"
      - name: "harmonic_suppression"
        query: "harmonic current suppression motor drive"
    max_results: 100

  arxiv:
    enabled: true
    categories: ["eess.SY"]
    queries:
      - name: "motor_control_ai"
        query: "motor control neural network parameter identification"
    max_results: 100
```

- [ ] **步骤 8：写 `configs/profiles/dtp-pmsm/research_profile.yaml`**

```yaml
research_profile:
  name: "DTP-PMSM Harmonic Current Suppression"
  slug: "dtp-pmsm"
  field: "dual three-phase permanent magnet synchronous motor harmonic current suppression"

  core_topics:
    - "dual three-phase PMSM"
    - "six-phase PMSM"
    - "multiphase motor"
    - "harmonic current suppression"
    - "vector space decomposition"

  reject_topics:
    - "power system harmonic compensation without motor drive relevance"
    - "mechanical design only"

  rule_filter:
    require_year_after: 2018
    require_abstract: true
    blacklist_keywords:
      - "review article only"
```

- [ ] **步骤 9：写 `configs/tag_schema.yaml`**

```yaml
# MVP1 占位；MVP2 引入 Screening Agent 时启用
allowed_tags:
  topics: []
  methods: []
  parameters: []
  status: []
  priority: []
```

- [ ] **步骤 10：写 `README.md`（骨架）**

```markdown
# research-paper-agent-team

面向特定科研方向（首版：DTP-PMSM 谐波抑制）的论文查新与管理 Agent Team。

> **当前阶段：MVP1**——查新 + 去重 + Markdown 报告。无 LLM、无 Zotero、无飞书。

## 快速开始

```bash
# 安装依赖
uv sync

# 初始化数据库
uv run rpat db-init

# Dry-run 一次查新（不写库）
uv run rpat discover --profile dtp-pmsm --days 14 --dry-run

# 正式查新
uv run rpat discover --profile dtp-pmsm --days 14
```

## 文档

- [架构](docs/architecture.md)
- [配置](docs/configuration.md)
- [Runtime Agents（MVP2+）](docs/runtime_agents.md)
- [开发协作流程](docs/development_workflow.md)
- ADR：[ADR-001](docs/adr/ADR-001-orchestrator-choice.md) · [ADR-002](docs/adr/ADR-002-agent-boundary.md) · [ADR-003](docs/adr/ADR-003-zotero-import-state-machine.md)

## 范围之外（MVP1）

LLM Screening · Zotero · 飞书 · LangGraph · MCP · Semantic Scholar enrichment · IEEE Xplore · RSS

详见 spec：`docs/superpowers/specs/2026-05-10-research-paper-agent-team-design.md`
```

- [ ] **步骤 11：安装依赖并验证**

运行：`uv sync`
预期：`.venv/` 创建成功，`uv.lock` 生成

运行：`uv run python -c "import pydantic, httpx, feedparser, rapidfuzz, jinja2, typer, structlog; print('ok')"`
预期：输出 `ok`

- [ ] **步骤 12：Commit**

```bash
git add .
git commit -m "feat: 初始化项目骨架（pyproject + configs + README）"
```

---

### 任务 1：从 spec 抽取项目文档

**Owner：** scribe | **Reviewer：** reviewer | **BlockedBy：** T0

**文件：**
- 创建：`docs/architecture.md`（从 spec §3、§9、§14 抽）
- 创建：`docs/runtime_agents.md`（从 spec §1.2、§1.3、§7、§14；MVP1 加一段"MVP1 暂未启用 Runtime Agents"提示）
- 创建：`docs/development_workflow.md`（从 spec §1.1，扩写 Claude Code 协作流程；明示 Dev Agent Team **不属于 runtime**）
- 创建：`docs/configuration.md`（从 spec §8 抽）
- 创建：`docs/adr/ADR-001-orchestrator-choice.md`（从 spec §11 ADR-001）
- 创建：`docs/adr/ADR-002-agent-boundary.md`（从 spec §11 ADR-002 + §1）
- 创建：`docs/adr/ADR-003-zotero-import-state-machine.md`（从 spec §11 ADR-003 + §6 papers 字段 + §3.1 状态机）

- [ ] **步骤 1：scribe 阅读 spec §15 拆分对应表**

读取：`docs/superpowers/specs/2026-05-10-research-paper-agent-team-design.md`
关注：§15 子文档对应表，确认每个 doc 的源章节。

- [ ] **步骤 2：写 `docs/architecture.md`**

内容要求：
- 简短开篇说明本文档为运行时架构
- 复制 spec §3.1 流程图
- 复制 spec §3.2 模块职责表
- 复制 spec §9 目录结构
- 复制 spec §14 决策回填表
- **不复制** spec §1.1（Dev Agent Team），那部分进 development_workflow.md
- 末尾加："详细决策见 ADR-001/002/003；single source of truth 见 spec"

- [ ] **步骤 3：写 `docs/runtime_agents.md`**

内容要求：
- 开篇：本文档仅描述项目运行时调用的 LLM 模块
- §1：MVP1 状态——**当前未启用 Runtime Agents**，本文档为前向规划
- §2：复制 spec §1.2 Runtime Agents 定义
- §3：复制 spec §1.3 字段写权限矩阵
- §4：复制 spec §7 Screening Agent 详细
- §5：复制 spec §7 Digest Agent 详细
- §6：明示"Runtime Agents 与 Development Agent Team 的区别"——指向 development_workflow.md

- [ ] **步骤 4：写 `docs/development_workflow.md`**

内容要求：
- §1：开篇明示——本文档仅描述使用 Claude Code 辅助开发本项目的协作流程，**不属于项目 runtime**
- §2：Development Agent Team 角色矩阵：
  | 角色 | 模型 | 职责 |
  |---|---|---|
  | Build (Tab) | big-pickle | 调度 |
  | Plan (Tab) | kimi-k2.6 | 任务拆分（只读） |
  | coder | deepseek-v4-pro | 实现 src/ + tests/ |
  | reviewer | deepseek-v4-pro | 代码审查 |
  | researcher | qwen3.5-plus | 外部 API/算法调研 |
  | scribe | minimax-m2.7 | 文档抽取与撰写 |
  | explore | minimax-m2.5 | 代码定位与引用查找 |
  | debug | glm-5.1 | 疑难调试 |
- §3：常见协作模式（如何拆任务、如何走 Gate、如何重审）
- §4：边界——这些 Agent **不会**：进入 src/、被 Python 调用、参与论文流程

- [ ] **步骤 5：写 `docs/configuration.md`**

内容要求：复制 spec §8 全部内容；为每个 yaml 加一段"何时编辑"说明。

- [ ] **步骤 6：写 `docs/adr/ADR-001-orchestrator-choice.md`**

ADR 格式：
```markdown
# ADR-001：Orchestrator 选型——纯 Python

- **状态**：Accepted
- **日期**：2026-05-10
- **决策者**：项目设计阶段

## 背景
[复制 spec §11 ADR-001 + 用户调研结论：arxiv-digest / zotero-arxiv-daily / research-assist / paper-distill-mcp / Scholar-Agent 均采用确定性 pipeline]

## 决定
MVP1-MVP4 使用纯 Python Orchestrator + 确定性 pipeline + 局部 LLM Runtime Agents。

## 后果
- 优点：依赖少、调试简单、单测易写、与同类工具技术栈对齐
- 缺点：复杂分支、人工审批恢复、长任务 checkpoint 需要手写

## 触发重新评估的条件
- 出现多 Agent handoff
- 需要人工审批中断后恢复
- 单次 run > 1 小时需 checkpoint
- 复杂条件分支无法用 Python if/else 优雅表达

## 备选方案
LangGraph / CrewAI / Prefect / Dagster——拒绝原因：MVP1-4 工作流为单向 DAG，引入框架反而增加学习与维护成本。
```

- [ ] **步骤 7：写 `docs/adr/ADR-002-agent-boundary.md`**

内容要求：
- 决定：Runtime Agents 仅做语义判断；流程稳定性由确定性代码负责
- 写权限矩阵（复制 spec §1.3）
- 严禁清单：摘要塞进 Screening / Agent 直调 Zotero/飞书 / Agent 写 paper metadata 字段
- Dev Agent Team 与 Runtime Agents 的边界（指向 dev_workflow.md）

- [ ] **步骤 8：写 `docs/adr/ADR-003-zotero-import-state-machine.md`**

内容要求：
- 状态图（mermaid）：accepted → pending_zotero → importing_zotero → imported_zotero / zotero_failed
- 默认策略：manual_approval；`import-zotero` 默认只处理 pending_zotero
- 自动批准：必须 `--auto-import-A-only` 显式开启
- 重试：启动时扫描非终态自动重试
- 幂等：DOI/zotero_item_key 任一存在则更新而不创建
- papers 表新增字段：zotero_state / zotero_last_error
- **MVP3 才实现**——本 ADR 为前向决策

- [ ] **步骤 9：reviewer 验收**

reviewer 检查清单：
- [ ] 7 份文档存在
- [ ] development_workflow.md 明确"不属于 runtime"
- [ ] runtime_agents.md 明确"MVP1 未启用"
- [ ] 3 份 ADR 状态/日期/决定/后果/备选 5 节齐全
- [ ] 所有交叉引用链接有效

- [ ] **步骤 10：Commit**

```bash
git add docs/
git commit -m "docs: 从 spec 抽取 architecture / runtime_agents / dev_workflow / configuration / ADR-001-003"
```

**Gate G1**：T0-T1 完成。reviewer 必须通过，否则回到对应任务。

---

### 任务 2：日志系统（structlog）

**Owner：** coder | **Reviewer：** reviewer (G2 时一起审) | **BlockedBy：** T0

**文件：**
- 创建：`src/__init__.py`（空）
- 创建：`src/logging_config.py`
- 测试：`tests/unit/test_logging.py`

- [ ] **步骤 1：写测试 `tests/unit/test_logging.py`**

```python
import json
import structlog
from src.logging_config import configure_logging


def test_configure_logging_returns_logger(tmp_path):
    log_file = tmp_path / "test.log"
    logger = configure_logging(log_level="info", log_file=str(log_file))
    assert logger is not None


def test_logging_writes_json_to_file(tmp_path):
    log_file = tmp_path / "test.log"
    logger = configure_logging(log_level="info", log_file=str(log_file))
    logger.info("test_event", run_id="abc", count=42)
    content = log_file.read_text()
    record = json.loads(content.strip().splitlines()[-1])
    assert record["event"] == "test_event"
    assert record["run_id"] == "abc"
    assert record["count"] == 42
```

- [ ] **步骤 2：运行测试验证失败**

运行：`uv run pytest tests/unit/test_logging.py -v`
预期：`ModuleNotFoundError: No module named 'src.logging_config'`

- [ ] **步骤 3：实现 `src/logging_config.py`**

```python
"""Structured logging configuration based on structlog."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import structlog


def configure_logging(
    log_level: str = "info",
    log_file: str | None = None,
) -> structlog.stdlib.BoundLogger:
    """Configure structlog for the project.

    Console output is human-readable; file output (if log_file given) is JSON.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(message)s")
        )
        handlers.append(file_handler)

    logging.basicConfig(level=level, handlers=handlers, force=True)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger()
```

- [ ] **步骤 4：运行测试验证通过**

运行：`uv run pytest tests/unit/test_logging.py -v`
预期：2 passed

- [ ] **步骤 5：Commit**

```bash
git add src/__init__.py src/logging_config.py tests/unit/test_logging.py
git commit -m "feat(logging): 接入 structlog 并支持文件 JSON + 控制台输出"
```

---

### 任务 3：Run ID 生成器

**Owner：** coder | **Reviewer：** G2 时审 | **BlockedBy：** T0

**文件：**
- 创建：`src/utils/__init__.py`（空）
- 创建：`src/utils/runid.py`
- 测试：`tests/unit/test_runid.py`

- [ ] **步骤 1：写测试 `tests/unit/test_runid.py`**

```python
import re
from datetime import datetime, timezone

import pytest

from src.utils.runid import generate_run_id, parse_run_id


RUN_ID_PATTERN = re.compile(
    r"^[a-z0-9-]+-(daily|weekly|monthly|manual)-\d{8}-\d{6}-[a-z0-9]{8}$"
)


def test_generate_run_id_format():
    rid = generate_run_id(profile_slug="dtp-pmsm", schedule_mode="weekly")
    assert RUN_ID_PATTERN.match(rid), f"unexpected format: {rid}"


def test_generate_run_id_unique():
    rids = {generate_run_id("dtp-pmsm", "weekly") for _ in range(100)}
    assert len(rids) == 100


def test_generate_run_id_uses_timestamp():
    fixed = datetime(2026, 5, 10, 9, 0, 0, tzinfo=timezone.utc)
    rid = generate_run_id("dtp-pmsm", "weekly", now=fixed)
    assert "20260510-090000" in rid


def test_parse_run_id_roundtrip():
    rid = "dtp-pmsm-weekly-20260510-090000-a1b2c3d4"
    parsed = parse_run_id(rid)
    assert parsed.profile_slug == "dtp-pmsm"
    assert parsed.schedule_mode == "weekly"
    assert parsed.timestamp.year == 2026
    assert parsed.short_id == "a1b2c3d4"


def test_parse_run_id_invalid():
    with pytest.raises(ValueError):
        parse_run_id("invalid-format")
```

- [ ] **步骤 2：运行测试验证失败**

运行：`uv run pytest tests/unit/test_runid.py -v`
预期：`ImportError`

- [ ] **步骤 3：实现 `src/utils/runid.py`**

```python
"""Run ID generation and parsing.

Format: {profile_slug}-{schedule_mode}-{YYYYMMDD-HHMMSS}-{shortuuid8}
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

import shortuuid

ScheduleMode = Literal["daily", "weekly", "monthly", "manual"]

_PATTERN = re.compile(
    r"^(?P<slug>[a-z0-9-]+)-"
    r"(?P<mode>daily|weekly|monthly|manual)-"
    r"(?P<date>\d{8})-(?P<time>\d{6})-"
    r"(?P<short>[a-z0-9]{8})$"
)


@dataclass(frozen=True)
class RunIdParts:
    profile_slug: str
    schedule_mode: str
    timestamp: datetime
    short_id: str


def generate_run_id(
    profile_slug: str,
    schedule_mode: ScheduleMode,
    now: datetime | None = None,
) -> str:
    if now is None:
        now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%d-%H%M%S")
    short = shortuuid.uuid()[:8].lower()
    return f"{profile_slug}-{schedule_mode}-{ts}-{short}"


def parse_run_id(run_id: str) -> RunIdParts:
    m = _PATTERN.match(run_id)
    if not m:
        raise ValueError(f"invalid run_id: {run_id}")
    ts = datetime.strptime(
        f"{m['date']}{m['time']}", "%Y%m%d%H%M%S"
    ).replace(tzinfo=timezone.utc)
    return RunIdParts(
        profile_slug=m["slug"],
        schedule_mode=m["mode"],
        timestamp=ts,
        short_id=m["short"],
    )
```

- [ ] **步骤 4：运行测试验证通过**

运行：`uv run pytest tests/unit/test_runid.py -v`
预期：5 passed

- [ ] **步骤 5：Commit**

```bash
git add src/utils/__init__.py src/utils/runid.py tests/unit/test_runid.py
git commit -m "feat(utils): Run ID 生成器（profile-mode-timestamp-shortuuid 格式）"
```

---

### 任务 4：时间窗口工具

**Owner：** coder | **Reviewer：** G2 时审 | **BlockedBy：** T0

**文件：**
- 创建：`src/utils/time.py`
- 测试：`tests/unit/test_time.py`

- [ ] **步骤 1：写测试 `tests/unit/test_time.py`**

```python
from datetime import datetime, timezone

from src.utils.time import compute_window, format_iso_date


def test_compute_window_basic():
    now = datetime(2026, 5, 10, tzinfo=timezone.utc)
    start, end = compute_window(days=14, now=now)
    assert end == now
    assert (end - start).days == 14


def test_compute_window_with_overlap():
    now = datetime(2026, 5, 10, tzinfo=timezone.utc)
    start, end = compute_window(days=14, overlap_days=2, now=now)
    assert (end - start).days == 16


def test_format_iso_date():
    d = datetime(2026, 5, 10, 9, 30, tzinfo=timezone.utc)
    assert format_iso_date(d) == "2026-05-10"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`uv run pytest tests/unit/test_time.py -v`

- [ ] **步骤 3：实现 `src/utils/time.py`**

```python
"""Time window utilities for paper discovery."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def compute_window(
    days: int,
    overlap_days: int = 0,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    """Return (start, end) datetimes for a discovery window.

    Window length = days + overlap_days, ending at `now`.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    start = now - timedelta(days=days + overlap_days)
    return start, now


def format_iso_date(dt: datetime) -> str:
    """YYYY-MM-DD."""
    return dt.strftime("%Y-%m-%d")
```

- [ ] **步骤 4：运行测试验证通过 + Commit**

```bash
uv run pytest tests/unit/test_time.py -v
git add src/utils/time.py tests/unit/test_time.py
git commit -m "feat(utils): 时间窗口计算与 ISO 日期格式化"
```

---

### 任务 5：哈希与标题归一化

**Owner：** coder | **Reviewer：** G2 时审 | **BlockedBy：** T0

**文件：**
- 创建：`src/utils/hashing.py`
- 创建：`src/normalize/__init__.py`（空）
- 创建：`src/normalize/title.py`
- 测试：`tests/unit/test_hashing.py`、`tests/unit/test_normalize_title.py`

- [ ] **步骤 1：写测试 `tests/unit/test_normalize_title.py`**

```python
from src.normalize.title import normalize_title


def test_lowercase():
    assert normalize_title("Dual Three-Phase PMSM") == "dual three-phase pmsm"


def test_strip_punctuation():
    assert normalize_title("FOC: A Survey!") == "foc a survey"


def test_collapse_whitespace():
    assert normalize_title("  Multiple   Spaces  ") == "multiple spaces"


def test_unicode_dashes():
    # en-dash / em-dash 都应折叠为普通 hyphen
    assert normalize_title("dtp–pmsm — method") == "dtp-pmsm method"


def test_strip_html_tags():
    assert normalize_title("<i>Italic</i> Title") == "italic title"


def test_idempotent():
    once = normalize_title("Some Title!")
    twice = normalize_title(once)
    assert once == twice
```

- [ ] **步骤 2：写测试 `tests/unit/test_hashing.py`**

```python
from src.utils.hashing import title_hash


def test_title_hash_stable():
    assert title_hash("Dual Three-Phase PMSM") == title_hash("Dual Three-Phase PMSM")


def test_title_hash_normalizes():
    # 大小写/标点不同应得到相同 hash
    assert title_hash("Dual Three-Phase PMSM!") == title_hash("dual three-phase pmsm")


def test_title_hash_distinct():
    assert title_hash("Topic A") != title_hash("Topic B")


def test_title_hash_length():
    assert len(title_hash("anything")) == 16  # 取 sha256 前 16 hex
```

- [ ] **步骤 3：运行测试验证失败**

```bash
uv run pytest tests/unit/test_normalize_title.py tests/unit/test_hashing.py -v
```

- [ ] **步骤 4：实现 `src/normalize/title.py`**

```python
"""Title normalization for hashing and fuzzy matching."""
from __future__ import annotations

import re
import unicodedata


_HTML_TAG = re.compile(r"<[^>]+>")
_PUNCT = re.compile(r"[^\w\s-]")
_WS = re.compile(r"\s+")
_UNICODE_DASHES = str.maketrans({"–": "-", "—": "-", "−": "-"})


def normalize_title(title: str) -> str:
    """Lowercase, strip HTML, collapse whitespace, unify dashes, strip punctuation."""
    if not title:
        return ""
    s = _HTML_TAG.sub("", title)
    s = unicodedata.normalize("NFKC", s)
    s = s.translate(_UNICODE_DASHES)
    s = s.lower()
    s = _PUNCT.sub("", s)
    s = _WS.sub(" ", s).strip()
    return s
```

- [ ] **步骤 5：实现 `src/utils/hashing.py`**

```python
"""Hashing utilities for paper deduplication."""
from __future__ import annotations

import hashlib

from src.normalize.title import normalize_title


def title_hash(title: str) -> str:
    """Stable hash over normalized title. First 16 hex of sha256."""
    norm = normalize_title(title)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]
```

- [ ] **步骤 6：运行测试 + Commit**

```bash
uv run pytest tests/unit/test_normalize_title.py tests/unit/test_hashing.py -v
git add src/normalize/__init__.py src/normalize/title.py src/utils/hashing.py tests/unit/test_normalize_title.py tests/unit/test_hashing.py
git commit -m "feat(normalize+utils): 标题归一化 + title_hash"
```

---

### 任务 6：配置加载（Pydantic Settings）

**Owner：** coder | **Reviewer：** G2 时审 | **BlockedBy：** T0

**文件：**
- 创建：`src/config.py`
- 测试：`tests/unit/test_config.py`

- [ ] **步骤 1：写测试 `tests/unit/test_config.py`**

```python
from pathlib import Path

import pytest
import yaml

from src.config import load_config, AppConfig


def write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def test_load_config_minimal(tmp_path):
    config_dir = tmp_path / "configs"
    write_yaml(config_dir / "schedule.yaml", {
        "schedule": {"enabled": False, "mode": "weekly", "day": "sunday", "time": "09:00", "timezone": "UTC"},
        "window": {"daily_days": 3, "weekly_days": 14, "monthly_days": 45},
        "limits": {"max_candidates_per_source": 10, "max_total_candidates": 30, "max_runtime_minutes": 5},
    })
    write_yaml(config_dir / "sources.yaml", {
        "sources": {
            "crossref": {"enabled": True, "queries": [{"name": "q1", "query": "x"}], "max_results": 10},
            "arxiv": {"enabled": True, "categories": ["eess.SY"], "queries": [{"name": "q1", "query": "x"}], "max_results": 10},
        }
    })
    profile_dir = config_dir / "profiles" / "dtp-pmsm"
    write_yaml(profile_dir / "research_profile.yaml", {
        "research_profile": {
            "name": "X", "slug": "dtp-pmsm", "field": "f",
            "core_topics": [], "reject_topics": [],
            "rule_filter": {"require_year_after": 2018, "require_abstract": True, "blacklist_keywords": []},
        }
    })

    cfg = load_config(config_dir=config_dir, profile="dtp-pmsm")
    assert isinstance(cfg, AppConfig)
    assert cfg.profile.slug == "dtp-pmsm"
    assert cfg.sources.crossref.enabled is True


def test_load_config_missing_profile(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(config_dir=tmp_path / "nonexistent", profile="nope")
```

- [ ] **步骤 2：运行测试验证失败**

- [ ] **步骤 3：实现 `src/config.py`**

```python
"""Configuration loading with Pydantic validation."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class ScheduleSection(BaseModel):
    enabled: bool
    mode: str
    day: str | None = None
    time: str | None = None
    timezone: str = "UTC"


class WindowSection(BaseModel):
    daily_days: int
    weekly_days: int
    monthly_days: int


class LimitsSection(BaseModel):
    max_candidates_per_source: int
    max_total_candidates: int
    max_runtime_minutes: int


class ScheduleConfig(BaseModel):
    schedule: ScheduleSection
    window: WindowSection
    limits: LimitsSection


class QuerySpec(BaseModel):
    name: str
    query: str


class CrossrefSource(BaseModel):
    enabled: bool
    mailto_env: str = "CROSSREF_MAILTO"
    queries: list[QuerySpec]
    max_results: int


class ArxivSource(BaseModel):
    enabled: bool
    categories: list[str] = []
    queries: list[QuerySpec]
    max_results: int


class SourcesConfig(BaseModel):
    crossref: CrossrefSource
    arxiv: ArxivSource


class RuleFilterSpec(BaseModel):
    require_year_after: int | None = None
    require_abstract: bool = False
    blacklist_keywords: list[str] = []


class ResearchProfile(BaseModel):
    name: str
    slug: str
    field: str
    core_topics: list[str] = []
    reject_topics: list[str] = []
    rule_filter: RuleFilterSpec = Field(default_factory=RuleFilterSpec)


class AppConfig(BaseModel):
    schedule: ScheduleSection
    window: WindowSection
    limits: LimitsSection
    sources: SourcesConfig
    profile: ResearchProfile


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_config(config_dir: Path, profile: str) -> AppConfig:
    schedule_raw = _read_yaml(config_dir / "schedule.yaml")
    sources_raw = _read_yaml(config_dir / "sources.yaml")
    profile_raw = _read_yaml(config_dir / "profiles" / profile / "research_profile.yaml")

    schedule_cfg = ScheduleConfig(**schedule_raw)
    sources_cfg = SourcesConfig(**sources_raw["sources"])
    profile_obj = ResearchProfile(**profile_raw["research_profile"])

    return AppConfig(
        schedule=schedule_cfg.schedule,
        window=schedule_cfg.window,
        limits=schedule_cfg.limits,
        sources=sources_cfg,
        profile=profile_obj,
    )
```

- [ ] **步骤 4：运行测试 + Commit**

```bash
uv run pytest tests/unit/test_config.py -v
git add src/config.py tests/unit/test_config.py
git commit -m "feat(config): YAML 加载 + Pydantic 校验"
```

---

### 任务 7：Pydantic 数据模型

**Owner：** coder | **Reviewer：** G2 时审 | **BlockedBy：** T0

**文件：**
- 创建：`src/models/__init__.py`（空）
- 创建：`src/models/paper.py`
- 创建：`src/models/run.py`
- 创建：`src/models/dedup.py`
- 测试：`tests/unit/test_models.py`

- [ ] **步骤 1：写测试 `tests/unit/test_models.py`**

```python
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.models.paper import PaperCandidate
from src.models.run import RunSummary, SourceResult
from src.models.dedup import DedupCandidate


def test_paper_candidate_minimal():
    p = PaperCandidate(source="crossref", title="A title")
    assert p.title == "A title"
    assert p.authors == []
    assert p.doi is None


def test_paper_candidate_with_all_fields():
    p = PaperCandidate(
        source="arxiv",
        source_id="2305.12345",
        doi="10.48550/arXiv.2305.12345",
        title="x",
        authors=["A. B."],
        venue="arXiv",
        published_date="2026-04-01",
        abstract="abstract",
        keywords=["k1"],
        url="https://example.com",
    )
    assert p.source == "arxiv"


def test_paper_candidate_requires_title():
    with pytest.raises(ValidationError):
        PaperCandidate(source="crossref")


def test_run_summary_defaults():
    s = RunSummary(
        run_id="x", started_at=datetime.now(timezone.utc).isoformat(), status="running"
    )
    assert s.raw_count == 0
    assert s.errors == []


def test_source_result_minimal():
    r = SourceResult(source="crossref", query="x", raw_count=10, normalized_count=8)
    assert r.errors == []


def test_dedup_candidate():
    d = DedupCandidate(
        paper_id_a=1, paper_id_b=2, match_type="fuzzy_title", similarity=0.92
    )
    assert d.status == "pending"
```

- [ ] **步骤 2：运行测试验证失败**

- [ ] **步骤 3：实现 `src/models/paper.py`**

```python
"""PaperCandidate model."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PaperCandidate(BaseModel):
    source: str
    source_id: str | None = None
    doi: str | None = None
    title: str
    normalized_title: str | None = None
    title_hash: str | None = None
    authors: list[str] = Field(default_factory=list)
    venue: str | None = None
    published_date: str | None = None
    indexed_date: str | None = None
    abstract: str | None = None
    keywords: list[str] = Field(default_factory=list)
    url: str | None = None
    pdf_url: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
```

- [ ] **步骤 4：实现 `src/models/run.py`**

```python
"""Run-level summary models."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RunStatus = Literal["running", "success", "failed", "partial"]


class SourceResult(BaseModel):
    source: str
    query: str
    raw_count: int = 0
    normalized_count: int = 0
    errors: list[str] = Field(default_factory=list)


class RunSummary(BaseModel):
    run_id: str
    started_at: str
    ended_at: str | None = None
    status: RunStatus
    sources: list[SourceResult] = Field(default_factory=list)
    raw_count: int = 0
    normalized_count: int = 0
    deduped_count: int = 0
    filtered_count: int = 0
    failed_count: int = 0
    report_path: str | None = None
    log_path: str | None = None
    errors: list[str] = Field(default_factory=list)
    dry_run: bool = False
```

- [ ] **步骤 5：实现 `src/models/dedup.py`**

```python
"""DedupCandidate model for soft-duplicate review queue."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

DedupStatus = Literal["pending", "merged", "rejected"]
MatchType = Literal["title_hash", "fuzzy_title", "title_author_year"]


class DedupCandidate(BaseModel):
    paper_id_a: int
    paper_id_b: int
    match_type: MatchType
    similarity: float
    status: DedupStatus = "pending"
    resolved_by: str | None = None
    resolved_at: str | None = None
```

- [ ] **步骤 6：运行测试 + Commit**

```bash
uv run pytest tests/unit/test_models.py -v
git add src/models/ tests/unit/test_models.py
git commit -m "feat(models): PaperCandidate / RunSummary / SourceResult / DedupCandidate"
```

---

### 任务 8：SQLite schema + connection 管理

**Owner：** coder | **Reviewer：** G2 时审 | **BlockedBy：** T7

**文件：**
- 创建：`src/storage/__init__.py`（空）
- 创建：`src/storage/db.py`
- 创建：`src/storage/migrations/001_initial.sql`
- 测试：`tests/unit/test_db.py`

- [ ] **步骤 1：写测试 `tests/unit/test_db.py`**

```python
import sqlite3
from pathlib import Path

from src.storage.db import open_db, apply_migrations, MIGRATIONS_DIR


def test_open_db_creates_file(tmp_path):
    db_path = tmp_path / "test.db"
    conn = open_db(db_path)
    assert db_path.exists()
    conn.close()


def test_apply_migrations_creates_tables(tmp_path):
    db_path = tmp_path / "test.db"
    conn = open_db(db_path)
    apply_migrations(conn)
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = {row[0] for row in cur.fetchall()}
    assert {"papers", "runs", "filter_decisions", "dedup_candidates", "schema_versions"} <= tables
    conn.close()


def test_apply_migrations_idempotent(tmp_path):
    db_path = tmp_path / "test.db"
    conn = open_db(db_path)
    apply_migrations(conn)
    apply_migrations(conn)  # 第二次应不报错
    cur = conn.execute("SELECT version FROM schema_versions ORDER BY version")
    versions = [row[0] for row in cur.fetchall()]
    assert versions == [1]
    conn.close()


def test_migrations_dir_has_001():
    assert (MIGRATIONS_DIR / "001_initial.sql").exists()
```

- [ ] **步骤 2：运行测试验证失败**

- [ ] **步骤 3：写 `src/storage/migrations/001_initial.sql`**

```sql
-- 001_initial.sql -- MVP1 tables

CREATE TABLE IF NOT EXISTS schema_versions (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doi TEXT,
    title TEXT NOT NULL,
    normalized_title TEXT,
    title_hash TEXT,
    source TEXT NOT NULL,
    source_id TEXT,
    url TEXT,
    pdf_url TEXT,
    authors_json TEXT,
    venue TEXT,
    published_date TEXT,
    indexed_date TEXT,
    abstract TEXT,
    keywords_json TEXT,
    status TEXT,
    raw_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);
CREATE INDEX IF NOT EXISTS idx_papers_title_hash ON papers(title_hash);
CREATE INDEX IF NOT EXISTS idx_papers_source_id ON papers(source, source_id);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT UNIQUE NOT NULL,
    profile_slug TEXT NOT NULL,
    schedule_mode TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT NOT NULL,
    sources_json TEXT,
    query_window_from TEXT,
    query_window_to TEXT,
    raw_count INTEGER DEFAULT 0,
    normalized_count INTEGER DEFAULT 0,
    deduped_count INTEGER DEFAULT 0,
    filtered_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    report_path TEXT,
    log_path TEXT,
    dry_run INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS filter_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    paper_id INTEGER,
    decision TEXT NOT NULL,
    reason_code TEXT,
    reason_text TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_filter_decisions_run ON filter_decisions(run_id);

CREATE TABLE IF NOT EXISTS dedup_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id_a INTEGER NOT NULL,
    paper_id_b INTEGER NOT NULL,
    match_type TEXT NOT NULL,
    similarity REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    resolved_by TEXT,
    resolved_at TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dedup_status ON dedup_candidates(status);
```

- [ ] **步骤 4：实现 `src/storage/db.py`**

```python
"""SQLite connection management and migrations."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def open_db(db_path: Path | str) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, isolation_level=None)  # autocommit-ish
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _applied_versions(conn: sqlite3.Connection) -> set[int]:
    try:
        cur = conn.execute("SELECT version FROM schema_versions")
        return {row[0] for row in cur.fetchall()}
    except sqlite3.OperationalError:
        return set()


def apply_migrations(conn: sqlite3.Connection) -> None:
    """Apply unapplied migrations from migrations/ in lexical order."""
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    applied = _applied_versions(conn)
    for f in files:
        version = int(f.name.split("_")[0])
        if version in applied:
            continue
        sql = f.read_text(encoding="utf-8")
        conn.executescript(sql)
        conn.execute(
            "INSERT INTO schema_versions(version, applied_at) VALUES (?, ?)",
            (version, datetime.now(timezone.utc).isoformat()),
        )
```

- [ ] **步骤 5：运行测试 + Commit**

```bash
uv run pytest tests/unit/test_db.py -v
git add src/storage/__init__.py src/storage/db.py src/storage/migrations/
git add tests/unit/test_db.py
git commit -m "feat(storage): SQLite schema + 幂等 migration（papers/runs/filter_decisions/dedup_candidates）"
```

---

### 任务 9：Repository 层

**Owner：** coder | **Reviewer：** G2 时审 | **BlockedBy：** T7, T8

**文件：**
- 创建：`src/storage/repositories.py`
- 测试：`tests/unit/test_repositories.py`

- [ ] **步骤 1：写测试 `tests/unit/test_repositories.py`**

```python
import sqlite3
from datetime import datetime, timezone

import pytest

from src.models.paper import PaperCandidate
from src.models.run import RunSummary, SourceResult
from src.storage.db import open_db, apply_migrations
from src.storage.repositories import (
    PapersRepo,
    RunsRepo,
    FilterDecisionsRepo,
    DedupCandidatesRepo,
)


@pytest.fixture
def conn(tmp_path):
    c = open_db(tmp_path / "t.db")
    apply_migrations(c)
    yield c
    c.close()


def test_papers_insert_and_lookup_by_doi(conn):
    repo = PapersRepo(conn)
    p = PaperCandidate(source="crossref", title="X", doi="10.1/abc", title_hash="h1")
    pid = repo.insert(p)
    assert repo.get_by_doi("10.1/abc").id == pid


def test_papers_lookup_by_title_hash(conn):
    repo = PapersRepo(conn)
    p = PaperCandidate(source="crossref", title="X", title_hash="h2")
    repo.insert(p)
    assert repo.get_by_title_hash("h2") is not None
    assert repo.get_by_title_hash("missing") is None


def test_papers_lookup_by_source_id(conn):
    repo = PapersRepo(conn)
    p = PaperCandidate(source="arxiv", source_id="2305.99999", title="X", title_hash="h3")
    repo.insert(p)
    assert repo.get_by_source_id("arxiv", "2305.99999") is not None


def test_runs_insert_and_get(conn):
    repo = RunsRepo(conn)
    summary = RunSummary(
        run_id="rid-1",
        started_at=datetime.now(timezone.utc).isoformat(),
        status="running",
    )
    repo.insert(summary, profile_slug="dtp-pmsm", schedule_mode="weekly")
    got = repo.get_by_run_id("rid-1")
    assert got["run_id"] == "rid-1"


def test_runs_update_summary(conn):
    repo = RunsRepo(conn)
    s = RunSummary(run_id="rid-1", started_at="2026-05-10T00:00:00+00:00", status="running")
    repo.insert(s, profile_slug="dtp-pmsm", schedule_mode="weekly")
    s.status = "success"
    s.raw_count = 10
    s.ended_at = "2026-05-10T00:01:00+00:00"
    repo.update_summary(s)
    got = repo.get_by_run_id("rid-1")
    assert got["status"] == "success"
    assert got["raw_count"] == 10


def test_filter_decisions_log(conn):
    repo = FilterDecisionsRepo(conn)
    repo.log(run_id="rid-1", paper_id=42, decision="reject", reason_code="missing_abstract", reason_text="no abstract")
    rows = repo.list_by_run("rid-1")
    assert len(rows) == 1
    assert rows[0]["reason_code"] == "missing_abstract"


def test_dedup_candidate_insert(conn):
    repo = DedupCandidatesRepo(conn)
    repo.insert(paper_id_a=1, paper_id_b=2, match_type="fuzzy_title", similarity=0.95)
    rows = repo.list_pending()
    assert len(rows) == 1
```

- [ ] **步骤 2：运行测试验证失败**

- [ ] **步骤 3：实现 `src/storage/repositories.py`**

```python
"""Repository layer over SQLite."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from src.models.paper import PaperCandidate
from src.models.run import RunSummary


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PapersRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def insert(self, p: PaperCandidate, status: str = "candidate") -> int:
        cur = self.conn.execute(
            """
            INSERT INTO papers (
                doi, title, normalized_title, title_hash, source, source_id,
                url, pdf_url, authors_json, venue, published_date, indexed_date,
                abstract, keywords_json, status, raw_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                p.doi, p.title, p.normalized_title, p.title_hash, p.source, p.source_id,
                p.url, p.pdf_url, json.dumps(p.authors), p.venue, p.published_date, p.indexed_date,
                p.abstract, json.dumps(p.keywords), status, json.dumps(p.raw), _now(), _now(),
            ),
        )
        return cur.lastrowid

    def get_by_doi(self, doi: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM papers WHERE doi = ?", (doi,)).fetchone()

    def get_by_title_hash(self, title_hash: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM papers WHERE title_hash = ?", (title_hash,)).fetchone()

    def get_by_source_id(self, source: str, source_id: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM papers WHERE source = ? AND source_id = ?", (source, source_id)
        ).fetchone()

    def list_by_run(self, run_id: str) -> list[sqlite3.Row]:
        # Note: papers don't carry run_id directly; we'd track via a join table in future MVPs.
        # For MVP1 we expose all-papers listing for reports.
        return self.conn.execute(
            "SELECT * FROM papers ORDER BY created_at DESC"
        ).fetchall()


class RunsRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def insert(self, s: RunSummary, profile_slug: str, schedule_mode: str) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO runs (
                run_id, profile_slug, schedule_mode, started_at, ended_at,
                status, sources_json, raw_count, normalized_count, deduped_count,
                filtered_count, failed_count, report_path, log_path, dry_run
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                s.run_id, profile_slug, schedule_mode, s.started_at, s.ended_at,
                s.status, json.dumps([sr.model_dump() for sr in s.sources]),
                s.raw_count, s.normalized_count, s.deduped_count,
                s.filtered_count, s.failed_count, s.report_path, s.log_path,
                1 if s.dry_run else 0,
            ),
        )
        return cur.lastrowid

    def update_summary(self, s: RunSummary) -> None:
        self.conn.execute(
            """
            UPDATE runs SET
                ended_at=?, status=?, sources_json=?, raw_count=?, normalized_count=?,
                deduped_count=?, filtered_count=?, failed_count=?, report_path=?, log_path=?
            WHERE run_id=?
            """,
            (
                s.ended_at, s.status, json.dumps([sr.model_dump() for sr in s.sources]),
                s.raw_count, s.normalized_count, s.deduped_count,
                s.filtered_count, s.failed_count, s.report_path, s.log_path, s.run_id,
            ),
        )

    def get_by_run_id(self, run_id: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()


class FilterDecisionsRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def log(self, run_id: str, paper_id: int | None, decision: str,
            reason_code: str | None, reason_text: str | None) -> None:
        self.conn.execute(
            """
            INSERT INTO filter_decisions (run_id, paper_id, decision, reason_code, reason_text, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, paper_id, decision, reason_code, reason_text, _now()),
        )

    def list_by_run(self, run_id: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM filter_decisions WHERE run_id = ? ORDER BY id",
            (run_id,),
        ).fetchall()


class DedupCandidatesRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def insert(self, paper_id_a: int, paper_id_b: int, match_type: str, similarity: float) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO dedup_candidates (paper_id_a, paper_id_b, match_type, similarity, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?)
            """,
            (paper_id_a, paper_id_b, match_type, similarity, _now()),
        )
        return cur.lastrowid

    def list_pending(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM dedup_candidates WHERE status='pending' ORDER BY id"
        ).fetchall()
```

- [ ] **步骤 4：运行测试 + Commit**

```bash
uv run pytest tests/unit/test_repositories.py -v
git add src/storage/repositories.py tests/unit/test_repositories.py
git commit -m "feat(storage): Repository 层（PapersRepo/RunsRepo/FilterDecisionsRepo/DedupCandidatesRepo）"
```

**Gate G2**：T2-T9 完成。reviewer 审单测覆盖率与 spec 一致性。

---

### 任务 10：Normalizer（字段统一）

**Owner：** coder | **Reviewer：** G3 时审 | **BlockedBy：** T5, T7

**文件：**
- 创建：`src/normalize/normalizer.py`
- 测试：`tests/unit/test_normalizer.py`

- [ ] **步骤 1：写测试 `tests/unit/test_normalizer.py`**

```python
from src.models.paper import PaperCandidate
from src.normalize.normalizer import normalize_paper


def test_normalize_paper_fills_title_hash_and_normalized():
    p = PaperCandidate(source="crossref", title="Dual Three-Phase PMSM!")
    out = normalize_paper(p)
    assert out.normalized_title == "dual three-phase pmsm"
    assert out.title_hash is not None
    assert len(out.title_hash) == 16


def test_normalize_paper_lowercase_doi():
    p = PaperCandidate(source="crossref", title="x", doi="10.1109/TIE.2024.123ABC")
    out = normalize_paper(p)
    assert out.doi == "10.1109/tie.2024.123abc"


def test_normalize_paper_strips_doi_url_prefix():
    p = PaperCandidate(source="crossref", title="x", doi="https://doi.org/10.1/abc")
    out = normalize_paper(p)
    assert out.doi == "10.1/abc"


def test_normalize_paper_strips_authors():
    p = PaperCandidate(source="crossref", title="x", authors=[" A. Author ", "  B. Author"])
    out = normalize_paper(p)
    assert out.authors == ["A. Author", "B. Author"]


def test_normalize_paper_idempotent():
    p = PaperCandidate(source="crossref", title="X")
    once = normalize_paper(p)
    twice = normalize_paper(once)
    assert once == twice
```

- [ ] **步骤 2：运行测试验证失败**

- [ ] **步骤 3：实现 `src/normalize/normalizer.py`**

```python
"""Paper field normalization.

Responsibilities:
- Lowercase DOI, strip URL prefix
- Compute normalized_title and title_hash
- Trim author whitespace
- Idempotent
"""
from __future__ import annotations

from src.models.paper import PaperCandidate
from src.normalize.title import normalize_title
from src.utils.hashing import title_hash as _title_hash


def _normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    s = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if s.startswith(prefix):
            s = s[len(prefix):]
    return s


def normalize_paper(p: PaperCandidate) -> PaperCandidate:
    return p.model_copy(update={
        "doi": _normalize_doi(p.doi),
        "normalized_title": normalize_title(p.title),
        "title_hash": _title_hash(p.title),
        "authors": [a.strip() for a in p.authors if a and a.strip()],
    })
```

- [ ] **步骤 4：运行测试 + Commit**

```bash
uv run pytest tests/unit/test_normalizer.py -v
git add src/normalize/normalizer.py tests/unit/test_normalizer.py
git commit -m "feat(normalize): 字段统一（DOI 小写/去前缀 + 标题归一化 + author trim）"
```

---

### 任务 11：Fetcher base + 共享 HTTP 客户端 + Crossref Fetcher

**Owner：** researcher → coder | **Reviewer：** G3 时审 | **BlockedBy：** T7

> **researcher 子代理调研要点**：Crossref REST API `/works` 端点；查询参数 `query.bibliographic`、`from-pub-date`、`until-pub-date`、`rows`、`mailto`；响应字段 `message.items[]`：`DOI/title[0]/author/container-title[0]/issued/abstract/URL/created`。

**文件：**
- 创建：`src/fetchers/__init__.py`（空）
- 创建：`src/fetchers/base.py`
- 创建：`src/fetchers/_http.py`
- 创建：`src/fetchers/crossref.py`
- 创建：`tests/fixtures/crossref/search_dtp_pmsm.json`（mock Crossref 响应）
- 创建：`tests/fixtures/crossref/empty_response.json`
- 测试：`tests/unit/test_fetcher_crossref.py`

- [ ] **步骤 1：写 fixture `tests/fixtures/crossref/search_dtp_pmsm.json`**

```json
{
  "status": "ok",
  "message-type": "work-list",
  "message": {
    "total-results": 2,
    "items": [
      {
        "DOI": "10.1109/TIE.2024.001",
        "title": ["Harmonic current suppression for dual three-phase PMSM"],
        "author": [{"given": "A.", "family": "Author"}, {"given": "B.", "family": "Author"}],
        "container-title": ["IEEE Transactions on Industrial Electronics"],
        "issued": {"date-parts": [[2024, 3, 15]]},
        "created": {"date-time": "2024-03-20T00:00:00Z"},
        "abstract": "<jats:p>This paper proposes a method for harmonic current suppression in dual three-phase PMSM drives.</jats:p>",
        "URL": "https://doi.org/10.1109/TIE.2024.001"
      },
      {
        "DOI": "10.1109/TPEL.2024.002",
        "title": ["Vector space decomposition for multiphase motors"],
        "author": [{"given": "C.", "family": "Researcher"}],
        "container-title": ["IEEE Transactions on Power Electronics"],
        "issued": {"date-parts": [[2024, 5, 1]]},
        "created": {"date-time": "2024-05-05T00:00:00Z"},
        "URL": "https://doi.org/10.1109/TPEL.2024.002"
      }
    ]
  }
}
```

- [ ] **步骤 2：写 fixture `tests/fixtures/crossref/empty_response.json`**

```json
{"status": "ok", "message-type": "work-list", "message": {"total-results": 0, "items": []}}
```

- [ ] **步骤 3：写测试 `tests/unit/test_fetcher_crossref.py`**

```python
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.fetchers.crossref import CrossrefFetcher

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "crossref"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_crossref_parse_response():
    fetcher = CrossrefFetcher(mailto="test@example.com")
    candidates = fetcher.parse_response(_load("search_dtp_pmsm.json"))
    assert len(candidates) == 2
    p1 = candidates[0]
    assert p1.source == "crossref"
    assert p1.doi == "10.1109/TIE.2024.001"
    assert p1.title.startswith("Harmonic current suppression")
    assert p1.authors == ["A. Author", "B. Author"]
    assert p1.venue == "IEEE Transactions on Industrial Electronics"
    assert p1.published_date == "2024-03-15"
    assert "harmonic current suppression" in (p1.abstract or "").lower()
    # JATS tags should be stripped
    assert "<jats:p>" not in (p1.abstract or "")


def test_crossref_parse_empty():
    fetcher = CrossrefFetcher()
    candidates = fetcher.parse_response(_load("empty_response.json"))
    assert candidates == []


def test_crossref_partial_date():
    payload = {
        "status": "ok",
        "message": {
            "items": [{
                "DOI": "10.1/x",
                "title": ["x"],
                "issued": {"date-parts": [[2024]]},
                "container-title": ["J"],
            }]
        }
    }
    candidates = CrossrefFetcher().parse_response(payload)
    assert candidates[0].published_date == "2024-01-01"


def test_crossref_fetch_uses_mock_http(httpx_mock):
    httpx_mock.add_response(
        url__startswith="https://api.crossref.org/works",
        json=_load("search_dtp_pmsm.json"),
    )
    fetcher = CrossrefFetcher(mailto="test@example.com")
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = datetime(2024, 12, 31, tzinfo=timezone.utc)
    result = fetcher.fetch(query="dual three-phase PMSM", start=start, end=end, max_results=10)
    assert result.raw_count == 2
    assert result.normalized_count == 2
    assert len(result.candidates) == 2


def test_crossref_fetch_handles_http_error(httpx_mock):
    httpx_mock.add_response(
        url__startswith="https://api.crossref.org/works",
        status_code=503,
    )
    fetcher = CrossrefFetcher()
    result = fetcher.fetch(
        query="x",
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 12, 31, tzinfo=timezone.utc),
        max_results=10,
    )
    assert len(result.errors) > 0
    assert result.candidates == []
```

- [ ] **步骤 4：运行测试验证失败**

- [ ] **步骤 5：实现 `src/fetchers/_http.py`**

```python
"""Shared HTTP client with sane defaults."""
from __future__ import annotations

import httpx


def make_client(timeout: float = 30.0, user_agent: str = "research-paper-agent-team/0.1") -> httpx.Client:
    return httpx.Client(
        timeout=timeout,
        headers={"User-Agent": user_agent, "Accept": "application/json"},
        follow_redirects=True,
    )
```

- [ ] **步骤 6：实现 `src/fetchers/base.py`**

```python
"""Fetcher abstract base + result DTO."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.models.paper import PaperCandidate


@dataclass
class FetchResult:
    source: str
    query: str
    raw_count: int = 0
    normalized_count: int = 0
    candidates: list[PaperCandidate] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    raw_payload: Any | None = None  # for dumping to data/raw/


class FetcherBase(ABC):
    source_name: str = "abstract"

    @abstractmethod
    def fetch(
        self,
        query: str,
        start: datetime,
        end: datetime,
        max_results: int,
    ) -> FetchResult: ...

    @abstractmethod
    def parse_response(self, payload: Any) -> list[PaperCandidate]: ...
```

- [ ] **步骤 7：实现 `src/fetchers/crossref.py`**

```python
"""Crossref REST API fetcher.

Endpoint: https://api.crossref.org/works
Docs: https://api.crossref.org/swagger-ui/index.html
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import structlog

from src.fetchers._http import make_client
from src.fetchers.base import FetcherBase, FetchResult
from src.models.paper import PaperCandidate

logger = structlog.get_logger(__name__)

_BASE_URL = "https://api.crossref.org/works"
_JATS_TAG = re.compile(r"<[^>]+>")


def _strip_jats(text: str) -> str:
    return _JATS_TAG.sub("", text).strip()


def _format_date_parts(date_parts: list[int] | None) -> str | None:
    if not date_parts:
        return None
    parts = list(date_parts) + [1, 1]  # pad to YMD
    y, m, d = parts[0], parts[1], parts[2]
    return f"{y:04d}-{m:02d}-{d:02d}"


def _author_name(a: dict[str, Any]) -> str:
    given = a.get("given", "").strip()
    family = a.get("family", "").strip()
    return f"{given} {family}".strip()


class CrossrefFetcher(FetcherBase):
    source_name = "crossref"

    def __init__(self, mailto: str | None = None, base_url: str = _BASE_URL) -> None:
        self.mailto = mailto
        self.base_url = base_url

    def parse_response(self, payload: dict[str, Any]) -> list[PaperCandidate]:
        items = (payload.get("message") or {}).get("items") or []
        out: list[PaperCandidate] = []
        for it in items:
            try:
                title_list = it.get("title") or []
                title = title_list[0] if title_list else ""
                if not title:
                    continue
                venue_list = it.get("container-title") or []
                venue = venue_list[0] if venue_list else None

                date_parts = (it.get("issued") or {}).get("date-parts") or [[]]
                published = _format_date_parts(date_parts[0]) if date_parts else None
                indexed_dt = (it.get("created") or {}).get("date-time")

                authors = [_author_name(a) for a in (it.get("author") or [])]
                abstract_raw = it.get("abstract")
                abstract = _strip_jats(abstract_raw) if abstract_raw else None

                out.append(PaperCandidate(
                    source=self.source_name,
                    source_id=it.get("DOI"),
                    doi=it.get("DOI"),
                    title=title,
                    authors=authors,
                    venue=venue,
                    published_date=published,
                    indexed_date=indexed_dt,
                    abstract=abstract,
                    url=it.get("URL"),
                    raw=it,
                ))
            except Exception as e:
                logger.warning("crossref_parse_item_failed", error=str(e), item_doi=it.get("DOI"))
        return out

    def fetch(
        self,
        query: str,
        start: datetime,
        end: datetime,
        max_results: int,
    ) -> FetchResult:
        result = FetchResult(source=self.source_name, query=query)
        params: dict[str, Any] = {
            "query.bibliographic": query,
            "from-pub-date": start.strftime("%Y-%m-%d"),
            "until-pub-date": end.strftime("%Y-%m-%d"),
            "rows": min(max_results, 1000),
            "sort": "issued",
            "order": "desc",
        }
        if self.mailto:
            params["mailto"] = self.mailto

        try:
            with make_client() as client:
                resp = client.get(self.base_url, params=params)
                resp.raise_for_status()
                payload = resp.json()
                result.raw_payload = payload
                items = (payload.get("message") or {}).get("items") or []
                result.raw_count = len(items)
                result.candidates = self.parse_response(payload)
                result.normalized_count = len(result.candidates)
        except Exception as e:
            logger.error("crossref_fetch_failed", error=str(e), query=query)
            result.errors.append(f"crossref: {type(e).__name__}: {e}")
        return result
```

- [ ] **步骤 8：运行测试 + Commit**

```bash
uv run pytest tests/unit/test_fetcher_crossref.py -v
git add src/fetchers/ tests/fixtures/crossref/ tests/unit/test_fetcher_crossref.py
git commit -m "feat(fetcher): Crossref fetcher（解析 + httpx 调用 + mock fixture 测试）"
```

---

### 任务 12：arXiv Fetcher

**Owner：** researcher → coder | **Reviewer：** G3 时审 | **BlockedBy：** T11

> **researcher 子代理调研要点**：arXiv API 端点 `http://export.arxiv.org/api/query`；查询参数 `search_query`（含 `cat:eess.SY`）、`start`、`max_results`、`sortBy=submittedDate`；返回 Atom XML，使用 `feedparser` 解析，关键字段 `entry.id/title/summary/published/updated/author/arxiv:primary_category/link`。

**文件：**
- 创建：`src/fetchers/arxiv.py`
- 创建：`tests/fixtures/arxiv/search_motor_control.xml`
- 创建：`tests/fixtures/arxiv/empty_response.xml`
- 测试：`tests/unit/test_fetcher_arxiv.py`

- [ ] **步骤 1：写 fixture `tests/fixtures/arxiv/search_motor_control.xml`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <title>arXiv Query: motor control</title>
  <id>http://arxiv.org/api/query?search_query=motor+control</id>
  <updated>2026-05-10T00:00:00Z</updated>
  <opensearch:totalResults xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">2</opensearch:totalResults>
  <entry>
    <id>http://arxiv.org/abs/2503.12345v1</id>
    <updated>2025-03-15T12:00:00Z</updated>
    <published>2025-03-15T12:00:00Z</published>
    <title>Neural network based parameter identification for PMSM</title>
    <summary>We propose a tiny neural network for online parameter identification of permanent magnet synchronous motors.</summary>
    <author><name>Alice Author</name></author>
    <author><name>Bob Researcher</name></author>
    <arxiv:primary_category term="eess.SY"/>
    <link rel="alternate" type="text/html" href="http://arxiv.org/abs/2503.12345v1"/>
    <link rel="related" title="pdf" type="application/pdf" href="http://arxiv.org/pdf/2503.12345v1"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2504.99999v2</id>
    <updated>2025-04-20T08:00:00Z</updated>
    <published>2025-04-18T08:00:00Z</published>
    <title>Sliding mode observer for multiphase machines</title>
    <summary>An extended sliding mode observer is presented for multiphase PMSM drives.</summary>
    <author><name>Charlie Engineer</name></author>
    <arxiv:primary_category term="eess.SY"/>
    <link rel="alternate" type="text/html" href="http://arxiv.org/abs/2504.99999v2"/>
  </entry>
</feed>
```

- [ ] **步骤 2：写 fixture `tests/fixtures/arxiv/empty_response.xml`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
  <opensearch:totalResults>0</opensearch:totalResults>
</feed>
```

- [ ] **步骤 3：写测试 `tests/unit/test_fetcher_arxiv.py`**

```python
from datetime import datetime, timezone
from pathlib import Path

from src.fetchers.arxiv import ArxivFetcher

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "arxiv"


def test_arxiv_parse_response():
    payload = (FIXTURES / "search_motor_control.xml").read_text(encoding="utf-8")
    candidates = ArxivFetcher().parse_response(payload)
    assert len(candidates) == 2
    p = candidates[0]
    assert p.source == "arxiv"
    assert p.source_id == "2503.12345"  # version stripped
    assert p.title.startswith("Neural network based")
    assert p.authors == ["Alice Author", "Bob Researcher"]
    assert p.published_date == "2025-03-15"
    assert p.url == "http://arxiv.org/abs/2503.12345v1"
    assert p.pdf_url == "http://arxiv.org/pdf/2503.12345v1"
    assert "neural network" in (p.abstract or "").lower()


def test_arxiv_parse_empty():
    payload = (FIXTURES / "empty_response.xml").read_text(encoding="utf-8")
    assert ArxivFetcher().parse_response(payload) == []


def test_arxiv_strips_version_suffix():
    p = ArxivFetcher().parse_response(
        (FIXTURES / "search_motor_control.xml").read_text(encoding="utf-8")
    )[1]
    assert p.source_id == "2504.99999"  # v2 stripped


def test_arxiv_fetch_with_mock(httpx_mock):
    payload = (FIXTURES / "search_motor_control.xml").read_text(encoding="utf-8")
    httpx_mock.add_response(
        url__startswith="http://export.arxiv.org/api/query",
        text=payload,
        headers={"content-type": "application/atom+xml"},
    )
    result = ArxivFetcher().fetch(
        query="motor control",
        start=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end=datetime(2025, 12, 31, tzinfo=timezone.utc),
        max_results=10,
    )
    assert result.raw_count == 2
    assert result.normalized_count == 2


def test_arxiv_fetch_handles_error(httpx_mock):
    httpx_mock.add_response(
        url__startswith="http://export.arxiv.org/api/query",
        status_code=500,
    )
    result = ArxivFetcher().fetch(
        query="x",
        start=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end=datetime(2025, 12, 31, tzinfo=timezone.utc),
        max_results=10,
    )
    assert len(result.errors) > 0
```

- [ ] **步骤 4：运行测试验证失败**

- [ ] **步骤 5：实现 `src/fetchers/arxiv.py`**

```python
"""arXiv API fetcher.

Endpoint: http://export.arxiv.org/api/query
Returns Atom XML; parsed via feedparser.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import feedparser
import structlog

from src.fetchers._http import make_client
from src.fetchers.base import FetcherBase, FetchResult
from src.models.paper import PaperCandidate

logger = structlog.get_logger(__name__)

_BASE_URL = "http://export.arxiv.org/api/query"
_VERSION_SUFFIX = re.compile(r"v\d+$")


def _strip_version(arxiv_id: str) -> str:
    """Convert '2503.12345v1' or 'http://arxiv.org/abs/2503.12345v1' -> '2503.12345'."""
    short = arxiv_id.rsplit("/", 1)[-1]
    return _VERSION_SUFFIX.sub("", short)


class ArxivFetcher(FetcherBase):
    source_name = "arxiv"

    def __init__(self, base_url: str = _BASE_URL) -> None:
        self.base_url = base_url

    def parse_response(self, payload: str) -> list[PaperCandidate]:
        feed = feedparser.parse(payload)
        out: list[PaperCandidate] = []
        for entry in feed.entries:
            try:
                arxiv_id = _strip_version(entry.id)
                published = entry.get("published", "")[:10] or None  # YYYY-MM-DD

                authors = [a.name.strip() for a in entry.get("authors", []) if getattr(a, "name", "").strip()]

                pdf_url = None
                html_url = None
                for link in entry.get("links", []):
                    if link.get("type") == "application/pdf":
                        pdf_url = link.get("href")
                    elif link.get("rel") == "alternate":
                        html_url = link.get("href")

                title = (entry.get("title") or "").strip()
                if not title:
                    continue

                out.append(PaperCandidate(
                    source=self.source_name,
                    source_id=arxiv_id,
                    doi=f"10.48550/arXiv.{arxiv_id}",
                    title=title,
                    authors=authors,
                    venue="arXiv",
                    published_date=published,
                    indexed_date=entry.get("updated", "")[:19] or None,
                    abstract=(entry.get("summary") or "").strip() or None,
                    url=html_url or entry.id,
                    pdf_url=pdf_url,
                    raw={k: v for k, v in entry.items() if isinstance(v, (str, int, float, bool, list, dict))},
                ))
            except Exception as e:
                logger.warning("arxiv_parse_entry_failed", error=str(e), entry_id=entry.get("id"))
        return out

    def fetch(
        self,
        query: str,
        start: datetime,
        end: datetime,
        max_results: int,
    ) -> FetchResult:
        result = FetchResult(source=self.source_name, query=query)
        params = {
            "search_query": query,
            "start": 0,
            "max_results": min(max_results, 2000),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        try:
            with make_client() as client:
                resp = client.get(self.base_url, params=params)
                resp.raise_for_status()
                payload = resp.text
                result.raw_payload = payload
                feed = feedparser.parse(payload)
                result.raw_count = len(feed.entries)
                result.candidates = self.parse_response(payload)
                # Filter by published date
                result.candidates = [
                    p for p in result.candidates
                    if p.published_date is None
                    or (start.strftime("%Y-%m-%d") <= p.published_date <= end.strftime("%Y-%m-%d"))
                ]
                result.normalized_count = len(result.candidates)
        except Exception as e:
            logger.error("arxiv_fetch_failed", error=str(e), query=query)
            result.errors.append(f"arxiv: {type(e).__name__}: {e}")
        return result
```

- [ ] **步骤 6：运行测试 + Commit**

```bash
uv run pytest tests/unit/test_fetcher_arxiv.py -v
git add src/fetchers/arxiv.py tests/fixtures/arxiv/ tests/unit/test_fetcher_arxiv.py
git commit -m "feat(fetcher): arXiv fetcher（feedparser 解析 + 版本号剥离 + 日期过滤）"
```

**Gate G3**：T10-T12 完成。reviewer 检查两个 fetcher 输出 PaperCandidate 字段一致性。

---

### 任务 13：Hard Deduplicator

**Owner：** coder | **Reviewer：** G4 时审 | **BlockedBy：** T9, T10

**文件：**
- 创建：`src/dedupe/__init__.py`（空）
- 创建：`src/dedupe/hard.py`
- 测试：`tests/unit/test_dedupe_hard.py`

- [ ] **步骤 1：写测试 `tests/unit/test_dedupe_hard.py`**

```python
from src.models.paper import PaperCandidate
from src.dedupe.hard import find_hard_duplicate_key, dedupe_hard


def test_find_hard_key_doi():
    p = PaperCandidate(source="crossref", title="x", doi="10.1/abc")
    assert find_hard_duplicate_key(p) == ("doi", "10.1/abc")


def test_find_hard_key_arxiv_source_id():
    p = PaperCandidate(source="arxiv", title="x", source_id="2503.12345")
    assert find_hard_duplicate_key(p) == ("source_id", "arxiv:2503.12345")


def test_find_hard_key_none():
    p = PaperCandidate(source="rss", title="x")
    assert find_hard_duplicate_key(p) is None


def test_dedupe_hard_removes_doi_duplicates():
    p1 = PaperCandidate(source="crossref", title="x", doi="10.1/abc")
    p2 = PaperCandidate(source="arxiv", title="y", doi="10.1/abc")  # 同 DOI
    p3 = PaperCandidate(source="crossref", title="z", doi="10.2/xyz")
    unique, dup_pairs = dedupe_hard([p1, p2, p3])
    assert len(unique) == 2
    assert len(dup_pairs) == 1


def test_dedupe_hard_keeps_first_occurrence():
    p1 = PaperCandidate(source="crossref", title="first", doi="10.1/abc")
    p2 = PaperCandidate(source="arxiv", title="second", doi="10.1/abc")
    unique, _ = dedupe_hard([p1, p2])
    assert unique[0].title == "first"
```

- [ ] **步骤 2：运行测试验证失败**

- [ ] **步骤 3：实现 `src/dedupe/hard.py`**

```python
"""Hard deduplication based on stable IDs (DOI / arXiv ID / source-specific ID)."""
from __future__ import annotations

from src.models.paper import PaperCandidate

HardKey = tuple[str, str]


def find_hard_duplicate_key(p: PaperCandidate) -> HardKey | None:
    """Return a stable identity key for a paper, or None if no hard ID is available."""
    if p.doi:
        return ("doi", p.doi.lower())
    if p.source and p.source_id:
        return ("source_id", f"{p.source}:{p.source_id}")
    return None


def dedupe_hard(
    papers: list[PaperCandidate],
) -> tuple[list[PaperCandidate], list[tuple[PaperCandidate, PaperCandidate, str]]]:
    """Return (unique_list, dup_pairs).

    - First occurrence wins.
    - Papers without a hard key pass through unchanged.
    - dup_pairs are (kept, dropped, match_type) for logging/audit.
    """
    seen: dict[HardKey, PaperCandidate] = {}
    unique: list[PaperCandidate] = []
    dups: list[tuple[PaperCandidate, PaperCandidate, str]] = []

    for p in papers:
        key = find_hard_duplicate_key(p)
        if key is None:
            unique.append(p)
            continue
        if key in seen:
            dups.append((seen[key], p, key[0]))
        else:
            seen[key] = p
            unique.append(p)
    return unique, dups
```

- [ ] **步骤 4：运行测试 + Commit**

```bash
uv run pytest tests/unit/test_dedupe_hard.py -v
git add src/dedupe/__init__.py src/dedupe/hard.py tests/unit/test_dedupe_hard.py
git commit -m "feat(dedupe): 硬去重（DOI / source_id 自动合并）"
```

---

### 任务 14：Soft Deduplicator + Deduplicator 编排

**Owner：** coder | **Reviewer：** G4 时审 | **BlockedBy：** T13

**文件：**
- 创建：`src/dedupe/soft.py`
- 创建：`src/dedupe/deduplicator.py`
- 测试：`tests/unit/test_dedupe_soft.py`、`tests/unit/test_deduplicator.py`

- [ ] **步骤 1：写测试 `tests/unit/test_dedupe_soft.py`**

```python
from src.models.paper import PaperCandidate
from src.normalize.normalizer import normalize_paper
from src.dedupe.soft import find_soft_matches


def _make(title: str, authors: list[str] | None = None, year: str | None = "2024") -> PaperCandidate:
    return normalize_paper(PaperCandidate(
        source="crossref", title=title, authors=authors or [],
        published_date=f"{year}-01-01" if year else None,
    ))


def test_title_hash_match():
    p1 = _make("Harmonic Current Suppression")
    p2 = _make("harmonic current suppression!")  # 大小写/标点不同 → hash 相同
    matches = find_soft_matches([p1, p2], threshold=90.0)
    assert len(matches) == 1
    assert matches[0].match_type == "title_hash"


def test_fuzzy_title_match():
    p1 = _make("Harmonic current suppression in dual three-phase PMSM drives")
    p2 = _make("Harmonic current suppression in dual three-phase PMSM drive")  # 缺一个 s
    matches = find_soft_matches([p1, p2], threshold=90.0)
    assert len(matches) == 1
    assert matches[0].match_type == "fuzzy_title"


def test_no_match_below_threshold():
    p1 = _make("Topic A")
    p2 = _make("Topic B")
    matches = find_soft_matches([p1, p2], threshold=90.0)
    assert matches == []


def test_title_author_year_match():
    p1 = _make("Some title", authors=["A. Author"], year="2024")
    p2 = _make("Some title with extra words really different", authors=["A. Author"], year="2024")
    # 即使 fuzzy title 不够高，title-prefix + author + year 也算 soft match
    matches = find_soft_matches([p1, p2], threshold=85.0, title_author_year=True)
    # 此用例下 fuzzy 也可能命中；具体看实现，但至少不为空
    assert len(matches) >= 1
```

- [ ] **步骤 2：写测试 `tests/unit/test_deduplicator.py`**

```python
import pytest

from src.models.paper import PaperCandidate
from src.normalize.normalizer import normalize_paper
from src.storage.db import open_db, apply_migrations
from src.storage.repositories import PapersRepo, DedupCandidatesRepo
from src.dedupe.deduplicator import deduplicate


@pytest.fixture
def conn(tmp_path):
    c = open_db(tmp_path / "t.db")
    apply_migrations(c)
    yield c
    c.close()


def _norm(title: str, **kw) -> PaperCandidate:
    return normalize_paper(PaperCandidate(source="crossref", title=title, **kw))


def test_deduplicate_hard_removes_duplicates(conn):
    papers = [
        _norm("X", doi="10.1/a"),
        _norm("X", doi="10.1/a"),  # hard dup
        _norm("Y", doi="10.2/b"),
    ]
    result = deduplicate(papers, conn=conn)
    assert len(result.unique) == 2


def test_deduplicate_soft_writes_candidates(conn):
    p1 = _norm("Harmonic Current Suppression in PMSM")
    p2 = _norm("harmonic current suppression in pmsm")  # 同 title_hash
    PapersRepo(conn).insert(p1)
    PapersRepo(conn).insert(p2)
    result = deduplicate([p1, p2], conn=conn)
    # soft match 写入 dedup_candidates
    candidates = DedupCandidatesRepo(conn).list_pending()
    assert len(candidates) >= 1
```

- [ ] **步骤 3：运行测试验证失败**

- [ ] **步骤 4：实现 `src/dedupe/soft.py`**

```python
"""Soft deduplication via title hash, fuzzy title match, and (title, author, year) combinations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from rapidfuzz import fuzz

from src.models.paper import PaperCandidate


@dataclass(frozen=True)
class SoftMatch:
    idx_a: int
    idx_b: int
    match_type: Literal["title_hash", "fuzzy_title", "title_author_year"]
    similarity: float


def _first_author_lastname(authors: list[str]) -> str | None:
    if not authors:
        return None
    return authors[0].split()[-1].lower()


def _year(date: str | None) -> str | None:
    return date[:4] if date and len(date) >= 4 else None


def find_soft_matches(
    papers: list[PaperCandidate],
    threshold: float = 90.0,
    title_author_year: bool = True,
) -> list[SoftMatch]:
    matches: list[SoftMatch] = []
    n = len(papers)
    for i in range(n):
        a = papers[i]
        for j in range(i + 1, n):
            b = papers[j]
            # 1. title_hash 完全匹配
            if a.title_hash and b.title_hash and a.title_hash == b.title_hash:
                matches.append(SoftMatch(i, j, "title_hash", 100.0))
                continue
            # 2. fuzzy title
            if a.normalized_title and b.normalized_title:
                sim = fuzz.token_set_ratio(a.normalized_title, b.normalized_title)
                if sim >= threshold:
                    matches.append(SoftMatch(i, j, "fuzzy_title", float(sim)))
                    continue
            # 3. title prefix + first author lastname + year
            if title_author_year:
                la = _first_author_lastname(a.authors)
                lb = _first_author_lastname(b.authors)
                ya = _year(a.published_date)
                yb = _year(b.published_date)
                if la and lb and la == lb and ya and yb and ya == yb:
                    if a.normalized_title and b.normalized_title:
                        prefix_sim = fuzz.partial_ratio(
                            a.normalized_title[:40], b.normalized_title[:40]
                        )
                        if prefix_sim >= 80:
                            matches.append(SoftMatch(i, j, "title_author_year", float(prefix_sim)))
    return matches
```

- [ ] **步骤 5：实现 `src/dedupe/deduplicator.py`**

```python
"""Deduplication orchestrator.

- Hard dedup: auto-merge based on DOI / source_id (in-memory list).
- Soft dedup: emit dedup_candidates rows to SQLite for manual review.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import structlog

from src.dedupe.hard import dedupe_hard
from src.dedupe.soft import find_soft_matches
from src.models.paper import PaperCandidate
from src.storage.repositories import DedupCandidatesRepo, PapersRepo

logger = structlog.get_logger(__name__)


@dataclass
class DedupeOutcome:
    unique: list[PaperCandidate]
    hard_dup_count: int
    soft_match_count: int


def deduplicate(
    papers: list[PaperCandidate],
    conn: sqlite3.Connection | None = None,
    soft_threshold: float = 90.0,
) -> DedupeOutcome:
    unique, hard_dups = dedupe_hard(papers)

    soft_matches = find_soft_matches(unique, threshold=soft_threshold)

    if conn is not None and soft_matches:
        papers_repo = PapersRepo(conn)
        dedup_repo = DedupCandidatesRepo(conn)
        for m in soft_matches:
            a = unique[m.idx_a]
            b = unique[m.idx_b]
            # Look up DB rows; skip if either side not yet persisted
            row_a = (a.doi and papers_repo.get_by_doi(a.doi)) or (
                a.title_hash and papers_repo.get_by_title_hash(a.title_hash)
            )
            row_b = (b.doi and papers_repo.get_by_doi(b.doi)) or (
                b.title_hash and papers_repo.get_by_title_hash(b.title_hash)
            )
            if row_a and row_b and row_a["id"] != row_b["id"]:
                dedup_repo.insert(
                    paper_id_a=row_a["id"],
                    paper_id_b=row_b["id"],
                    match_type=m.match_type,
                    similarity=m.similarity,
                )

    logger.info(
        "dedup_done",
        in_count=len(papers),
        unique=len(unique),
        hard_dups=len(hard_dups),
        soft_matches=len(soft_matches),
    )
    return DedupeOutcome(
        unique=unique,
        hard_dup_count=len(hard_dups),
        soft_match_count=len(soft_matches),
    )
```

- [ ] **步骤 6：运行测试 + Commit**

```bash
uv run pytest tests/unit/test_dedupe_soft.py tests/unit/test_deduplicator.py -v
git add src/dedupe/soft.py src/dedupe/deduplicator.py tests/unit/test_dedupe_soft.py tests/unit/test_deduplicator.py
git commit -m "feat(dedupe): 软去重（title_hash / fuzzy / title-author-year）+ 编排器"
```

---

### 任务 15：Rule Filter

**Owner：** coder | **Reviewer：** G4 时审 | **BlockedBy：** T6, T9

**文件：**
- 创建：`src/filter/__init__.py`（空）
- 创建：`src/filter/rule_filter.py`
- 测试：`tests/unit/test_rule_filter.py`

- [ ] **步骤 1：写测试 `tests/unit/test_rule_filter.py`**

```python
import pytest

from src.config import RuleFilterSpec
from src.models.paper import PaperCandidate
from src.storage.db import open_db, apply_migrations
from src.storage.repositories import FilterDecisionsRepo
from src.filter.rule_filter import apply_rule_filter


@pytest.fixture
def conn(tmp_path):
    c = open_db(tmp_path / "t.db")
    apply_migrations(c)
    yield c
    c.close()


def _p(**kw) -> PaperCandidate:
    return PaperCandidate(source="crossref", title=kw.pop("title", "x"), **kw)


def test_rule_filter_passes_clean_paper(conn):
    spec = RuleFilterSpec(require_year_after=2018, require_abstract=True, blacklist_keywords=[])
    p = _p(title="ok", abstract="abs", published_date="2024-01-01")
    out = apply_rule_filter([p], spec=spec, conn=conn, run_id="r1", paper_ids=[1])
    assert len(out) == 1


def test_rule_filter_rejects_old_year(conn):
    spec = RuleFilterSpec(require_year_after=2018, require_abstract=False)
    p = _p(title="old", abstract="x", published_date="2010-01-01")
    out = apply_rule_filter([p], spec=spec, conn=conn, run_id="r1", paper_ids=[1])
    assert out == []
    decisions = FilterDecisionsRepo(conn).list_by_run("r1")
    assert decisions[0]["reason_code"] == "year_too_old"


def test_rule_filter_rejects_missing_abstract(conn):
    spec = RuleFilterSpec(require_year_after=None, require_abstract=True)
    p = _p(title="t", abstract=None, published_date="2024-01-01")
    out = apply_rule_filter([p], spec=spec, conn=conn, run_id="r1", paper_ids=[1])
    assert out == []
    decisions = FilterDecisionsRepo(conn).list_by_run("r1")
    assert decisions[0]["reason_code"] == "missing_abstract"


def test_rule_filter_blacklist_keyword(conn):
    spec = RuleFilterSpec(require_year_after=None, require_abstract=False, blacklist_keywords=["review article only"])
    p = _p(title="t", abstract="this is review article only no method", published_date="2024-01-01")
    out = apply_rule_filter([p], spec=spec, conn=conn, run_id="r1", paper_ids=[1])
    assert out == []
    decisions = FilterDecisionsRepo(conn).list_by_run("r1")
    assert decisions[0]["reason_code"] == "blacklist_keyword"


def test_rule_filter_logs_pass_too(conn):
    spec = RuleFilterSpec()
    p = _p(title="t", published_date="2024-01-01")
    apply_rule_filter([p], spec=spec, conn=conn, run_id="r1", paper_ids=[1])
    decisions = FilterDecisionsRepo(conn).list_by_run("r1")
    assert any(d["decision"] == "pass" for d in decisions)
```

- [ ] **步骤 2：运行测试验证失败**

- [ ] **步骤 3：实现 `src/filter/rule_filter.py`**

```python
"""Rule-based filter applied before LLM screening (which exists from MVP2)."""
from __future__ import annotations

import sqlite3

from src.config import RuleFilterSpec
from src.models.paper import PaperCandidate
from src.storage.repositories import FilterDecisionsRepo


def _year(date: str | None) -> int | None:
    if not date or len(date) < 4:
        return None
    try:
        return int(date[:4])
    except ValueError:
        return None


def _check(p: PaperCandidate, spec: RuleFilterSpec) -> tuple[str, str | None, str | None]:
    """Return (decision, reason_code, reason_text)."""
    if spec.require_year_after is not None:
        y = _year(p.published_date)
        if y is None or y < spec.require_year_after:
            return ("reject", "year_too_old", f"published_date={p.published_date} < {spec.require_year_after}")

    if spec.require_abstract and not (p.abstract and p.abstract.strip()):
        return ("reject", "missing_abstract", "abstract is empty or missing")

    if spec.blacklist_keywords:
        haystack = (p.title + " " + (p.abstract or "")).lower()
        for kw in spec.blacklist_keywords:
            if kw.lower() in haystack:
                return ("reject", "blacklist_keyword", f"matched: {kw}")

    return ("pass", None, None)


def apply_rule_filter(
    papers: list[PaperCandidate],
    spec: RuleFilterSpec,
    conn: sqlite3.Connection,
    run_id: str,
    paper_ids: list[int | None] | None = None,
) -> list[PaperCandidate]:
    """Apply spec; log every decision; return only papers that passed."""
    repo = FilterDecisionsRepo(conn)
    if paper_ids is None:
        paper_ids = [None] * len(papers)
    out: list[PaperCandidate] = []
    for p, pid in zip(papers, paper_ids, strict=True):
        decision, code, text = _check(p, spec)
        repo.log(run_id=run_id, paper_id=pid, decision=decision, reason_code=code, reason_text=text)
        if decision == "pass":
            out.append(p)
    return out
```

- [ ] **步骤 4：运行测试 + Commit**

```bash
uv run pytest tests/unit/test_rule_filter.py -v
git add src/filter/__init__.py src/filter/rule_filter.py tests/unit/test_rule_filter.py
git commit -m "feat(filter): Rule Filter（年份/摘要/黑名单）+ filter_decisions 全程记录"
```

**Gate G4**：T13-T15 完成。reviewer 检查软去重不会误合并、filter_decisions 既记 reject 也记 pass。

---

### 任务 16：Report Writer（Markdown + JSON）

**Owner：** coder | **Reviewer：** G5 时审 | **BlockedBy：** T7

**文件：**
- 创建：`src/reports/__init__.py`（空）
- 创建：`src/reports/templates/candidates.md.j2`
- 创建：`src/reports/templates/run_summary.md.j2`
- 创建：`src/reports/digest_writer.py`
- 测试：`tests/unit/test_report_writer.py`

- [ ] **步骤 1：写测试 `tests/unit/test_report_writer.py`**

```python
import json
from pathlib import Path

from src.models.paper import PaperCandidate
from src.models.run import RunSummary, SourceResult
from src.reports.digest_writer import write_candidates_report, write_run_summary_json


def _p(title: str, **kw) -> PaperCandidate:
    return PaperCandidate(source="crossref", title=title, **kw)


def test_write_candidates_md(tmp_path):
    out = tmp_path / "candidates.md"
    papers = [
        _p("Harmonic suppression", doi="10.1/a", venue="TIE", published_date="2024-03-15", abstract="x"),
        _p("VSD control", doi="10.2/b", venue="TPEL", published_date="2024-05-01"),
    ]
    write_candidates_report(papers, output=out, run_id="r1")
    text = out.read_text(encoding="utf-8")
    assert "# 论文查新候选清单" in text
    assert "r1" in text
    assert "Harmonic suppression" in text
    assert "10.1/a" in text


def test_write_candidates_md_empty(tmp_path):
    out = tmp_path / "candidates.md"
    write_candidates_report([], output=out, run_id="r1")
    text = out.read_text(encoding="utf-8")
    assert "本轮未发现候选论文" in text


def test_write_run_summary_json(tmp_path):
    out = tmp_path / "summary.json"
    s = RunSummary(
        run_id="r1", started_at="2026-05-10T00:00:00+00:00", status="success",
        sources=[SourceResult(source="crossref", query="x", raw_count=10, normalized_count=8)],
        raw_count=10, normalized_count=8, deduped_count=7, filtered_count=5,
    )
    write_run_summary_json(s, output=out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["run_id"] == "r1"
    assert data["sources"][0]["source"] == "crossref"
```

- [ ] **步骤 2：写模板 `src/reports/templates/candidates.md.j2`**

```jinja
# 论文查新候选清单

- **Run ID**：{{ run_id }}
- **生成时间**：{{ generated_at }}
- **候选数**：{{ papers | length }}

{% if not papers %}
本轮未发现候选论文。
{% else %}
{% for p in papers %}
## {{ loop.index }}. {{ p.title }}

- **来源**：{{ p.source }}{% if p.source_id %} (`{{ p.source_id }}`){% endif %}
- **DOI**：{% if p.doi %}`{{ p.doi }}`{% else %}—{% endif %}
- **期刊/会议**：{{ p.venue or "—" }}
- **发表日期**：{{ p.published_date or "—" }}
- **作者**：{% if p.authors %}{{ p.authors | join(", ") }}{% else %}—{% endif %}
- **链接**：{% if p.url %}<{{ p.url }}>{% else %}—{% endif %}

{% if p.abstract %}**摘要**：{{ p.abstract | truncate(500) }}{% endif %}

---
{% endfor %}
{% endif %}
```

- [ ] **步骤 3：写模板 `src/reports/templates/run_summary.md.j2`**

```jinja
# Run Summary — {{ summary.run_id }}

- **状态**：{{ summary.status }}
- **开始**：{{ summary.started_at }}
- **结束**：{{ summary.ended_at or "—" }}
- **Dry-run**：{{ "是" if summary.dry_run else "否" }}

## 计数

| 阶段 | 数量 |
|---|---:|
| Raw（原始） | {{ summary.raw_count }} |
| Normalized | {{ summary.normalized_count }} |
| Deduped | {{ summary.deduped_count }} |
| Filtered（通过 rule filter） | {{ summary.filtered_count }} |
| Failed | {{ summary.failed_count }} |

## 数据源

| 源 | 查询 | Raw | Normalized | 错误 |
|---|---|---:|---:|---|
{% for s in summary.sources %}| {{ s.source }} | {{ s.query }} | {{ s.raw_count }} | {{ s.normalized_count }} | {{ s.errors | length }} |
{% endfor %}

{% if summary.errors %}
## 错误

{% for e in summary.errors %}- {{ e }}
{% endfor %}
{% endif %}

## 报告路径

- Candidates report: `{{ summary.report_path or "—" }}`
- Log: `{{ summary.log_path or "—" }}`
```

- [ ] **步骤 4：实现 `src/reports/digest_writer.py`**

```python
"""Report rendering for MVP1 (candidates + run summary).

Future MVPs will extend this module with digest generation; for now it only
emits the deterministic Markdown/JSON outputs of MVP1.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.models.paper import PaperCandidate
from src.models.run import RunSummary

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(["md", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def write_candidates_report(
    papers: list[PaperCandidate],
    output: Path,
    run_id: str,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    tmpl = _env.get_template("candidates.md.j2")
    rendered = tmpl.render(
        papers=papers,
        run_id=run_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
    output.write_text(rendered, encoding="utf-8")


def write_run_summary_md(summary: RunSummary, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    tmpl = _env.get_template("run_summary.md.j2")
    output.write_text(tmpl.render(summary=summary), encoding="utf-8")


def write_run_summary_json(summary: RunSummary, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(summary.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
```

- [ ] **步骤 5：运行测试 + Commit**

```bash
uv run pytest tests/unit/test_report_writer.py -v
git add src/reports/ tests/unit/test_report_writer.py
git commit -m "feat(reports): Markdown candidates + run summary（MD + JSON）"
```

---

### 任务 17：Orchestrator（MVP1 pipeline）

**Owner：** coder | **Reviewer：** G5 时审 | **BlockedBy：** T6, T8, T9, T10, T11, T12, T14, T15, T16

**文件：**
- 创建：`src/orchestrator.py`
- 测试：`tests/integration/test_orchestrator.py`

- [ ] **步骤 1：写测试 `tests/integration/test_orchestrator.py`**

```python
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.config import AppConfig, ScheduleSection, WindowSection, LimitsSection, SourcesConfig, CrossrefSource, ArxivSource, QuerySpec, ResearchProfile, RuleFilterSpec
from src.fetchers.base import FetchResult
from src.models.paper import PaperCandidate
from src.orchestrator import run_mvp1_pipeline
from src.storage.db import open_db, apply_migrations
from src.storage.repositories import PapersRepo, RunsRepo, FilterDecisionsRepo


def _make_config() -> AppConfig:
    return AppConfig(
        schedule=ScheduleSection(enabled=False, mode="weekly", timezone="UTC"),
        window=WindowSection(daily_days=3, weekly_days=14, monthly_days=45),
        limits=LimitsSection(max_candidates_per_source=10, max_total_candidates=30, max_runtime_minutes=5),
        sources=SourcesConfig(
            crossref=CrossrefSource(enabled=True, queries=[QuerySpec(name="q1", query="x")], max_results=10),
            arxiv=ArxivSource(enabled=True, queries=[QuerySpec(name="q1", query="x")], max_results=10),
        ),
        profile=ResearchProfile(
            name="x", slug="dtp-pmsm", field="f",
            rule_filter=RuleFilterSpec(require_year_after=2018, require_abstract=False, blacklist_keywords=[]),
        ),
    )


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "papers.db"


@pytest.fixture
def data_dir(tmp_path):
    return tmp_path / "data"


def _stub_fetchers(monkeypatch):
    """Replace real fetchers with stubs returning canned PaperCandidate lists."""
    from src.fetchers import crossref as cr, arxiv as ax

    def crossref_fetch(self, query, start, end, max_results):
        return FetchResult(
            source="crossref", query=query, raw_count=2, normalized_count=2,
            candidates=[
                PaperCandidate(source="crossref", title="Crossref paper A", doi="10.1/a", abstract="x", published_date="2024-03-15"),
                PaperCandidate(source="crossref", title="Crossref paper B", doi="10.1/b", abstract="x", published_date="2024-04-15"),
            ],
        )

    def arxiv_fetch(self, query, start, end, max_results):
        return FetchResult(
            source="arxiv", query=query, raw_count=1, normalized_count=1,
            candidates=[
                PaperCandidate(source="arxiv", source_id="2503.99999", title="Arxiv paper A", doi="10.48550/arXiv.2503.99999", abstract="x", published_date="2024-05-15"),
            ],
        )

    monkeypatch.setattr(cr.CrossrefFetcher, "fetch", crossref_fetch)
    monkeypatch.setattr(ax.ArxivFetcher, "fetch", arxiv_fetch)


def test_pipeline_e2e(monkeypatch, db_path, data_dir):
    _stub_fetchers(monkeypatch)
    config = _make_config()
    summary = run_mvp1_pipeline(
        config=config,
        db_path=db_path,
        data_dir=data_dir,
        schedule_mode="weekly",
        dry_run=False,
    )
    assert summary.status in ("success", "partial")
    assert summary.raw_count == 3
    assert summary.normalized_count == 3
    assert summary.deduped_count >= 1

    conn = open_db(db_path)
    apply_migrations(conn)
    assert RunsRepo(conn).get_by_run_id(summary.run_id) is not None
    assert len(PapersRepo(conn).list_by_run(summary.run_id)) >= 1
    assert len(FilterDecisionsRepo(conn).list_by_run(summary.run_id)) >= 1
    conn.close()

    # Report files exist
    assert (data_dir / "reports" / summary.run_id / "candidates.md").exists()
    assert (data_dir / "reports" / summary.run_id / "summary.json").exists()


def test_pipeline_dry_run_does_not_write_db(monkeypatch, db_path, data_dir):
    _stub_fetchers(monkeypatch)
    config = _make_config()
    summary = run_mvp1_pipeline(
        config=config, db_path=db_path, data_dir=data_dir,
        schedule_mode="manual", dry_run=True,
    )
    # DB file may or may not exist; if it does, it must have no papers
    if db_path.exists():
        conn = open_db(db_path)
        apply_migrations(conn)
        assert RunsRepo(conn).get_by_run_id(summary.run_id) is None
        conn.close()
    # Reports go under _dryrun/
    assert (data_dir / "reports" / "_dryrun" / summary.run_id / "candidates.md").exists()


def test_pipeline_partial_when_one_source_fails(monkeypatch, db_path, data_dir):
    from src.fetchers import crossref as cr, arxiv as ax

    def crossref_fetch_fail(self, query, start, end, max_results):
        return FetchResult(source="crossref", query=query, raw_count=0, normalized_count=0,
                           candidates=[], errors=["crossref: 503"])

    def arxiv_fetch_ok(self, query, start, end, max_results):
        return FetchResult(source="arxiv", query=query, raw_count=1, normalized_count=1,
                           candidates=[PaperCandidate(source="arxiv", source_id="x", title="ok", abstract="a", published_date="2024-01-01")])

    monkeypatch.setattr(cr.CrossrefFetcher, "fetch", crossref_fetch_fail)
    monkeypatch.setattr(ax.ArxivFetcher, "fetch", arxiv_fetch_ok)

    config = _make_config()
    summary = run_mvp1_pipeline(
        config=config, db_path=db_path, data_dir=data_dir,
        schedule_mode="manual", dry_run=False,
    )
    assert summary.status == "partial"
```

- [ ] **步骤 2：运行测试验证失败**

- [ ] **步骤 3：实现 `src/orchestrator.py`**

```python
"""MVP1 pipeline orchestrator (deterministic, no LLM).

Pipeline:
  fetchers (Crossref + arXiv) → normalize → dedupe → rule_filter → SQLite + report
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

from src.config import AppConfig
from src.dedupe.deduplicator import deduplicate
from src.fetchers.arxiv import ArxivFetcher
from src.fetchers.base import FetchResult
from src.fetchers.crossref import CrossrefFetcher
from src.filter.rule_filter import apply_rule_filter
from src.models.paper import PaperCandidate
from src.models.run import RunSummary, SourceResult
from src.normalize.normalizer import normalize_paper
from src.reports.digest_writer import (
    write_candidates_report,
    write_run_summary_json,
    write_run_summary_md,
)
from src.storage.db import apply_migrations, open_db
from src.storage.repositories import PapersRepo, RunsRepo
from src.utils.runid import generate_run_id
from src.utils.time import compute_window

logger = structlog.get_logger(__name__)


def _data_subdir(data_dir: Path, run_id: str, dry_run: bool, kind: str) -> Path:
    base = data_dir / kind / ("_dryrun" if dry_run else "") / run_id
    # Cleaner: data/reports/_dryrun/{run_id}/ vs data/reports/{run_id}/
    if dry_run:
        base = data_dir / kind / "_dryrun" / run_id
    else:
        base = data_dir / kind / run_id
    base.mkdir(parents=True, exist_ok=True)
    return base


def _run_fetchers(config: AppConfig, start, end) -> tuple[list[PaperCandidate], list[SourceResult]]:
    all_candidates: list[PaperCandidate] = []
    source_results: list[SourceResult] = []

    if config.sources.crossref.enabled:
        mailto = os.environ.get(config.sources.crossref.mailto_env)
        cr = CrossrefFetcher(mailto=mailto)
        for q in config.sources.crossref.queries:
            res = cr.fetch(query=q.query, start=start, end=end,
                           max_results=config.sources.crossref.max_results)
            source_results.append(SourceResult(
                source="crossref", query=q.query,
                raw_count=res.raw_count, normalized_count=res.normalized_count,
                errors=res.errors,
            ))
            all_candidates.extend(res.candidates)

    if config.sources.arxiv.enabled:
        ax = ArxivFetcher()
        for q in config.sources.arxiv.queries:
            res = ax.fetch(query=q.query, start=start, end=end,
                           max_results=config.sources.arxiv.max_results)
            source_results.append(SourceResult(
                source="arxiv", query=q.query,
                raw_count=res.raw_count, normalized_count=res.normalized_count,
                errors=res.errors,
            ))
            all_candidates.extend(res.candidates)

    return all_candidates, source_results


def run_mvp1_pipeline(
    config: AppConfig,
    db_path: Path,
    data_dir: Path,
    schedule_mode: str = "manual",
    dry_run: bool = False,
    days: int | None = None,
) -> RunSummary:
    run_id = generate_run_id(profile_slug=config.profile.slug, schedule_mode=schedule_mode)
    started = datetime.now(timezone.utc).isoformat()

    if days is None:
        days = {"daily": config.window.daily_days, "weekly": config.window.weekly_days,
                "monthly": config.window.monthly_days}.get(schedule_mode, config.window.weekly_days)
    window_start, window_end = compute_window(days=days)

    summary = RunSummary(
        run_id=run_id, started_at=started, status="running", dry_run=dry_run,
    )

    log = logger.bind(run_id=run_id, dry_run=dry_run)
    log.info("pipeline_start", schedule_mode=schedule_mode, days=days)

    # 1. Fetch
    candidates, source_results = _run_fetchers(config, window_start, window_end)
    summary.sources = source_results
    summary.raw_count = sum(s.raw_count for s in source_results)

    # 2. Normalize
    candidates = [normalize_paper(p) for p in candidates]
    summary.normalized_count = len(candidates)

    # 3. Dedup (in-memory hard; soft writes to DB if not dry-run)
    if not dry_run:
        conn = open_db(db_path)
        apply_migrations(conn)
        # Insert papers first so dedup soft can reference paper_ids
        papers_repo = PapersRepo(conn)
        paper_ids: list[int | None] = []
        for p in candidates:
            existing = (
                (p.doi and papers_repo.get_by_doi(p.doi))
                or (p.title_hash and papers_repo.get_by_title_hash(p.title_hash))
                or (p.source_id and papers_repo.get_by_source_id(p.source, p.source_id))
            )
            if existing:
                paper_ids.append(existing["id"])
            else:
                paper_ids.append(papers_repo.insert(p))

        outcome = deduplicate(candidates, conn=conn)
        summary.deduped_count = len(outcome.unique)
    else:
        outcome = deduplicate(candidates, conn=None)
        summary.deduped_count = len(outcome.unique)
        paper_ids = [None] * len(outcome.unique)
        conn = None

    # 4. Rule Filter
    if conn is not None:
        # Re-derive paper_ids for the deduped subset (by DOI / source_id / title_hash lookup)
        papers_repo = PapersRepo(conn)
        deduped_ids: list[int | None] = []
        for p in outcome.unique:
            existing = (
                (p.doi and papers_repo.get_by_doi(p.doi))
                or (p.title_hash and papers_repo.get_by_title_hash(p.title_hash))
            )
            deduped_ids.append(existing["id"] if existing else None)
        passed = apply_rule_filter(
            outcome.unique, spec=config.profile.rule_filter,
            conn=conn, run_id=run_id, paper_ids=deduped_ids,
        )
    else:
        # dry-run: no DB writes
        from sqlite3 import connect as _connect
        tmp_conn = _connect(":memory:")
        apply_migrations(tmp_conn)
        passed = apply_rule_filter(
            outcome.unique, spec=config.profile.rule_filter,
            conn=tmp_conn, run_id=run_id, paper_ids=[None] * len(outcome.unique),
        )
        tmp_conn.close()

    summary.filtered_count = len(passed)

    # 5. Reports
    reports_dir = _data_subdir(data_dir, run_id, dry_run, "reports")
    candidates_path = reports_dir / "candidates.md"
    summary_md_path = reports_dir / "summary.md"
    summary_json_path = reports_dir / "summary.json"

    write_candidates_report(passed, output=candidates_path, run_id=run_id)
    summary.report_path = str(candidates_path)
    summary.ended_at = datetime.now(timezone.utc).isoformat()

    has_source_errors = any(s.errors for s in source_results)
    summary.status = "partial" if has_source_errors else "success"

    write_run_summary_md(summary, output=summary_md_path)
    write_run_summary_json(summary, output=summary_json_path)

    # 6. Persist run row
    if not dry_run and conn is not None:
        runs_repo = RunsRepo(conn)
        runs_repo.insert(summary, profile_slug=config.profile.slug, schedule_mode=schedule_mode)
        runs_repo.update_summary(summary)
        conn.close()

    log.info("pipeline_done", status=summary.status, filtered=summary.filtered_count)
    return summary
```

- [ ] **步骤 4：运行测试 + Commit**

```bash
uv run pytest tests/integration/test_orchestrator.py -v
git add src/orchestrator.py tests/integration/test_orchestrator.py
git commit -m "feat(orchestrator): MVP1 pipeline（fetch→normalize→dedupe→filter→report）含 dry-run 与 partial"
```

**Gate G5**：T16-T17 完成。reviewer 必查 dry-run 不写库、partial 状态触发条件、报告路径正确。

---

### 任务 18：CLI（typer）

**Owner：** coder | **Reviewer：** G6 时审 | **BlockedBy：** T6, T8, T17

**文件：**
- 创建：`src/main.py`
- 测试：`tests/integration/test_cli.py`

- [ ] **步骤 1：写测试 `tests/integration/test_cli.py`**

```python
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.main import app

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "db-init" in result.stdout
    assert "discover" in result.stdout
    assert "run" in result.stdout


def test_cli_db_init(tmp_path):
    db = tmp_path / "papers.db"
    result = runner.invoke(app, ["db-init", "--db-path", str(db)])
    assert result.exit_code == 0
    assert db.exists()


def test_cli_discover_dry_run(tmp_path, monkeypatch):
    # Stub fetchers to avoid real network calls
    from src.fetchers import crossref as cr, arxiv as ax
    from src.fetchers.base import FetchResult

    def stub(self, query, start, end, max_results):
        return FetchResult(source=self.source_name, query=query, raw_count=0, normalized_count=0)

    monkeypatch.setattr(cr.CrossrefFetcher, "fetch", stub)
    monkeypatch.setattr(ax.ArxivFetcher, "fetch", stub)

    # Minimal configs
    cfg = tmp_path / "configs"
    (cfg).mkdir()
    (cfg / "schedule.yaml").write_text(
        "schedule:\n  enabled: false\n  mode: weekly\n  timezone: UTC\n"
        "window:\n  daily_days: 3\n  weekly_days: 14\n  monthly_days: 45\n"
        "limits:\n  max_candidates_per_source: 10\n  max_total_candidates: 30\n  max_runtime_minutes: 5\n",
        encoding="utf-8",
    )
    (cfg / "sources.yaml").write_text(
        "sources:\n"
        "  crossref:\n    enabled: true\n    queries: [{name: q1, query: x}]\n    max_results: 10\n"
        "  arxiv:\n    enabled: true\n    categories: [eess.SY]\n    queries: [{name: q1, query: x}]\n    max_results: 10\n",
        encoding="utf-8",
    )
    pdir = cfg / "profiles" / "dtp-pmsm"
    pdir.mkdir(parents=True)
    (pdir / "research_profile.yaml").write_text(
        "research_profile:\n  name: x\n  slug: dtp-pmsm\n  field: f\n"
        "  core_topics: []\n  reject_topics: []\n"
        "  rule_filter: {require_year_after: null, require_abstract: false, blacklist_keywords: []}\n",
        encoding="utf-8",
    )

    data = tmp_path / "data"
    db = tmp_path / "papers.db"
    result = runner.invoke(app, [
        "--config-dir", str(cfg), "--profile", "dtp-pmsm",
        "discover", "--db-path", str(db), "--data-dir", str(data),
        "--days", "14", "--dry-run",
    ])
    assert result.exit_code == 0, result.stdout
    # dry-run 不应写 DB
    assert not db.exists() or db.stat().st_size == 0
```

- [ ] **步骤 2：运行测试验证失败**

- [ ] **步骤 3：实现 `src/main.py`**

```python
"""CLI entrypoint (typer).

MVP1 commands: db-init / discover / run / report

Global options applied via Typer callback for context.
"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from src.config import load_config
from src.logging_config import configure_logging
from src.orchestrator import run_mvp1_pipeline
from src.storage.db import apply_migrations, open_db

app = typer.Typer(no_args_is_help=True, help="research-paper-agent-team CLI (MVP1)")


_ConfigDir = Annotated[Path, typer.Option("--config-dir", help="Path to configs/ directory")]
_Profile = Annotated[str, typer.Option("--profile", help="Profile slug under configs/profiles/")]
_DryRun = Annotated[bool, typer.Option("--dry-run", help="No DB writes, no external side effects")]
_LogLevel = Annotated[str, typer.Option("--log-level")]
_DbPath = Annotated[Path, typer.Option("--db-path", help="SQLite DB path")]
_DataDir = Annotated[Path, typer.Option("--data-dir", help="data/ root for raw/normalized/reports/logs")]


@app.callback()
def _global_options(
    ctx: typer.Context,
    config_dir: _ConfigDir = Path("configs"),
    profile: _Profile = "dtp-pmsm",
    log_level: _LogLevel = "info",
):
    configure_logging(log_level=log_level)
    ctx.obj = {"config_dir": config_dir, "profile": profile, "log_level": log_level}


@app.command("db-init")
def db_init_cmd(
    db_path: _DbPath = Path("data/papers.db"),
):
    """Initialize SQLite schema."""
    conn = open_db(db_path)
    apply_migrations(conn)
    conn.close()
    typer.echo(f"DB initialized at {db_path}")


@app.command("discover")
def discover_cmd(
    ctx: typer.Context,
    db_path: _DbPath = Path("data/papers.db"),
    data_dir: _DataDir = Path("data"),
    days: Annotated[int, typer.Option("--days")] = 14,
    schedule_mode: Annotated[str, typer.Option("--mode")] = "manual",
    dry_run: _DryRun = False,
):
    """Discover new papers (fetch → normalize → dedupe → rule_filter → report)."""
    config = load_config(config_dir=ctx.obj["config_dir"], profile=ctx.obj["profile"])
    summary = run_mvp1_pipeline(
        config=config, db_path=db_path, data_dir=data_dir,
        schedule_mode=schedule_mode, dry_run=dry_run, days=days,
    )
    typer.echo(f"run_id: {summary.run_id}")
    typer.echo(f"status: {summary.status}")
    typer.echo(f"raw={summary.raw_count} normalized={summary.normalized_count} "
               f"deduped={summary.deduped_count} filtered={summary.filtered_count}")
    typer.echo(f"report: {summary.report_path}")


@app.command("run")
def run_cmd(
    ctx: typer.Context,
    db_path: _DbPath = Path("data/papers.db"),
    data_dir: _DataDir = Path("data"),
    days: Annotated[int, typer.Option("--days")] = 14,
    schedule_mode: Annotated[str, typer.Option("--mode")] = "manual",
    dry_run: _DryRun = False,
):
    """End-to-end run. In MVP1 equivalent to `discover`."""
    return discover_cmd(
        ctx=ctx, db_path=db_path, data_dir=data_dir,
        days=days, schedule_mode=schedule_mode, dry_run=dry_run,
    )


@app.command("report")
def report_cmd(
    ctx: typer.Context,
    run_id: Annotated[str, typer.Option("--run-id", help="Run ID to re-render report for")],
    db_path: _DbPath = Path("data/papers.db"),
    data_dir: _DataDir = Path("data"),
):
    """Re-render report for an existing run_id from SQLite state."""
    from src.reports.digest_writer import write_candidates_report
    from src.storage.repositories import PapersRepo

    conn = open_db(db_path)
    apply_migrations(conn)
    papers_rows = PapersRepo(conn).list_by_run(run_id)
    conn.close()

    # Convert sqlite Rows back to PaperCandidate (best-effort minimal fields)
    from src.models.paper import PaperCandidate
    import json as _json
    papers = [
        PaperCandidate(
            source=row["source"], source_id=row["source_id"], doi=row["doi"],
            title=row["title"], normalized_title=row["normalized_title"], title_hash=row["title_hash"],
            authors=_json.loads(row["authors_json"] or "[]"),
            venue=row["venue"], published_date=row["published_date"],
            abstract=row["abstract"], url=row["url"], pdf_url=row["pdf_url"],
        )
        for row in papers_rows
    ]
    output = data_dir / "reports" / run_id / "candidates.md"
    write_candidates_report(papers, output=output, run_id=run_id)
    typer.echo(f"Re-rendered: {output}")


if __name__ == "__main__":
    app()
```

- [ ] **步骤 4：运行测试 + Commit**

```bash
uv run pytest tests/integration/test_cli.py -v
git add src/main.py tests/integration/test_cli.py
git commit -m "feat(cli): typer 入口 + db-init/discover/run/report 子命令 + 全局参数"
```

---

### 任务 19：conftest 与 e2e 验收

**Owner：** coder + tester | **Reviewer：** reviewer (G6) | **BlockedBy：** T17, T18

**文件：**
- 创建：`tests/__init__.py`（空）
- 创建：`tests/conftest.py`
- 验证：5 条 MVP1 验收闸门全部通过

- [ ] **步骤 1：写 `tests/conftest.py`**

```python
"""Global pytest fixtures."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_real_network(monkeypatch, request):
    """Refuse real httpx network calls unless test is marked live_api."""
    if "live_api" in request.keywords:
        return
    import httpx

    original_send = httpx.Client.send

    def guarded_send(self, *args, **kwargs):
        # pytest-httpx will replace transport; if real network reached, raise
        raise RuntimeError(
            "Real network call blocked; use httpx_mock fixture or mark test with @pytest.mark.live_api"
        )

    # Don't actually patch — pytest-httpx already refuses unmocked requests by default;
    # this fixture serves as documentation. (Left as no-op to avoid double-protection conflicts.)
```

- [ ] **步骤 2：执行完整测试套件**

运行：`uv run pytest -v --cov=src --cov-report=term-missing`
预期：所有测试通过，覆盖率 > 80%

- [ ] **步骤 3：手动 e2e 验收（5 条闸门）**

闸门 1：重复 discover 不重复入库
```bash
uv run rpat db-init
uv run rpat discover --days 14
uv run rpat discover --days 14
# 检查 SQLite：papers 表中条目数应未翻倍
uv run python -c "import sqlite3; c=sqlite3.connect('data/papers.db'); print(c.execute('SELECT COUNT(*) FROM papers').fetchone())"
```

闸门 2：候选报告字段完整
打开 `data/reports/<run_id>/candidates.md`，确认每条含 title/authors/venue/date/doi/abstract/url。

闸门 3：source 失败 → partial（mock 测试 `test_pipeline_partial_when_one_source_fails` 已覆盖）

闸门 4：CI 不调真实 API
```bash
uv run pytest -m "not live_api" -v
```
预期：全绿。

闸门 5：dry-run 不写库
```bash
rm -f data/papers.db
uv run rpat discover --days 14 --dry-run
ls data/reports/_dryrun/
# data/papers.db 不应存在
```

- [ ] **步骤 4：Commit**

```bash
git add tests/__init__.py tests/conftest.py
git commit -m "test: 全局 conftest + MVP1 5 条验收闸门通过"
```

**Gate G6（最终）**：reviewer 审 5 条闸门全过 + 整体代码质量 + spec 一致性。通过后 MVP1 完成。

---

## DAG（任务依赖）

```text
T0(skeleton) ──┬─→ T1(docs)
                ├─→ T2(logging)──┐
                ├─→ T3(runid)────┤
                ├─→ T4(time)─────┤
                ├─→ T5(hash)─────┤
                ├─→ T6(config)───┤
                └─→ T7(models)───┴─→ T8(db) ─→ T9(repos) ─┐
                                                            │
T7 ─→ T10(normalizer) ─┐                                    │
                        ├─→ T11(crossref) ─┐                │
                        └─→ T12(arxiv)─────┤                │
                                            ├─→ T13(hard dedup)
                                            │       │
                                            │       └─→ T14(soft+orchestrator)
                                            │              │
T6, T9 ────────────────────────────────────┴──→ T15(rule_filter)
                                                           │
T7 ─→ T16(report writer)                                   │
                                                           │
T6,T8,T9,T10,T11,T12,T14,T15,T16 ──────────→ T17(orchestrator)
                                                           │
T6,T8,T17 ─────────────────────────────────→ T18(CLI)
                                                           │
T17,T18 ───────────────────────────────────→ T19(conftest+e2e)

Reviewer Gates: G1(after T1)  G2(after T9)  G3(after T12)  G4(after T15)  G5(after T17)  G6(after T19)
```

**并行机会**：
- T2 / T3 / T4 / T5 / T6 / T7 在 T0 完成后可全并行
- T11 / T12 在 T10 完成后可并行（researcher 可同时调研两个 API）
- T13 / T14 / T15 在 dedupe/filter 部分可流水线
- T1（scribe 文档抽取）可与 T2-T9 并行进行

---

## 范围之外（**不在本 plan 中实现**）

- LLM Screening Agent（MVP2）
- Zotero 集成（MVP3）
- 飞书通知（MVP4）
- Digest Agent（MVP4）
- Semantic Scholar enrichment（MVP2+）
- IEEE Xplore fetcher（MVP4+）
- RSS fetcher（MVP4+）
- source_watermarks 表（MVP1.5/MVP2）
- LangGraph / CrewAI / Prefect / Dagster
- MCP 化
- 多 profile 切换 UI

---

## 自检结果

**1. 规格覆盖度**：
- spec §3.1 流程图 → T11/T12（fetchers）/ T10（normalize）/ T14（dedupe）/ T15（filter）/ T17（orchestrator）✓
- spec §3.2 模块职责 MVP1 部分 → 已对应 ✓
- spec §5 CLI 契约 → T18 全局参数 + 子命令矩阵 ✓
- spec §5.4 dry-run 语义 → T17 实现 + T18 参数 + T19 闸门 5 验证 ✓
- spec §6 4 张表 MVP1 部分（papers/runs/filter_decisions/dedup_candidates）→ T8 ✓
- spec §10 MVP1 5 条验收闸门 → T19 ✓
- spec §11 ADR-001/002/003 → T1 ✓
- spec §15 子文档拆分 → T1 ✓

**2. 占位符扫描**：
- 无 "TODO" / "待定" / "后续实现" 占位 ✓
- 每个步骤都包含完整代码或精确命令 ✓

**3. 类型一致性**：
- `PaperCandidate` 字段在 T7/T10/T11/T12/T13/T14/T15/T16/T17 全部一致 ✓
- `RunSummary.dry_run` 在 T7 定义、T17 写入、T8 schema 持久化 ✓
- `FetchResult` 在 T11 定义、T11/T12/T17 使用一致 ✓
- `apply_rule_filter` 签名（papers/spec/conn/run_id/paper_ids）在 T15 定义、T17 调用一致 ✓
- `RuleFilterSpec` 在 T6 定义、T15 使用 ✓

---

## 执行交接

**计划已完成并保存到 `D:\projects\agents\research-paper-agent-team\docs\superpowers\plans\2026-05-10-mvp1-implementation.md`。**

两种执行方式：

**1. 子代理驱动（推荐）** — 每个任务调度一个新子代理，任务间通过 Gate 进行 reviewer 审查，快速迭代。**契合你的 Agent Team 配置**：
- `Build (big-pickle)` 调度 T0→T19；
- `Plan (kimi-k2.6)` 在每个 Gate 重新评估剩余 DAG；
- `coder (deepseek-v4-pro)` 实现 T0/T2-T19 的代码与测试；
- `researcher (qwen3.5-plus)` 在 T11/T12 之前调研 Crossref 与 arXiv API；
- `scribe (minimax-m2.7)` 完成 T1 的 7 份文档抽取；
- `reviewer (deepseek-v4-pro)` 把守 G1-G6；
- `debug (glm-5.1)` 在 fetcher 解析或 SQLite 异常时介入；
- `explore (minimax-m2.5)` 在 T17 之前定位所有 import 与依赖关系。

**2. 内联执行** — 在当前会话使用 `executing-plans` 顺序执行，批量推进并设检查点。

**选哪种方式？**
