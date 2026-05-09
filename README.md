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
