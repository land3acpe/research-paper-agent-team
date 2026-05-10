# research-paper-agent-team

[![CI](https://img.shields.io/badge/ci-github%20actions-blue)](https://github.com/land3acpe/research-paper-agent-team/actions)
[![Coverage](https://img.shields.io/badge/coverage-95%25-brightgreen)](https://github.com/land3acpe/research-paper-agent-team/actions)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green)](./LICENSE)
[![Status](https://img.shields.io/badge/status-MVP1-orange)](./CHANGELOG.md)

面向特定科研方向的**论文查新与管理 Agent Team**。

> 首版方向：**DTP-PMSM 谐波抑制**（双三相永磁同步电机）。无 LLM、无 Zotero、无飞书，一条纯 Python 确定性 pipeline 搞定查新+去重+报告。

---

## 简介

`research-paper-agent-team` 是一个面向领域文献调研的命令行工具。它从多个学术数据源抓取论文元数据，经归一化、模糊去重、关键词/年份过滤后，输出 Markdown + JSON 双格式报告。全程不需要外挂 LLM，不依赖任何外部服务——数据存在本机 SQLite 里，开箱即用。

**解决的问题：** 科研人员在文献调研初期需要定期追踪某个方向的最新论文，手动翻 arXiv、Semantic Scholar 既低效又容易重复。本工具将这一流程自动化、可复现，每次运行生成一个唯一 `run_id`，方便追溯每次查新的结果变化。

---

## 特性

- **多源论文抓取** — 支持 arXiv API 和 Semantic Scholar API，可扩展更多数据源
- **标题归一化 + 模糊去重** — 基于 `rapidfuzz` 的标题相似度计算，自动合并跨源重复论文
- **关键词/年份过滤** — 按 Profile 定义的 include/exclude 关键词和年份范围筛选
- **Markdown + JSON 报告生成** — 每次运行产出可读 Markdown 报告和结构化 JSON 数据
- **纯 Python 确定性 pipeline** — 无 LLM 框架依赖，无随机性，结果严格可复现
- **SQLite 本地存储** — 零外部服务依赖，单文件数据库，方便备份和迁移

---

## 快速开始

### 环境要求

- Python 3.11 或 3.12
- [uv](https://docs.astral.sh/uv/) 包管理器

### 安装与运行

```bash
# 克隆仓库
git clone https://github.com/land3acpe/research-paper-agent-team.git
cd research-paper-agent-team

# 安装依赖
uv sync

# 初始化数据库
uv run rpat db-init

# Dry-run 一次查新（不写库，预览结果）
uv run rpat discover --profile dtp-pmsm --days 14 --dry-run

# 正式查新（写入 SQLite 并生成报告）
uv run rpat discover --profile dtp-pmsm --days 14
```

---

## CLI 命令

| 命令 | 说明 |
|------|------|
| `rpat db-init` | 初始化 SQLite 数据库，创建表结构并执行迁移 |
| `rpat discover` | 执行查新 pipeline：抓取 → 归一化 → 去重 → 过滤 → 报告 |
| `rpat run` | MVP1 中与 `discover` 等价，预留为完整 pipeline 入口 |
| `rpat report` | 根据已有 `--run-id` 重新渲染报告 |

### 命令详解

#### `rpat db-init`

```bash
uv run rpat db-init [--db-path data/papers.db]
```

初始化数据库文件。首次运行必须执行此命令。如果数据库已存在，会安全地应用未执行的迁移。

#### `rpat discover`

```bash
uv run rpat discover \
    --profile dtp-pmsm \
    --days 14 \
    [--dry-run] \
    [--db-path data/papers.db] \
    [--data-dir data] \
    [--config-dir configs] \
    [--mode manual]
```

核心命令，执行完整的论文查新流程：

1. **抓取 (Fetch)** — 从 arXiv、Semantic Scholar 等数据源拉取论文元数据
2. **归一化 (Normalize)** — 将不同来源的标题格式统一化
3. **去重 (Dedupe)** — 硬去重（title_hash）+ 软去重（rapidfuzz 模糊匹配）
4. **过滤 (Filter)** — 按 Profile 配置的关键词和年份规则筛选
5. **报告 (Report)** — 生成 Markdown 和 JSON 报告

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--profile` | `dtp-pmsm` | Profile 名称，对应 `configs/profiles/<name>/` |
| `--days` | `14` | 回溯天数，只抓取该时间窗口内的新论文 |
| `--dry-run` | `false` | 试运行模式：不写入数据库，不产生外部副作用 |
| `--db-path` | `data/papers.db` | SQLite 数据库路径 |
| `--data-dir` | `data` | 数据根目录（raw / normalized / reports / logs） |
| `--config-dir` | `configs` | 配置文件目录 |
| `--mode` | `manual` | 调度模式（manual / schedule） |

#### `rpat run`

```bash
uv run rpat run [参数同 discover]
```

在 MVP1 中等同于 `discover`。后续版本将扩展为包含 LLM Screening 等阶段的完整 pipeline。

#### `rpat report`

```bash
uv run rpat report --run-id <run_id> [--db-path data/papers.db] [--data-dir data]
```

从 SQLite 中读取指定 `run_id` 的记录，重新渲染 Markdown 报告。

---

## 项目结构

```
src/
├── main.py                 # CLI 入口（typer）
├── orchestrator.py         # Pipeline 编排器（MVP1）
├── config.py               # 配置加载（Pydantic Settings）
├── logging_config.py       # 结构化日志配置（structlog）
├── fetchers/               # 数据源抓取
│   ├── base.py             #   抽象基类
│   ├── _http.py            #   HTTP 客户端封装（httpx + tenacity）
│   ├── arxiv.py            #   arXiv API 抓取器
│   └── crossref.py         #   CrossRef API 抓取器
├── normalize/              # 标题归一化
│   ├── normalizer.py       #   归一化调度
│   └── title.py            #   标题字符串处理
├── dedupe/                 # 论文去重
│   ├── deduplicator.py     #   去重调度（硬去重 + 软去重）
│   ├── hard.py             #   硬去重（title_hash 精确匹配）
│   └── soft.py             #   软去重（rapidfuzz 模糊匹配）
├── filter/                 # 规则过滤
│   └── rule_filter.py      #   关键词 / 年份过滤
├── models/                 # 数据模型（Pydantic）
│   ├── paper.py            #   PaperCandidate, PaperRecord
│   ├── dedup.py            #   DedupGroup, DedupDecision
│   └── run.py              #   RunSummary
├── reports/                # 报告生成
│   ├── digest_writer.py    #   Markdown 报告写入
│   └── templates/          #   Jinja2 模板
├── storage/                # 持久化层
│   ├── db.py               #   SQLite 连接管理 + 迁移
│   ├── repositories.py     #   数据访问（PapersRepo）
│   └── migrations/         #   SQL 迁移脚本
└── utils/                  # 工具函数
    ├── hashing.py          #   标题哈希
    ├── runid.py            #   运行 ID 生成
    └── time.py             #   时间工具
configs/
├── profiles/               # 研究方向配置
│   └── dtp-pmsm/           #   DTP-PMSM 谐波抑制方向
├── sources.yaml            # 数据源定义
├── schedule.yaml           # 定时调度配置（MVP2+）
└── tag_schema.yaml         # 标签体系
docs/
├── architecture.md         # 架构文档
├── configuration.md        # 配置说明
├── development_workflow.md # 开发协作流程
├── runtime_agents.md       # Runtime Agents 设计（MVP2+）
├── adr/                    # 架构决策记录
│   ├── ADR-001-orchestrator-choice.md
│   ├── ADR-002-agent-boundary.md
│   └── ADR-003-zotero-import-state-machine.md
└── superpowers/
    └── specs/              # 需求规格说明
tests/                      # 测试用例
```

---

## 开发

```bash
# 安装全部依赖（含 dev 工具）
uv sync

# 运行测试（默认跳过 live_api 测试）
uv run pytest

# 完整测试（含在线 API 测试）
uv run pytest -m ""

# 代码检查
uv run ruff check src/ tests/

# 类型检查
uv run mypy src/ tests/

# 测试覆盖率报告
uv run pytest --cov=src --cov-report=term-missing
```

---

## 文档

- [架构](docs/architecture.md) — 系统整体架构与数据流设计
- [配置](docs/configuration.md) — Profile、数据源、调度配置说明
- [Runtime Agents（MVP2+）](docs/runtime_agents.md) — 面向 LLM 时代的 Runtime Agent 设计
- [开发协作流程](docs/development_workflow.md) — 分支策略、代码审查、Git 规范
- ADR：[ADR-001](docs/adr/ADR-001-orchestrator-choice.md) · [ADR-002](docs/adr/ADR-002-agent-boundary.md) · [ADR-003](docs/adr/ADR-003-zotero-import-state-machine.md)

---

## 路线图

| 阶段 | 状态 | 内容 |
|------|------|------|
| **MVP1** | ✅ 已完成 | 多源查新 + 标题归一化 + 模糊去重 + 关键词/年份过滤 + Markdown 报告 |
| **MVP2** | 🔜 计划中 | LLM Screening（相关性打分 + 摘要翻译）、RSS 订阅、Semantic Scholar 丰富化、IEEE Xplore |
| **MVP3** | 📋 规划中 | Zotero 自动导入、飞书消息推送、LangGraph Agent 编排、MCP 集成 |

MVP1 范围之外的项目：LLM Screening · Zotero · 飞书 · LangGraph · MCP · Semantic Scholar enrichment · IEEE Xplore · RSS

详见 [需求规格](docs/superpowers/specs/2026-05-10-research-paper-agent-team-design.md)

---

## 贡献

欢迎提交 Issue 和 Pull Request！请先阅读 [开发协作流程](docs/development_workflow.md) 了解分支策略和代码审查规范。

---

## 许可证

本项目基于 [MIT License](./LICENSE) 开源。Copyright (c) 2026 land3acpe。
