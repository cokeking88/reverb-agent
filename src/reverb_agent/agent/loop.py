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
        self._stream_callback: Optional[Callable] = None
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
        if event.type in ["file_focus", "page_focus", "window_focus", "user_action", "user_reply"]:
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
            # We first broadcast that analysis is starting
            if self._stream_callback:
                self._stream_callback("start", "")

            # Modified _analyze_events to handle streaming
            analysis = await self._analyze_events_stream(events)
            logger.info(f"LLM Analysis result: {analysis}")

            if self._stream_callback:
                self._stream_callback("end", "")

            # Clear the stream after processing successfully
            if self._stream_callback:
                self._stream_callback("clear", "")

            if analysis.get("should_remember"):
                summary = analysis.get("summary", "")
                if summary:
                    memory_type = analysis.get("type", "episodic")
                    tags = analysis.get("tags", [])
                    logger.info(f"Adding memory: {summary[:50]}...")
                    self.memory.add_memory(
                        content=summary,
                        memory_type=memory_type,
                        tags=tags
                    )
            else:
                summary = analysis.get("summary", "")
            
            if analysis.get("should_ask_user") and self._callback:
                question = analysis.get("question", "")
                if question:
                    logger.info(f"LLM question: {question}")

                    # Provide a callback for when the user replies
                    def on_reply(user_answer: str):
                        logger.info(f"User replied: {user_answer}")
                        # Dispatch to loop as a system user_action
                        with self._thread_lock:
                            self._event_buffer.append(ObserverEvent(
                                observer="system",
                                type="user_reply",
                                source={"app": "Reverb", "url": "N/A"},
                                data={"question": question, "reply": user_answer}
                            ))
                        if self._main_loop and self._main_loop.is_running():
                            asyncio.run_coroutine_threadsafe(self._process_events(), self._main_loop)

                    self._callback(thought=summary, question=question, reply_callback=on_reply)
                else:
                    self._callback(thought=summary, question=None, reply_callback=None)
            elif self._callback:
                self._callback(thought=summary, question=None, reply_callback=None)
        except Exception as e:
            logger.error(f"Error processing events: {e}")
    
    async def _analyze_events(self, events: List[ObserverEvent]) -> dict:
        """Fallback method using standard chat for compatibility."""
        return await self._analyze_events_stream(events)

    async def _analyze_events_stream(self, events: List[ObserverEvent]) -> dict:
        """Use LLM to analyze events with streaming."""
        event_lines = []
        for e in events[-50:]:
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
            elif e.type == "user_reply":
                q = e.data.get("question", "")
                r = e.data.get("reply", "")
                extra_info = f" [LLM Asked: '{q}', User Replied: '{r}']"
            elif e.type == "page_focus" and "content" in e.data:
                content_preview = e.data["content"][:300].replace('\n', ' ')
                extra_info = f" [Content preview: '{content_preview}...']"

            event_lines.append(f"- {e.observer}: {e.type} - {source_info}{extra_info}")

        event_summary = "\n".join(event_lines)
        logger.info(f"Sending to LLM: {event_summary[:100]}...")
        
        system_prompt = """你是一个智能工作助手，负责分析用户当前的屏幕和操作上下文事件。

通过传入的这批事件（包括过去一段时间的窗口切换、网页焦点切换、网页内元素的点击、输入操作等），来理解用户正在经历的工作流或学习路径。

请先进行思考，如果支持 <think> 标签，请使用 <think> 标签输出思考过程。然后直接返回以下格式的纯JSON文本，不要包裹在Markdown的```json ```里：
{
  "should_remember": true/false,
  "summary": "简单总结当前用户正在做的事情，包含上下文背景和目的（不超过50字）",
  "type": "episodic/semantic",
  "tags": ["tag1", "tag2"],
  "should_ask_user": true/false,
  "question": "如果你看到用户的行为有特殊的意图但不确定，可以生成一个简短问题询问用户（比如：'你正在查阅并发相关的资料，是遇到了多线程bug吗？'），如果非常明确则留空"
}

注：should_remember请谨慎设置为true。只有当用户的操作构成一个完整的“经验、知识、习惯或者特定的工作流上下文”时，才需要记录。单纯的无意义网页浏览不要记录。"""
        
        messages = [{"role": "user", "content": f"事件:\n{event_summary}"}]
        
        try:
            full_content = ""
            async for chunk in self.llm.chat_stream(messages, system_prompt):
                # Only stream if it's a non-empty string
                if chunk is not None:
                    full_content += str(chunk)
                    if self._stream_callback:
                        self._stream_callback("chunk", str(chunk))

            logger.info(f"LLM Response: {full_content[:200]}...")

            content = full_content.strip()

            logger.info(f"Full content to parse: {content}")

            # Store the think content for display
            think_content = ""
            if "<think>" in content and "</think>" in content:
                think_content = content.split("</think>")[0].split("<think>")[-1].strip()
                content = content.split("</think>")[-1].strip()
            elif "</think>" in content:
                think_content = content.split("</think>")[0].replace("<think>", "").strip()
                content = content.split("</think>")[-1].strip()
            elif "<think>" in content:
                think_content = content.split("<think>")[-1].strip()
                content = "" # No JSON payload returned yet

            if think_content and self._callback:
                # Add the think block as a thought history item so it stays visible
                self._callback(thought=f"🧠 {think_content}", question=None, reply_callback=None)

            # Clean markdown block if present
            if not content:
                logger.warning("No JSON payload found after think block.")
                return {"should_remember": False, "should_ask_user": False}

            if "```json" in content:
                content = content.split("```json")[-1].strip()
            if "```" in content:
                content = content.split("```")[0].strip()

            # Double check it starts with { and ends with }
            content = content.strip()
            if content.startswith("{") and content.endswith("}"):
                pass # valid json bounds
            else:
                # Try to extract just the json part
                start_idx = content.find("{")
                end_idx = content.rfind("}")
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    content = content[start_idx:end_idx+1]
                else:
                    logger.error(f"Could not find valid JSON boundaries in: {content}")
                    raise json.JSONDecodeError("No valid JSON found", content, 0)

            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"LLM JSON decode error: {e}")
            if self._stream_callback:
                self._stream_callback("clear", "")
            return {
                "should_remember": False,
                "should_ask_user": True,
                "question": "LLM返回格式错误"
            }
        except Exception as e:
            logger.error(f"LLM call error: {e}")
            if self._stream_callback:
                self._stream_callback("clear", "")
            return {
                "should_remember": False,
                "error": str(e)[:100],
                "should_ask_user": True,
                "question": f"LLM错误: {str(e)[:50]}"
            }
    
    def set_callback(self, callback: Callable) -> None:
        """Set callback for user questions."""
        self._callback = callback

    def set_stream_callback(self, callback: Callable) -> None:
        """Set callback for streaming LLM thoughts."""
        self._stream_callback = callback
