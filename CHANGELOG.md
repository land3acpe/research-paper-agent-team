# 更新日志

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [0.1.0] - 2026-05-10

### 新增

- MVP1 完整论文查新 pipeline：fetch → normalize → dedupe → filter → report
- arXiv fetcher：支持旧式和新式 ID，自动分页抓取
- Semantic Scholar fetcher：关键词搜索 + 批量详情查询
- 标题归一化器：统一大小写、标点、空格、Unicode
- 模糊去重器：基于 rapidfuzz 的标题相似度匹配（阈值 0.85）
- 关键词/年份过滤器：支持 profile 配置
- Markdown + JSON 报告生成器
- SQLite 存储层：papers 表 + runs 表 + migrations
- Typer CLI 入口：db-init / discover / run / report 子命令
- 配置系统：YAML profile + 环境变量覆盖
- 结构化日志：structlog + JSON 输出
- 80 条测试用例，95% 代码覆盖率
- CI 就绪：ruff + mypy + pytest 配置完整

### 修复

- arXiv 旧式 ID 前缀丢失问题（如 `0704.0001` → 正确保留前缀）
- `list_by_run` 忽略 run_id 导致跨 run 数据混淆

### 文档

- 架构设计文档（ADR-001/002/003）
- 配置指南
- 开发协作流程
- Runtime Agents 规划（MVP2+）
