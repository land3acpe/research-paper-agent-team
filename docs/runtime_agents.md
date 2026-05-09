# Runtime Agents

> **定位**：本文档仅描述项目运行时由 Python Orchestrator 调用的 LLM 语义模块。开发协作中使用的 AI 工具（Development Agent Team）不在本文档范围内，见 [development_workflow.md](./development_workflow.md)。

---

## 1. MVP1 状态

**当前项目处于 MVP1 阶段，未启用任何 Runtime Agent。**

本文档为 MVP2+ 前向规划。MVP1 仅实现确定性 pipeline：fetchers → normalize → dedupe → rule_filter → report，不涉及 LLM 调用。

---

## 2. Runtime Agents 定义

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

---

## 3. 字段写权限矩阵

| 字段 | 数据源/normalizer 写 | Runtime Agent 写 |
|---|:---:|:---:|
| title / authors / venue / doi / published_date / abstract / url / source_id | ✅ | ❌ |
| decision / priority / score / reason / tags / collection_suggestion | ❌ | ✅ |
| summary / research_relation / new_tag_suggestions | ❌ | ✅ |
| zotero_item_key / status / imported_at | Zotero Writer 写 | ❌ |

---

## 4. Screening Agent

- **职责**：相关性判断 / 评分 / 优先级 / 受控标签 / 筛选理由
- **不做**：摘要生成、研究趋势分析（属于 Digest Agent）
- **批量**：默认 batch_size=5，输出 JSON array；解析失败时降级单篇
- **输出字段**：decision / priority / score / topic_relevance / method_relevance / venue_quality / novelty_potential / tags / collection / reason / evidence / manual_review_required / fulltext_required / new_tag_suggestions
- **评分上限**：score 合法范围 0–20；四个 sub-score 各 0–5
- **prompt 文件**：`prompts/screening_agent.md`，版本化
- **实现阶段**：MVP2

---

## 5. Digest Agent

- **职责**：周期入库论文摘要 / 标签聚合 / 趋势 / 推荐阅读顺序 / 与当前课题关系
- **不做**：单篇相关性判断（属于 Screening Agent）
- **输入**：本轮 imported papers + screening_results
- **输出**：Markdown 文档，含 10 个 section
- **prompt 文件**：`prompts/digest_agent.md`，版本化
- **实现阶段**：MVP4

---

## 6. Runtime Agents 与 Development Agent Team 的区别

| 维度 | Runtime Agents | Development Agent Team |
|---|---|---|
| 调用者 | Python Orchestrator | 用户（通过 Claude Code） |
| 代码位置 | `src/agents/` | `.claude/agents/` |
| 功能 | 论文语义判断（Screening + Digest） | 辅助开发：编码、审查、调研、文档撰写 |
| 输出 | 写入 screening_results / digest 报告 | 修改 `src/`、`tests/`、`docs/` |
| 文档 | 本文档 | [development_workflow.md](./development_workflow.md) |

Runtime Agents **不会**进入 `src/` 业务代码、不会被 Python 调用、不参与论文查新/筛选/入库/通知流程。它们是完全独立的两层概念，代码和文档中不得混用。
