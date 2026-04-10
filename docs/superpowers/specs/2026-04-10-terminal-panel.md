# Terminal Panel TUI Design

## Overview

使用 Rich 库实现终端面板，左侧显示事件流，右侧显示思考和记忆。

## Layout

```
┌─────────────────────────────────────────────────────────────┐
│                      Reverb Agent                           │
├───────────────────────────┬─────────────────────────────────┤
│      EVENT STREAM         │         THOUGHTS               │
│                           │                                 │
│  [12:30] VSCode: file     │  分析: 用户正在开发 HTTP 服务器  │
│  [12:29] Chrome: GitHub   │  推断: 这是一个新功能            │
│  [12:28] VSCode: file     │  建议: 可以创建测试 Skill        │
│  [12:27] Terminal: git   │                                 │
│                           │                                 │
├───────────────────────────┼─────────────────────────────────┤
│      MEMORIES             │         STATUS                  │
│                           │                                 │
│  • 11:00 周报任务         │  Observers: 5 active            │
│  • 10:30 代码审查          │  LLM: ollama/llama3             │
│  • 昨天 API 集成           │  Skills: 3 learned               │
│                           │                                 │
└───────────────────────────┴─────────────────────────────────┘
```

## Components

1. **Event Panel** - 显示最近的事件流，实时更新
2. **Thoughts Panel** - 显示 Agent 分析和思考结果
3. **Memories Panel** - 显示学到的记忆/技能
4. **Status Panel** - 显示系统状态

## Implementation

使用 Rich 的 `Panel` + `Layout` 实现：
- `Layout` 定义左右分区
- 定时刷新面板内容
- 事件驱动更新