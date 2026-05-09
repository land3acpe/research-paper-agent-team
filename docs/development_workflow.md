# Development Workflow（开发协作流程）

> **定位**：本文档仅描述使用 Claude Code / AI 工具辅助开发本项目的协作流程，**不属于项目 runtime**。开发 Agent Team 不会被 Python Orchestrator 调用，不进入 `src/` 运行时模块，不参与论文查新/筛选/入库/通知流程。

---

## 2. Development Agent Team 角色矩阵

本项目的开发协作由以下 8 个 Agent 角色构成，各自承担独立的开发任务领域：

| 角色 | 模型 | 职责 |
|---|---|---|
| Build (Tab) | big-pickle | 调度——接收用户意图、分派任务、汇总结果、把控整体进度 |
| Plan (Tab) | kimi-k2.6 | 任务拆分——将需求拆解为独立的子任务，制定实现计划（只读，不改代码） |
| coder | deepseek-v4-pro | 实现 `src/` + `tests/`——编写与修改业务代码和测试代码 |
| reviewer | deepseek-v4-pro | 代码审查——对 coder 的产出进行质量审查，确保符合架构与规范 |
| researcher | qwen3.5-plus | 外部 API/算法调研——查找论文检索 API 文档、去重算法、Zotero SDK 用法等 |
| scribe | minimax-m2.7 | 文档抽取与撰写——从 spec 中抽取子文档、撰写 ADR、维护项目文档 |
| explore | minimax-m2.5 | 代码定位与引用查找——在大型代码库中快速定位文件、函数、类引用 |
| debug | glm-5.1 | 疑难调试——分析复杂 bug、定位根本原因、提出修复路径 |

---

## 3. 常见协作模式

### 3.1 如何拆任务

1. 用户提出需求 → **Build** 接收并转交 **Plan**
2. **Plan** 拆分为独立子任务，写出实现计划（只读分析，不改代码）
3. **Build** 确认计划后将子任务分派给 coder / scribe / researcher 等
4. 各角色独立执行，无共享状态依赖的子任务可并行

### 3.2 如何走 Gate

每个 MVP 阶段有明确的验收闸门（Gate），由 **reviewer** 执行审查：
- 代码审查聚焦于架构合规、逻辑正确、测试覆盖
- 通过后方可进入下一阶段

### 3.3 如何重审

当审查不通过时：
- **reviewer** 给出具体的问题定位和建议
- **coder** 根据反馈修改后重新提交审查
- 反复直到 Gate 通过

---

## 4. 边界——这些 Agent 不会做什么

以下行为由 Development Agent Team **明确定义为 out of scope**，绝不允许发生：

- ❌ **不会**进入 `src/` 作为运行时模块（不被 Python 调用）
- ❌ **不会**被 Python Orchestrator 调用参与论文查新 pipeline
- ❌ **不会**替代 Runtime Agents（Screening / Digest）做语义判断
- ❌ **不会**直接操作 Zotero、发送飞书通知、修改 SQLite 业务数据

Development Agent Team 的唯一职责是辅助开发本项目——编写代码、审查质量、调研方案、撰写文档。项目启动后，它们与 runtime 完全隔离。
