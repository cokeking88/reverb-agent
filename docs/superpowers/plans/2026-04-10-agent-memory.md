# Agent Loop & Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现 Agent Loop（LLM 集成、事件理解、模式识别、Skill自生成）和 Memory 存储层。

**Tech Stack:** Python asyncio, OpenAI/Ollama SDK, SQLite (SQLAlchemy)

---

## File Structure

```
src/hermes_mac/
├── agent/
│   ├── __init__.py
│   ├── loop.py          # Agent Loop
│   ├── llm.py           # LLM client
│   ├── memory.py        # Memory storage
│   └── skills.py        # Skill management
└── cli.py               # Updated
```

---

### Task 1: Implement LLM Client

**Files:**
- Create: `src/hermes_mac/agent/llm.py`

**实现要求：**
1. 支持 Ollama 和 OpenAI 两种 provider
2. 流式输出支持
3. 配置从 config.py 读取

```python
"""LLM client for Ollama and OpenAI."""

import json
from typing import Optional, AsyncGenerator
from pydantic import BaseModel

try:
    import openai
except ImportError:
    openai = None


class LLMResponse(BaseModel):
    content: str
    model: str
    usage: Optional[dict] = None


class LLMClient:
    """Client for LLM providers."""
    
    def __init__(self, provider: str = "ollama", model: str = "llama3", 
                 endpoint: Optional[str] = None, api_key: Optional[str] = None):
        self.provider = provider
        self.model = model
        self.endpoint = endpoint
        self.api_key = api_key
        
        if provider == "openai" and openai:
            openai.api_key = api_key or "dummy"
            if endpoint:
                openai.base_url = endpoint
    
    async def chat(self, messages: list[dict], system: Optional[str] = None) -> LLMResponse:
        """Send chat request."""
        if self.provider == "ollama":
            return await self._ollama_chat(messages, system)
        elif self.provider == "openai" and openai:
            return await self._openai_chat(messages, system)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    async def _ollama_chat(self, messages: list[dict], system: Optional[str]) -> LLMResponse:
        import aiohttp
        url = f"{self.endpoint or 'http://localhost:11434'}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                data = await resp.json()
                return LLMResponse(
                    content=data.get("message", {}).get("content", ""),
                    model=self.model
                )
    
    async def _openai_chat(self, messages: list[dict], system: Optional[str]) -> LLMResponse:
        if system:
            messages = [{"role": "system", "content": system}] + messages
        response = await openai.ChatCompletion.acreate(
            model=self.model,
            messages=messages
        )
        return LLMResponse(
            content=response.choices[0].message.content,
            model=response.model,
            usage=response.usage.to_dict() if response.usage else None
        )
```

- [ ] **Step 1: Create llm.py**
- [ ] **Step 2: Add aiohttp to dependencies**
- [ ] **Step 3: Commit**

---

### Task 2: Implement Memory Storage

**Files:**
- Create: `src/hermes_mac/agent/memory.py`

**实现要求：**
1. SQLite 存储（使用 SQLAlchemy）
2. Memory 表：episodic, semantic, user_model 类型
3. Session 表：存储会话事件
4. CRUD 操作

```python
"""Memory storage using SQLite."""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Float, Integer, Text, create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class Memory(Base):
    """Memory record."""
    __tablename__ = "memories"
    
    id = Column(String, primary_key=True)
    content = Column(Text, nullable=False)
    memory_type = Column(String, default="episodic")  # episodic, semantic, user_model
    tags = Column(Text, default="")  # comma-separated
    created_at = Column(Float, default=func.time())
    updated_at = Column(Float, default=func.time())


class Session(Base):
    """Session record for event storage."""
    __tablename__ = "sessions"
    
    id = Column(String, primary_key=True)
    summary = Column(Text, default="")
    created_at = Column(Float, default=func.time())


class EventLog(Base):
    """Event log for a session."""
    __tablename__ = "event_log"
    
    id = Column(String, primary_key=True)
    session_id = Column(String)
    observer = Column(String)
    event_type = Column(String)
    timestamp = Column(Float)
    source = Column(Text)  # JSON
    data = Column(Text)    # JSON


class MemoryStore:
    """Memory storage manager."""
    
    def __init__(self, db_path: str):
        self.engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
    
    def add_memory(self, memory: Memory) -> None:
        with self.Session() as session:
            session.add(memory)
            session.commit()
    
    def get_memories(self, memory_type: Optional[str] = None, limit: int = 100) -> list[Memory]:
        with self.Session() as session:
            query = session.query(Memory)
            if memory_type:
                query = query.filter(Memory.memory_type == memory_type)
            return query.order_by(Memory.created_at.desc()).limit(limit).all()
    
    def add_event(self, event_log: EventLog) -> None:
        with self.Session() as session:
            session.add(event_log)
            session.commit()
```

- [ ] **Step 1: Create memory.py**
- [ ] **Step 2: Commit**

---

### Task 3: Implement Agent Loop

**Files:**
- Create: `src/hermes_mac/agent/loop.py`

**实现要求：**
1. 接收 Observer 事件
2. 定期调用 LLM 分析事件流
3. 发现模式并创建记忆
4. 主动询问用户

```python
"""Agent Loop for event processing and learning."""

import asyncio
from typing import List, Callable
from hermes_mac.observers.events import ObserverEvent
from hermes_mac.agent.llm import LLMClient
from hermes_mac.agent.memory import MemoryStore, Memory


class AgentLoop:
    """Agent loop for processing observer events and learning."""
    
    def __init__(self, llm_client: LLMClient, memory_store: MemoryStore):
        self.llm = llm_client
        self.memory = memory_store
        self._event_buffer: List[ObserverEvent] = []
        self._callback: Optional[Callable] = None
    
    def on_event(self, event: ObserverEvent) -> None:
        """Receive events from observers."""
        self._event_buffer.append(event)
        # 如果是重要事件（如文件切换），立即处理
        if event.type in ["file_focus", "page_focus", "window_focus"]:
            asyncio.create_task(self._process_events())
    
    async def _process_events(self) -> None:
        """Process buffered events."""
        if not self._event_buffer:
            return
        
        events = self._event_buffer.copy()
        self._event_buffer.clear()
        
        # 用 LLM 分析事件
        analysis = await self._analyze_events(events)
        
        if analysis.get("should_remember"):
            # 保存为记忆
            memory = Memory(
                id=analysis.get("id", ""),
                content=analysis.get("summary", ""),
                memory_type=analysis.get("type", "episodic"),
                tags=",".join(analysis.get("tags", []))
            )
            self.memory.add_memory(memory)
        
        if analysis.get("should_ask_user"):
            # 触发用户询问
            if self._callback:
                self._callback(analysis.get("question", ""))
    
    async def _analyze_events(self, events: List[ObserverEvent]) -> dict:
        """Use LLM to analyze events."""
        event_summary = "\n".join([
            f"- {e.observer}: {e.type} - {e.source.get('app', e.source.get('file', 'N/A'))}"
            for e in events[-10:]
        ])
        
        system_prompt = """你是一个工作助手。分析以下用户事件，判断是否需要记忆。

分析用户的行为模式，如果是重复性工作，考虑创建 Skill。
如果需要确认用户意图，提出问题。

返回 JSON:
{
  "should_remember": true/false,
  "summary": "事件总结",
  "type": "episodic/semantic",
  "tags": ["tag1", "tag2"],
  "should_ask_user": true/false,
  "question": "如果需要问用户问题"
}"""
        
        messages = [{"role": "user", "content": f"事件:\n{event_summary}"}]
        
        try:
            response = await self.llm.chat(messages, system_prompt)
            import json
            return json.loads(response.content)
        except:
            return {"should_remember": False}
    
    def set_callback(self, callback: Callable) -> None:
        """Set callback for user questions."""
        self._callback = callback
```

- [ ] **Step 1: Create loop.py**
- [ ] **Step 2: Commit**

---

### Task 4: Implement Skills System

**Files:**
- Create: `src/hermes_mac/agent/skills.py`

**实现要求：**
1. Skill 数据结构（trigger, steps）
2. Skill 存储（JSON 文件）
3. Skill 执行

```python
"""Skills management."""

import json
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime


class Step(BaseModel):
    """Skill step."""
    action: str
    params: dict = {}


class Skill(BaseModel):
    """Skill definition."""
    id: str
    name: str
    description: str
    trigger: str  # e.g., "every Monday morning"
    steps: List[Step]
    created_at: float = 0
    usage_count: int = 0
    version: int = 1


class SkillManager:
    """Skill manager."""
    
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self.skills_dir.mkdir(parents=True, exist_ok=True)
    
    def list_skills(self) -> List[Skill]:
        """List all skills."""
        skills = []
        for f in self.skills_dir.glob("*.json"):
            with open(f) as fp:
                skills.append(Skill(**json.load(fp)))
        return skills
    
    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """Get a skill by ID."""
        path = self.skills_dir / f"{skill_id}.json"
        if path.exists():
            with open(path) as fp:
                return Skill(**json.load(fp))
        return None
    
    def add_skill(self, skill: Skill) -> None:
        """Save a skill."""
        path = self.skills_dir / f"{skill.id}.json"
        with open(path, "w") as fp:
            json.dump(skill.model_dump(), fp, indent=2)
    
    async def execute_skill(self, skill_id: str) -> dict:
        """Execute a skill."""
        skill = self.get_skill(skill_id)
        if not skill:
            return {"error": f"Skill {skill_id} not found"}
        
        skill.usage_count += 1
        self.add_skill(skill)  # 更新使用次数
        
        return {"status": "executed", "skill": skill.name}
```

- [ ] **Step 1: Create skills.py**
- [ ] **Step 2: Commit**

---

### Task 5: Integrate with CLI

**Files:**
- Modify: `src/hermes_mac/cli.py`

**实现要求：**
1. 添加 `agent` 子命令启动 Agent Loop
2. 添加 `memory` 命令查看记忆
3. 添加 `skills` 命令查看技能

```python
@main.command()
def agent():
    """Start agent loop."""
    # 初始化 LLM, Memory, AgentLoop
    # 连接到 Observer 事件
    pass

@main.command()
def memory():
    """Show memories."""
    # 读取并显示记忆
    pass

@main.command()
def skills():
    """Show skills."""
    # 显示技能列表
    pass
```

- [ ] **Step 1: Update cli.py**
- [ ] **Step 2: Commit**

---

## Summary

- LLM Client: Ollama/OpenAI 支持
- Memory: SQLite 存储记忆
- Agent Loop: 事件分析、模式发现、主动询问
- Skills: 技能存储和执行
- CLI 集成