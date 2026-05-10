# 安全策略

## 支持的版本

以下版本正在接受安全更新：

| 版本 | 支持状态 |
| --- | --- |
| 0.1.x | ✅ 支持 |

## 报告漏洞

如果你发现安全漏洞，请**不要**通过公开的 GitHub Issue 报告。

请通过以下方式私下报告：

* 在 GitHub 上使用 [安全报告功能](https://github.com/land3acpe/research-paper-agent-team/security/advisories/new)
* 或发送邮件至项目维护者

我们承诺：

* 在 48 小时内确认收到报告
* 在 7 天内提供初步评估
* 在发布修复之前不公开披露漏洞详情

## 安全最佳实践

* 不要将 API 密钥或令牌提交到代码仓库
* 使用 `.env` 文件存储敏感配置（已在 `.gitignore` 中排除）
* 定期更新依赖项：`uv lock --upgrade`
