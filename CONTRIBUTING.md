# 贡献指南

感谢你对 research-paper-agent-team 的关注！本文档将帮助你参与项目开发。

## 开发环境搭建

```bash
# 克隆仓库
git clone https://github.com/land3acpe/research-paper-agent-team.git
cd research-paper-agent-team

# 安装依赖（需要 uv）
uv sync

# 初始化数据库
uv run rpat db-init
```

## 代码规范

### Python 风格

- **格式化**：ruff（line-length = 100）
- **类型检查**：mypy strict 模式
- **测试**：pytest，覆盖率目标 ≥ 90%

```bash
# 格式化 + lint
uv run ruff check --fix .
uv run ruff format .

# 类型检查
uv run mypy src/

# 运行测试
uv run pytest

# 运行测试 + 覆盖率
uv run pytest --cov=src --cov-report=term-missing
```

### Commit 规范

使用 [Conventional Commits](https://www.conventionalcommits.org/) 格式：

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

常用 type：
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档变更
- `refactor`: 重构（不改变行为）
- `test`: 测试相关
- `chore`: 构建/工具变更

### 分支策略

- `main`：稳定版本，所有 PR 合并目标
- `feat/<name>`：新功能分支
- `fix/<name>`：Bug 修复分支

## 提交 Pull Request

1. Fork 仓库或创建分支
2. 编写代码 + 测试
3. 确保所有检查通过：
   - `uv run ruff check .` 无错误
   - `uv run mypy src/` 无错误
   - `uv run pytest` 全绿
4. 提交 PR，描述变更内容和原因

## 报告 Bug

请使用 [GitHub Issues](https://github.com/land3acpe/research-paper-agent-team/issues)，包含：

- 复现步骤
- 期望行为 vs 实际行为
- Python 版本和操作系统
- 相关日志输出

## 许可证

贡献的代码将按照 [MIT License](LICENSE) 发布。
