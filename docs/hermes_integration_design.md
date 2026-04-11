# Hermes Agent 闭环学习机制与 Reverb 集成原理

本文档详细说明了我们如何借鉴开源项目 `NousResearch/hermes-agent` 的核心架构，并将其（闭环学习与自动技能生成）移植到了当前的 `pc个人助手` (Reverb Agent) 中。

## 1. 核心问题与背景

之前的 Reverb Agent 主要是一个“被动观察者”。它监听系统的 UI 事件（点击、输入、网页焦点），并通过 LLM 总结用户“刚刚做了什么”。
但是它缺乏：
1. **跨会话的长期记忆 (Cross-Session Recall)**：它只能看到当前时刻（滑动窗口内的几十个事件），一旦关闭重启，或者用户去做了别的任务，它就完全失去了前置上下文。
2. **知识沉淀 (Procedural Memory)**：即使它观察到用户完成了一个非常高价值的“完整工作流”（比如每次上线前固定执行 `git fetch -> build -> 填写飞书表格`），它也只会把这些动作作为一条文本记录在数据库中，**不会转化为可以被自己复用的执行脚本**。

Hermes Agent 解决了这些问题。它被称为“具有内置学习循环 (built-in learning loop)” 的 Agent。通过借鉴它，我们将 Reverb Agent 的能力从“被动总结”升级为“主动学习与技能提炼”。

---

## 2. 第一阶段：引入 FTS5 实现海量历史事件的毫秒级召回 (Session Search)

在 Hermes 中，所有的会话记录都存储在 SQLite 数据库中，并且启用了 **FTS5 (Full-Text Search)** 虚拟表。
为什么使用 FTS5 而不是传统的向量数据库 (Vector DB/FAISS/Chroma)？
- **极低的资源消耗**：FTS5 是 SQLite 原生支持的，不需要启动任何外部服务，内存开销几乎为零。
- **精确关键词匹配**：对于代码片段、错误日志、特定的函数名（如 `execute_skill`），全文索引（BM25 算法）往往比基于语义相似度的 Embedding 模型找得更准。

### 我们在 Reverb 中的实现：
我们在 `src/reverb_agent/agent/memory.py` 中重构了 `MemoryStore`：
1. **自动创建虚拟表**：创建了 `event_log_fts` 和 `memories_fts` 两张基于 FTS5 的虚拟表。
2. **触发器 (Triggers) 自动同步**：利用 SQLite 原生的 `CREATE TRIGGER`，每当 `event_log` 表插入新事件时，数据库会在引擎层自动把文本内容（`source`, `data`, `event_type` 等）同步到 FTS 虚拟表中。这使得代码完全解耦，不需要在应用层手动双写。
3. **平滑数据迁移 (Backfill)**：针对用户已有的 `reverb.db` 历史数据，我们编写了启动时检查逻辑，如果发现 FTS 表为空，则会自动执行 `INSERT INTO ... SELECT FROM` 将历史记录一次性编入索引。

通过 `reverb search "关键词"` 这个新添加的 CLI 命令，用户现在可以瞬间检索过去几个月的任何点击和浏览历史，并按匹配相关度 (Rank) 排序。

---

## 3. 第二阶段：LLM 上下文 RAG 注入 (Context Retrieval)

有了底层的 FTS5 引擎，我们如何让 LLM “记起”过去的经验？
借鉴 Hermes 的 `Session Search Tool`，我们在 `AgentLoop._analyze_events_stream` 中实现了 **RAG (Retrieval-Augmented Generation) 历史事件相似度召回**。

### 工作流：
1. **动态提词**：当 AgentLoop 收集到最近的 80 个 UI 事件准备发送给 LLM 时，它会主动截取**最后 5 个事件**的关键特征（例如网页的 Title，或者点击的 Button ID）。
2. **FTS 隐式查询**：使用正则表达式将这些特征清理为安全的关键词，拼接成 `OR` 搜索语句，向 FTS5 引擎查询**过去发生过的相似事件**（Cross-session Recall）。
3. **Prompt 注入**：将搜索到的最高相关度（Rank 最高的 5 条）历史事件，拼接在系统 Prompt 的 `【跨会话历史相似事件】` 区域。

**效果**：现在，当用户在 Chrome 里打开了 "AWS Console"，如果三个月前用户也打开过并在里面进行过复杂的 IAM 权限配置，LLM 在分析当前屏幕时，会“看到”那条三个月前的历史记录，从而准确推断用户的意图：“你是不是又要配置 IAM 角色了？”

---

## 4. 第三阶段：自动技能生成闭环 (Autonomous Skill Creation)

Hermes 的核心亮点是 **Procedural Memory (程序性记忆)**。它把总结性的知识存入通用记忆（MEMORY.md），把“如何完成某项具体任务的操作步骤”存入技能夹（Skills Hub / `SKILL.md`）。

在 Reverb Agent 中，我们之前有一个手动的 `SkillManager`（通过 JSON 管理操作步骤），但它从未与 LLM 直接连通。

### 我们在 Reverb 中的实现：
1. **扩展 System Prompt Schema**：我们在要求 LLM 返回的 JSON 格式中，强制注入了一个可选字段 `"new_skill"`：
   ```json
   "new_skill": {
     "name": "技能名称（如：发送工作周报）",
     "description": "详细描述该技能的作用",
     "trigger": "触发条件或用户可能说的指令",
     "steps": [
       {"action": "click", "params": {"element": "button_id"}},
       {"action": "api_post", "params": {"url": "/api/v1/submit", "body": "JSON payload"}}
     ]
   }
   ```
   并明确指导 LLM：**“如果你观察到用户完成了一系列重复性或具有明确目标的操作（如通过UI点击、输入、网络请求完成了一个多步任务），你应该将其总结为一个可复用的技能。”**

2. **打通解析回调**：在 `cli.py` 初始化时，我们将 `SkillManager` 实例传递给了 `AgentLoop`。在处理 LLM 返回结果时，如果发现 JSON 中包含了合法的 `new_skill`，代码会在后台静默调用 `self.skill_manager.create_skill(...)`。

3. **自动固化**：这些被捕获的工作流会被持久化到 `~/.reverb-agent/data/skills/*.json` 中。
4. **UI 增强**：如果成功提炼了技能，Agent 会在 Web UI 面板的 Thoughts 里主动提示用户：`✨ 新增了自动技能：XXXX`。

## 总结

经过这次集成，Reverb Agent 完成了从 **"Observer (监控者)"** 到 **"Learner (学习者)"** 的蜕变：

1. 监控系统收集用户的离散 UI 事件与 API 流量。
2. 遇到触发点，将其转化为查询词，向 FTS5 索要**长程历史相关记录**。
3. 将当前窗口事件 + 历史召回上下文一并发送给 LLM。
4. LLM 如果识别到工作流完结，直接返回结构化的 `new_skill`。
5. 引擎捕获 `new_skill`，自动在本地文件系统固化该技能。
6. 未来当用户发出类似指令时，即可直接调用 `execute_skill`。

这正是 Autonomous AI Agents 闭环学习的最简优雅实现模式。

## 5. 第四阶段：多级记忆系统 (Multi-Level Cognitive Memory)
我们在 `AgentLoop` 中划分了四级认知层级：
1. **User Profile (用户画像)**：用户偏好的工作流与习惯。
2. **Semantic (语义规则)**：系统规则、项目结构上下文。
3. **Episodic (情景记忆)**：通过 FTS5 召回的跨会话相似历史事件。
4. **Procedural (程序记忆)**：已经固化提炼的可用技能列表。

这使得大模型能更立体地理解用户的当前操作，实现类似于 Hermes 的 Honcho (多模态分层记忆) 功能。
