# ADR-001：Orchestrator 选型——纯 Python

- **状态**：Accepted
- **日期**：2026-05-10
- **决策者**：项目设计阶段

## 背景

在项目架构设计阶段，需要确定 Pipeline Orchestrator 的技术选型。调研了同类学术论文管理工具的技术栈：

- **arxiv-digest**：确定性 pipeline + CLI
- **zotero-arxiv-daily**：确定性 pipeline + CLI
- **research-assist**：确定性 pipeline + CLI
- **paper-distill-mcp**：确定性 pipeline + MCP
- **Scholar-Agent**：确定性 pipeline + CLI

以上五个同类工具均未引入 LangGraph、CrewAI、Prefect 或 Dagster 等调度框架，均采用确定性 pipeline + CLI 的简洁架构。

## 决定

MVP1-MVP4 使用**纯 Python Orchestrator + 确定性 pipeline + 局部 LLM Runtime Agents**。

核心设计原则：`代码负责稳定性，Agent 负责研究判断`。流程编排（查新→归一化→去重→过滤→入库→摘要→通知）由确定性 Python 模块负责，只在语义判断环节（Screening + Digest）调用 LLM。

## 后果

### 优点
- **依赖少**：无需引入额外的调度框架，减少第三方依赖风险
- **调试简单**：纯 Python 逻辑，pdb / logging 即可调试
- **单测易写**：确定性代码天然适合单元测试
- **技术栈对齐**：与同类工具（arxiv-digest、zotero-arxiv-daily 等）保持一致

### 缺点
- 复杂分支逻辑需要手写 Python if/else 管理
- 人工审批中断后恢复需要自行实现
- 长任务（>1 小时）的 checkpoint 机制需要手写

## 触发重新评估的条件

以下任一条件满足时，重新评估是否引入调度框架：

- 出现多 Agent handoff（Agent A 输出作为 Agent B 输入的复杂协商场景）
- 需要人工审批中断后自动恢复执行
- 单次 run 超过 1 小时，需要 checkpoint/pause/resume
- 复杂条件分支无法用 Python if/else 优雅表达

## 备选方案

| 方案 | 拒绝原因 |
|---|---|
| **LangGraph** | MVP1-4 工作流为单向 DAG，无需图状态管理；引入反而增加学习与维护成本 |
| **CrewAI** | 面向多 Agent 协作，本项目只有 2 个 Runtime Agent，职责明确无协商需求 |
| **Prefect** | 面向数据工程 pipeline，功能过重；本项目调度需求简单（cron + CLI 手动触发） |
| **Dagster** | 面向数据资产编排，与本项目"论文查新→入库→通知"的线性流程不匹配 |
