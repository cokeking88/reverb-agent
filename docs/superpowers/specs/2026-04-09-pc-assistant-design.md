# PC 个人助手 - 设计文档

> 参考: Hermes Agent (NousResearch) - 融合其自学习能力 + 自主观察特性

## 1. 项目概述

**项目名称**：PC Personal Assistant / Hermes-mac  
**核心目标**：通过自主观察用户日常工作，自动学习工作模式，主动创建Skills，定期提醒和自动化辅助  
**目标用户**：使用 Mac 进行开发的知识工作者

## 2. 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                     Hermes-mac CLI Core                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │  Observer  │→│   Agent     │→│   Memory    │          │
│  │ (自主观察)  │  │   Loop     │  │ (自学习存储) │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
│         ↑                ↑                ↑                │
│         │         ┌──────┴──────┐        │                │
│         │         │   Skills    │        │                │
│         │         │  (自生成)   │        │                │
│         │         └─────────────┘        │                │
└─────────────────────────────────────────────────────────────┘
         ↑                        ↑
    ┌────────┐              ┌────────┐
    │Gateway │              │ Gateway│
    │(飞书等) │              │(其他)   │
    └────────┘              └────────┘
```

### 2.1 技术选型

- **运行时**：Python（对齐 Hermes Agent 生态）
- **CLI 框架**：基于 Hermes Agent 定制
- **LLM 调用**：支持 Ollama / OpenAI / OpenRouter / 自定义端点
- **存储**：SQLite（记忆）+ JSON（配置）+ 文件系统（Skills）
- **macOS 集成**：AppleScript + Accessibility API + NSWorkspace

## 3. 模块设计

### 3.1 Observer 观察层（新增自主观察）

**职责**：自主采集用户在 Mac 上的操作事件（不同于 Hermes 被动等待用户输入）

**设计原则**：通用可扩展的观察器架构，支持任意 APP 的观察器插件

**观察器接口抽象**：
```typescript
// 观察器基接口
interface Observer {
  name: string;                    // 观察器名称
  appBundleId?: string;            // 关联的 APP bundle ID
  capabilities: Capability[];      // 支持的能力
  
  start(): Promise<void>;          // 启动观察
  stop(): Promise<void>;          // 停止观察
  onEvent(callback: (event: ObserverEvent) => void): void;
}

// 能力类型
type Capability = 
  | 'window_focus'        // 窗口焦点
  | 'file_content'        // 文件内容
  | 'cursor_position'    // 光标位置
  | 'code_diff'          // 代码修改
  | 'dom_content'        // 网页内容
  | 'user_action'        // 用户操作（点击、输入等）
  | 'message'            // 消息内容
  | 'meeting'            // 日历会议
  | 'command'            // 命令执行;
```

**内置观察器（按优先级，MVP 全部实现）**：

1. **SystemObserver** - 系统级观察
   - 窗口切换（active app）
   - 应用启动/关闭
   - 键盘快捷键
   - 文件访问

2. **BrowserObserver** - 浏览器观察（精细化）
   - URL/标题
   - DOM 内容（选中文本、页面结构）
   - 用户操作（点击、输入、滚动）
   - 支持：Chrome、Edge、Safari

3. **VSCodeObserver** - VSCode 观察（精细化）
   - 当前打开的文件路径
   - 文件内容 + 光标位置（第几行第几列）
   - 代码修改 diff（新增/删除/修改内容）
   - 执行的终端命令

4. **IntelliJObserver** - IDE 观察（Android Studio）
   - 当前打开的文件路径
   - 文件内容 + 光标位置
   - 代码修改 diff
   - 构建状态

5. **FeishuObserver** - 飞书观察（精细化）
   - 当前查看的文档内容
   - 消息内容（会话列表、具体消息）
   - 日程信息
   - 审批/任务

6. **TerminalObserver** - 终端观察
   - 当前工作目录
   - 执行的命令
   - 命令输出

7. **CalendarObserver** - 日历观察
   - 会议事件
   - 日程安排

**观察器注册机制**：
```typescript
// 观察器注册表
interface ObserverRegistry {
  register(observer: Observer): void;
  unregister(name: string): void;
  get(name: string): Observer | undefined;
  list(): Observer[];
  listByCapability(capability: Capability): Observer[];
}
```

**事件格式**：
```typescript
interface ObserverEvent {
  id: string;
  observer: string;              // 观察器名称
  type: string;                 // 事件类型
  timestamp: number;
  source: {
    app?: string;
    window?: string;
    file?: string;
    line?: number;              // 光标行号
    column?: number;             // 光标列号
  };
  data: Record<string, any>;     // 观察器-specific 数据
  // 关联的任务 ID（如果 Agent 判断属于某个任务）
  taskId?: string;
}
```

**实现方式**：
- AppleScript：系统事件、飞书、部分浏览器
- 浏览器扩展：Chrome/Safari（DOM、用户操作）
- IDE 插件：VSCode（扩展 API）、IntelliJ（插件）→ 无需 Debug Port
- 系统 API：日历、终端历史

### 3.2 Agent Loop 理解层（对齐 Hermes Agent）

**职责**：解读事件流、识别模式、生成记忆（基于 Hermes Agent 的 Agent Loop）

**核心能力**：
1. **事件聚合**：将连续事件聚合成"任务"单元
2. **模式识别**：发现时间/频率规律的工作（对齐 Hermes 的模式发现）
3. **主动询问**：定期向用户确认任务细节（对齐 Hermes 的 nudge 机制）
4. **Skill 自生成**：将重复工作封装为可复用流程（对齐 Hermes 的 skill creation）
5. **记忆检索**：跨会话搜索和上下文recall（对齐 Hermes 的 FTS5 session search）
6. **用户建模**：学习用户偏好和工作风格（对齐 Hermes 的 Honcho 用户建模）

**对齐 Hermes Agent 特性**：
- 周期性自检（periodic self-nudge）判断是否需要记录
- 复杂任务后自动创建 Skill
- 使用过程自我改进 Skill
- 基于 FTS5 的会话搜索 + LLM 总结

**LLM 调用接口**：
```typescript
interface LLMConfig {
  provider: 'ollama' | 'openai' | 'openrouter' | 'custom';
  model: string;
  endpoint?: string;
  apiKey?: string;
}
```

### 3.3 Memory 记忆层（对齐 Hermes Agent）

**职责**：持久化存储学习成果（完全对齐 Hermes 的记忆系统）

**对齐 Hermes 的数据结构**：

1. **Memory（记忆）**
   ```typescript
   interface Memory {
     id: string;
     content: string;        // 记忆内容
     memoryType: 'episodic' | 'semantic' | 'user_model';
     tags: string[];
     createdAt: number;
     updatedAt: number;
   }
   ```

2. **Skill（技能）** - Hermes 的 procedural memory
   ```typescript
   interface Skill {
     id: string;
     name: string;
     description: string;
     trigger: Trigger;
     steps: Step[];
     createdAt: number;
     usageCount: number;
     // 自我改进能力
     version: number;
     improvements: Improvement[];
   }
   ```

3. **Session（会话）** - 用于跨会话检索
   ```typescript
   interface Session {
     id: string;
     events: ObserverEvent[];
     summary: string;
     createdAt: number;
   }
   ```

4. **User Profile（用户画像）** - 对齐 Honcho 用户建模
   ```typescript
   interface UserProfile {
     id: string;
     preferences: Record<string, any>;
     workPatterns: WorkPattern[];
     communicationStyle: string;
     updatedAt: number;
   }
   ```

**存储位置**：统一数据目录（可配置，默认 `~/.hermes-mac/data`）

### 3.4 Gateway 扩展层

**职责**：对接外部服务（对齐 Hermes Gateway）

**对齐 Hermes 的 Gateway**：
- 支持多平台：Telegram, Discord, Slack, WhatsApp, Signal, Email
- 飞书作为中国特色 Gateway
- Webhook 接收
- 消息推送（卡片消息）

**接口设计**：
```typescript
interface Gateway {
  name: string;
  push(message: Message): Promise<void>;
  pull(event: any): Promise<any>;
}
```

### 3.5 Cron 调度层（新增定时任务）

**职责**：基于观察学习到的模式，执行定时任务

**能力**：
- 日/周/月周期性任务（对齐 Hermes cron）
- 自然语言定义任务
- 任意 Gateway 推送结果
- 任务执行后自学习改进

## 4. 交互设计

### 4.1 CLI 命令

```bash
# 启动观察模式
assistant observe

# 查看当前记忆
assistant memory list

# 查看学到的技能
assistant skills list

# 手动触发技能
assistant run <skill-id>

# 主动询问模式
assistant ask "刚才在做什么"

# 配置 LLM
assistant config llm --provider ollama --model llama3

# 配置飞书
assistant config gateway feishu --webhook <url>
```

### 4.2 主动询问机制

- 每完成一个任务后，LLM 判断是否需要确认
- 用户回复自然语言描述，自动转为结构化记忆
- 支持追问细节（时间、频率、关联项目）

## 5. 隐私与安全

- 所有观察数据本地存储，不上传云端
- 可配置观察粒度（开/关特定事件类型）
- 数据目录支持加密（future）

## 6. 扩展性

- **平台拓展**：Observer 层抽象，Windows/Linux 可实现各自adapter
- **Gateway 拓展**：实现 Gateway 接口即可添加新服务
- **存储后端**：Storage 接口抽象，可换 Postgres/Redis

## 7. 里程碑

1. **MVP**：系统事件观察 + 浏览器精细化观察 + VSCode/Android Studio 精细化观察 + 飞书观察 + LLM 解读 + CLI 交互 + Skill 自生成
2. **V1.0**：定时触发 + 飞书推送 + 记忆检索优化
3. **V1.1**：更多 APP 观察器支持
4. **V2.0**：跨平台支持 + 云端同步