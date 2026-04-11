"""Agent Loop for event processing and learning."""

import asyncio
import json
import concurrent.futures
import uuid
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
        import threading
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
        if event.type in ["file_focus", "page_focus", "window_focus"]:
            logger.info(f"Scheduling LLM analysis for: {event.type} (debounced)")

            # To avoid threading event loop complications completely,
            # let's revert to a robust asyncio approach and just add it
            # to the global event loop properly

            if self._debounce_task and not self._debounce_task.done():
                self._debounce_task.cancel()

            # Schedule a proper async debounce safely
            try:
                # Always use self._main_loop which we set from cli.py
                if self._main_loop is None:
                    try:
                        self._main_loop = asyncio.get_event_loop()
                    except RuntimeError:
                        # Fallback if no loop is available at all
                        pass

                if self._main_loop and self._main_loop.is_running():
                    import threading
                    # Check if we are running in the main thread with the main event loop
                    if threading.current_thread() is threading.main_thread():
                        self._debounce_task = self._main_loop.create_task(self._debounced_process_events())
                    else:
                        # Thread-safe scheduling to the main event loop
                        self._debounce_task = asyncio.run_coroutine_threadsafe(
                            self._debounced_process_events(), self._main_loop
                        )

                    if hasattr(self._debounce_task, 'add_done_callback'):
                        self._analysis_tasks.add(self._debounce_task)
                        self._debounce_task.add_done_callback(self._analysis_tasks.discard)
                else:
                    logger.error("Failed to schedule debounce: No running main event loop found.")
            except Exception as e:
                logger.error(f"Failed to schedule debounce: {e}")

    async def _debounced_process_events(self) -> None:
        """Delay execution of processing to debounce frequent focus events."""
        try:
            await asyncio.sleep(self._debounce_delay)
            logger.info("Debounce sleep finished, executing process_events")
            await self._process_events()
        except asyncio.CancelledError:
            # Task was cancelled by a subsequent focus event, ignore
            pass
        except Exception as e:
            logger.error(f"Error in debounced processing: {e}")

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
        event_summary = "\n".join([
            f"- {e.observer}: {e.type} - {e.source.get('app', e.source.get('file', e.source.get('url', 'N/A')))}"
            for e in events[-10:]
        ])
        logger.info(f"Sending to LLM: {event_summary[:100]}...")
        
        system_prompt = """你是一个工作助手。分析用户事件。

直接返回以下格式的JSON，不要其他内容：
{"should_remember": false, "summary": "简单总结", "type": "episodic", "tags": [], "should_ask_user": false, "question": ""}"""
        
        messages = [{"role": "user", "content": f"事件:\n{event_summary}"}]
        
        try:
            response = await self.llm.chat(messages, system_prompt)
            logger.info(f"LLM Response: {response.content[:200]}...")
            return json.loads(response.content)
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