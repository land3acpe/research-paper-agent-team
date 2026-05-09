# Configuration（配置文件说明）

> **定位**：本文档描述项目运行时所需的所有配置文件及其结构。配置文件位于 `configs/` 目录下，由 `--config-dir` 全局参数指定路径（默认 `./configs/`）。

---

## 配置文件结构

```text
configs/
├── schedule.yaml         # 定时与限额
├── sources.yaml          # 数据源 API key、查询、max_results
├── tag_schema.yaml       # allowed_tags
├── zotero.yaml           # collection_root / import_policy / duplicate_policy
├── feishu.yaml           # webhook_env / message_style
├── llm.yaml              # provider 配置（OpenAI 兼容协议）
└── profiles/
    └── dtp-pmsm/
        └── research_profile.yaml
```

---

### schedule.yaml

定时调度与每次运行的限额配置。

**何时编辑**：调整查新频率（daily/weekly/monthly）、修改单次运行最大论文数量、切换调度模式（cron / APScheduler / 手动）时编辑此文件。

---

### sources.yaml

数据源 API key、查询关键词、每个源的 max_results。

**何时编辑**：新增数据源（如 IEEE Xplore、RSS）、修改检索关键词、更换 API key、调整每个源的返回数量上限时编辑此文件。

---

### tag_schema.yaml

定义 `allowed_tags` 列表——Screening Agent 只能从中选择标签，不能自行创造。

**何时编辑**：研究课题发生变化、需要添加新标签分类、调整标签层级结构时编辑此文件。注意：Agent 建议的新标签会写入 `new_tag_suggestions`，不会直接进入此文件。

---

### zotero.yaml

Zotero 集成配置：collection_root（目标合集路径）、import_policy（导入策略）、duplicate_policy（重复处理策略）。

**何时编辑**：修改 Zotero 文库的 collection 结构、调整导入策略（如从 manual_approval 改为自动）、配置 Zotero API key 相关参数时编辑此文件。

---

### feishu.yaml

飞书通知配置：webhook_env（webhook 地址环境变量名）、message_style（消息样式模板）。

**何时编辑**：更换飞书机器人 webhook 地址、调整通知消息格式、新增通知渠道时编辑此文件。

---

### llm.yaml

LLM provider 配置，遵循 OpenAI 兼容协议。

```yaml
llm:
  default_provider: deepseek
  providers:
    deepseek:
      base_url: "https://api.deepseek.com"
      api_key_env: "DEEPSEEK_API_KEY"
      models:
        screening: "deepseek-v4-pro"
        digest: "deepseek-v4-pro"
    qwen:
      base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
      api_key_env: "DASHSCOPE_API_KEY"
      models:
        screening: "qwen3.5-plus"
```

**何时编辑**：切换 LLM provider（如从 DeepSeek 切换到 Qwen）、更换 API key 环境变量名、调整 Screening / Digest Agent 使用的模型版本时编辑此文件。

---

### profiles/{name}/research_profile.yaml

按研究课题的画像配置：研究方向关键词、必含词/黑名单词、年份范围、语言偏好等。

**何时编辑**：新增研究课题（如从 DTP-PMSM 切换到其他方向）、调整相关性筛选规则、修改评分权重时编辑此文件。通过 `--profile` 全局参数切换不同画像。
