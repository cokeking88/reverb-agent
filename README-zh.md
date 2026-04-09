# Reverb Agent

一个个人AI助手，从你的工作模式中学习，帮助你完成各种任务。

## 功能特性

- **自主观察**：跨应用监控你的工作
- **模式学习**：分析你的行为，发现重复的工作流程
- **技能生成**：从重复任务中创建可复用的技能
- **记忆系统**：跨会话存储学习到的知识
- **CLI优先**：轻量级命令行界面

## 安装

```bash
pip install -e .
```

## 快速开始

```bash
# 初始化数据目录
reverb init

# 配置 LLM
reverb config-llm --provider ollama --model llama3

# 开始观察
reverb observe

# 查看状态
reverb status
```

## 命令

### observe

启动观察模式，监控你的应用程序。

```bash
reverb observe                    # 默认（system, vscode, intellij, browser, feishu）
reverb observe --interval 5       # 设置轮询间隔
reverb observe --observers system,vscode  # 选择特定观察器
reverb observe --browser Safari   # 选择浏览器（Chrome, Safari, Edge）
```

### status

显示当前配置。

```bash
reverb status
```

### config-llm

配置 LLM 设置。

```bash
reverb config-llm --provider ollama --model llama3
reverb config-llm --provider openai --model gpt-4 --api-key YOUR_KEY
```

### memory

查看学习到的记忆。

```bash
reverb memory                     # 显示最近的记忆
reverb memory --type episodic     # 按类型筛选
reverb memory --limit 20          # 限制结果数量
```

### skills

查看生成的技能。

```bash
reverb skills
```

### run

执行一个技能。

```bash
reverb run <skill-id>
```

## 观察器

| 观察器 | 说明 |
|----------|-------------|
| system | 监控窗口焦点和应用变化 |
| vscode | 追踪 VSCode 中的文件变化 |
| intellij | 监控 Android Studio/IntelliJ |
| browser | 追踪浏览器标签页和 URL |
| feishu | 监控飞书桌面应用 |

## 配置

配置存储在 `~/.reverb-agent/config.json`。

```json
{
  "data_dir": "~/.reverb-agent/data",
  "llm": {
    "provider": "ollama",
    "model": "llama3"
  },
  "observers": {
    "enabled": true,
    "interval": 5
  }
}
```

## 数据存储

所有数据本地存储在 `~/.reverb-agent/data/`：
- `reverb.db` - SQLite 数据库，存储记忆和会话
- `skills/` - 生成的技能定义

## 隐私

所有观察数据均保存在本地，不上传云端。

## 环境要求

- Python 3.11+
- macOS（其他平台即将支持）
- LLM 端点（Ollama、OpenAI 等）