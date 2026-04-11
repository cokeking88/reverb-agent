"""Agent Loop for event processing and learning."""

import asyncio
import json
import concurrent.futures
import uuid
import threading
from typing import List, Optional, Callable
from reverb_agent.observers.events import ObserverEvent
from reverb_agent.agent.llm import LLMClient
from reverb_agent.agent.memory import MemoryStore
from reverb_agent.logging import logger


class AgentLoop:
    """Agent loop for processing observer events and learning."""
    
    def __init__(self, llm_client: LLMClient, memory_store: MemoryStore):
        self.llm = llm_client
        self.memory = memory_store
        self._event_buffer: List[ObserverEvent] = []
        self._callback: Optional[Callable] = None
        self._session_id = memory_store.create_session()
        self._analysis_tasks = set()
        self._debounce_task: Optional[asyncio.Task] = None
        self._debounce_delay = 2.0
        self._main_loop = None
        self._thread_lock = threading.Lock()
        logger.info("AgentLoop initialized")

    def set_main_loop(self, loop):
        """Store reference to the main event loop to correctly dispatch from threads."""
        self._main_loop = loop

    def on_event(self, event: ObserverEvent) -> None:
        """Receive events from observers."""
        with self._thread_lock:
            self._event_buffer.append(event)
        logger.info(f"Event received: {event.type} - {event.source}")
        
        # 记录到数据库
        self.memory.add_event(
            self._session_id,
            event.observer,
            event.type,
            event.source,
            event.data
        )
        
        # 重要事件立即处理 - run async
        if event.type in ["file_focus", "page_focus", "window_focus", "user_action"]:
            logger.info(f"Scheduling LLM analysis for: {event.type} (debounced)")

            # To avoid threading event loop complications completely,
            # let's revert to a robust asyncio approach and just add it
            # to the global event loop properly

            if self._debounce_task and not self._debounce_task.done():
                self._debounce_task.cancel()

            # Schedule a proper async debounce safely
            try:
                # Setup debounce task state and lock
                with self._thread_lock:
                    if hasattr(self, '_debounce_cancel_event'):
                        self._debounce_cancel_event.set()

                    self._debounce_cancel_event = threading.Event()
                    cancel_evt = self._debounce_cancel_event

                # Check if we can safely just use asyncio.run_coroutine_threadsafe
                # with the main_loop that the cli set for us
                if self._main_loop and self._main_loop.is_running():
                    # Create a simple function to wait and then run
                    async def wait_then_run():
                        try:
                            # Wait asynchronously without blocking threads
                            await asyncio.sleep(self._debounce_delay)
                            if not cancel_evt.is_set():
                                logger.info("Debounce finished, running process_events")
                                await self._process_events()
                        except Exception as e:
                            logger.error(f"Error in delayed run: {e}")

                    # Schedule it safely into the main loop
                    self._debounce_task = asyncio.run_coroutine_threadsafe(
                        wait_then_run(), self._main_loop
                    )
                    return

                def _run_debounce_thread(cancel_event):
                    if cancel_event.wait(self._debounce_delay):
                        return # Cancelled

                    # Sleep finished, create a new event loop just for this execution
                    try:
                        logger.info("Debounce sleep finished, executing process_events in thread")
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self._process_events())
                    except Exception as e:
                        logger.error(f"Error executing debounced events: {e}")
                    finally:
                        try:
                            loop.close()
                        except:
                            pass

                # Start the dedicated thread
                t = threading.Thread(target=_run_debounce_thread, args=(cancel_evt,))
                t.daemon = True
                t.start()

            except Exception as e:
                logger.error(f"Failed to schedule debounce: {e}")

    # We can remove the unused async definition
    # async def _debounced_process_events(self) -> None:

    async def _process_events(self) -> None:
        """Process buffered events."""
        events = []
        with self._thread_lock:
            if not self._event_buffer:
                return

            events = self._event_buffer.copy()
            self._event_buffer.clear()

        logger.info(f"Processing {len(events)} events")

        # Don't proceed if events list is empty
        if not events:
            return

        try:
            analysis = await self._analyze_events(events)
            logger.info(f"LLM Analysis result: {analysis}")
            
            if analysis.get("should_remember"):
                summary = analysis.get("summary", "")
                memory_type = analysis.get("type", "episodic")
                tags = analysis.get("tags", [])
                logger.info(f"Adding memory: {summary[:50]}...")
                self.memory.add_memory(
                    content=summary,
                    memory_type=memory_type,
                    tags=tags
                )
            
            if analysis.get("should_ask_user") and self._callback:
                question = analysis.get("question", "")
                logger.info(f"LLM question: {question}")
                self._callback(question)
        except Exception as e:
            logger.error(f"Error processing events: {e}")
    
    async def _analyze_events(self, events: List[ObserverEvent]) -> dict:
        """Use LLM to analyze events."""
        event_lines = []
        for e in events[-10:]:
            source_info = e.source.get('app', e.source.get('file', e.source.get('url', 'N/A')))

            # Extract rich DOM info if available
            extra_info = ""
            if e.type == "user_action":
                action = e.data.get("action", "")
                element = e.data.get("element", "")
                text = e.data.get("text", "")
                value = e.data.get("value", "")
                extra_info = f" [Action: {action}, Element: {element}"
                if text: extra_info += f", Text: '{text}'"
                if value: extra_info += f", Value: '{value}'"
                extra_info += "]"
            elif e.type == "page_focus" and "content" in e.data:
                content_preview = e.data["content"][:100].replace('\n', ' ')
                extra_info = f" [Content preview: '{content_preview}...']"

            event_lines.append(f"- {e.observer}: {e.type} - {source_info}{extra_info}")

        event_summary = "\n".join(event_lines)
        logger.info(f"Sending to LLM: {event_summary[:100]}...")
        
        system_prompt = """你是一个工作助手，负责分析用户当前的屏幕和操作上下文事件。

通过一系列事件（包括窗口切换、网页焦点切换、网页内元素的点击、输入等操作），来理解用户正在做什么、在看什么内容。

请直接返回以下格式的纯JSON文本，不要包裹在Markdown的```json ```里：
{
  "should_remember": true/false,
  "summary": "简单总结当前用户正在做的事情（不超过30字）",
  "type": "episodic/semantic",
  "tags": ["tag1", "tag2"],
  "should_ask_user": true/false,
  "question": "如果有些意图非常不明确需要用户解答，则生成一个简短问题，否则留空"
}"""
        
        messages = [{"role": "user", "content": f"事件:\n{event_summary}"}]
        
        try:
            response = await self.llm.chat(messages, system_prompt)
            logger.info(f"LLM Response: {response.content[:200]}...")

            content = response.content.strip()
            # Handle markdown code blocks if the LLM ignores instructions
            if content.startswith("```json"):
                content = content[7:]
                if content.endswith("```"):
                    content = content[:-3]
            content = content.strip()

            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"LLM JSON decode error: {e}")
            return {
                "should_remember": False,
                "should_ask_user": True,
                "question": "LLM返回格式错误"
            }
        except Exception as e:
            logger.error(f"LLM call error: {e}")
            return {
                "should_remember": False, 
                "error": str(e)[:100],
                "should_ask_user": True,
                "question": f"LLM错误: {str(e)[:50]}"
            }
    
    def set_callback(self, callback: Callable) -> None:
        """Set callback for user questions."""
        self._callback = callback