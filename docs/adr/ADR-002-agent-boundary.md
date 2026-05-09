# ADR-002：Agent 边界——确定性代码与 LLM Agent 的职责分离

- **状态**：Accepted
- **日期**：2026-05-10
- **决策者**：项目设计阶段

## 背景

项目需要两类"Agent"：Runtime Agents（Screening + Digest）做论文语义判断，确定性代码模块做流程编排与副作用管理。需要明确定义两者的边界，防止职责混淆导致的稳定性和安全性问题。

## 决定

**流程稳定性由确定性代码（Python Orchestrator + 各确定性模块）负责；Runtime Agents 仅负责语义判断。**

具体拆分：

| 环节 | 负责方 | 说明 |
|---|---|---|
| 查新调度、多源拉取、归一化 | 确定性代码 | Fetchers + Normalizer |
| 去重（硬/软） | 确定性代码 | Deduplicator |
| 规则初筛（黑名单/年份/语言） | 确定性代码 | Rule Filter |
| **相关性判断/评分/标签/优先级** | **Screening Agent** | 仅此环节调用 LLM |
| 根据 Agent 输出做 accept/reject/uncertain | 确定性代码 | Quality Gate |
| Zotero 写入 | 确定性代码 | Zotero Writer + State Machine |
| **周期总结/摘要/趋势/推荐阅读** | **Digest Agent** | 仅此环节调用 LLM |
| 报告渲染 | 确定性代码 | Report Writer (Jinja2) |
| 飞书通知 | 确定性代码 | Feishu Notifier |

## 写权限矩阵

严格执行以下边界——跨列写入视为 bug：

| 字段 | 数据源/normalizer 写 | Runtime Agent 写 |
|---|:---:|:---:|
| title / authors / venue / doi / published_date / abstract / url / source_id | ✅ | ❌ |
| decision / priority / score / reason / tags / collection_suggestion | ❌ | ✅ |
| summary / research_relation / new_tag_suggestions | ❌ | ✅ |
| zotero_item_key / status / imported_at | Zotero Writer 写 | ❌ |

## 严禁清单

以下行为**严禁**在任何实现中出现：

1. **把摘要生成塞进 Screening Agent**——摘要生成属于 Digest Agent，Screening Agent 仅做相关性判断
2. **Agent 直调 Zotero API**——Zotero 操作必须走 Zotero Writer（确定性模块）和 State Machine
3. **Agent 直调飞书 Webhook**——飞书通知必须走 Feishu Notifier（确定性模块）
4. **Agent 写 paper metadata 字段**——title/authors/venue/doi 等元数据字段只能由数据源 fetcher 或 normalizer 写入

## Dev Agent Team 与 Runtime Agents 的边界

本项目存在两层 Agent 概念，必须严格区分：

- **Development Agent Team**：用户使用 Claude Code 辅助开发时的协作角色（coder / reviewer / scribe 等），详见 [development_workflow.md](../development_workflow.md)。不进入 `src/`，不由 Python 调用，不参与论文 pipeline。
- **Runtime Agents**：项目运行时由 Orchestrator 调用的 LLM 模块（Screening + Digest），详见 [runtime_agents.md](../runtime_agents.md)。代码位于 `src/agents/`，仅做语义判断。

两层概念在文档、目录、代码中不得混用，命名不得重叠。
