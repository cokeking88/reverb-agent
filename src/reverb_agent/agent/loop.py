"""Agent Loop for event processing and learning."""

import asyncio
import json
import uuid
from typing import List, Optional, Callable
from reverb_agent.observers.events import ObserverEvent
from reverb_agent.agent.llm import LLMClient
from reverb_agent.agent.memory import MemoryStore


class AgentLoop:
    """Agent loop for processing observer events and learning."""
    
    def __init__(self, llm_client: LLMClient, memory_store: MemoryStore, loop=None):
        self.llm = llm_client
        self.memory = memory_store
        self._event_buffer: List[ObserverEvent] = []
        self._callback: Optional[Callable] = None
        self._session_id = memory_store.create_session()
        self._loop = loop or asyncio.get_event_loop()
    
    def on_event(self, event: ObserverEvent) -> None:
        """Receive events from observers."""
        print(f"[DEBUG] on_event called for {event.type}")
        self._event_buffer.append(event)
        # 记录到数据库
        self.memory.add_event(
            self._session_id,
            event.observer,
            event.type,
            event.source,
            event.data
        )
        
        # 重要事件立即处理 - use existing event loop
        if event.type in ["file_focus", "page_focus", "window_focus"]:
            if self._loop.is_running():
                self._loop.create_task(self._process_events())
            else:
                # Loop not running - run directly
                asyncio.run(self._process_events())
    
    async def _process_events(self) -> None:
        """Process buffered events."""
        print(f"[DEBUG] _process_events called with {len(self._event_buffer)} events")
        print(f"[DEBUG] LLM client: {self.llm}")
        if not self._event_buffer:
            return
        
        events = self._event_buffer.copy()
        self._event_buffer.clear()
        
        try:
            analysis = await self._analyze_events(events)
            print(f"[DEBUG] Analysis result: {analysis}")
            
            if analysis.get("should_remember"):
                self.memory.add_memory(
                    content=analysis.get("summary", ""),
                    memory_type=analysis.get("type", "episodic"),
                    tags=analysis.get("tags", [])
                )
            
            if analysis.get("should_ask_user") and self._callback:
                q = analysis.get("question", "")
                print(f"[DEBUG] Calling callback with: {q}")
                self._callback(q)
        except Exception as e:
            print(f"[DEBUG] Error processing events: {e}")
    
    async def _analyze_events(self, events: List[ObserverEvent]) -> dict:
        """Use LLM to analyze events."""
        event_summary = "\n".join([
            f"- {e.observer}: {e.type} - {e.source.get('app', e.source.get('file', e.source.get('url', 'N/A')))}"
            for e in events[-10:]
        ])
        
        system_prompt = """你是一个工作助手。分析用户事件。

直接返回以下格式的JSON，不要其他内容：
{"should_remember": false, "summary": "简单总结", "type": "episodic", "tags": [], "should_ask_user": false, "question": ""}"""
        
        messages = [{"role": "user", "content": f"事件:\n{event_summary}"}]
        
        try:
            response = await self.llm.chat(messages, system_prompt)
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {
                "should_remember": False,
                "should_ask_user": True,
                "question": "LLM返回格式错误"
            }
        except Exception as e:
            # Return error info so it can be displayed
            return {
                "should_remember": False, 
                "error": str(e)[:100],
                "should_ask_user": True,
                "question": f"LLM错误: {str(e)[:50]}"
            }
    
    def set_callback(self, callback: Callable) -> None:
        """Set callback for user questions."""
        self._callback = callback