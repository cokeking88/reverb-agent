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
from reverb_agent.agent.skills import SkillManager
from reverb_agent.logging import logger


class AgentLoop:
    """Agent loop for processing observer events and learning."""

    def __init__(self, llm_client: LLMClient, memory_store: MemoryStore, skill_manager: SkillManager = None):
        self.llm = llm_client
        self.memory = memory_store
        self.skill_manager = skill_manager
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

            # Autonomous Skill Creation
            if self.skill_manager and analysis.get("new_skill"):
                skill_data = analysis.get("new_skill")
                if isinstance(skill_data, dict) and "name" in skill_data and "steps" in skill_data:
                    logger.info(f"Creating autonomous skill: {skill_data['name']}")
                    self.skill_manager.create_skill(
                        name=skill_data.get("name", "Auto Skill"),
                        description=skill_data.get("description", "Autonomous generated skill"),
                        trigger=skill_data.get("trigger", ""),
                        steps=skill_data.get("steps", [])
                    )
                    # Tell user about it via summary
                    summary += f"\n✨ 新增了自动技能：{skill_data['name']}"

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
        for e in events[-80:]: # Increased from 50 to 80 events to capture longer workflows
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
            elif e.type == "page_focus":
                title = e.data.get("title", "")
                content_preview = ""
                if "content" in e.data and e.data["content"]:
                    content_preview = e.data["content"][:4000].replace('\n', ' ').strip()

                extra_info = f" [Title: '{title}'"
                if content_preview:
                    # Cap historical events context to prevent prompt injection and token explosion
                    extra_info += f", Page content snippet: '{content_preview[:800]}...']"
                else:
                    extra_info += "]"

            event_lines.append(f"- {e.observer}: {e.type} - {source_info}{extra_info}")

        # Add full context for the *current* focused page only
        last_event = events[-1] if events else None
        if last_event and last_event.type == "page_focus" and "content" in last_event.data and last_event.data["content"]:
            full_content = last_event.data["content"][:4000].replace('\n', ' ').strip()
            event_lines.append(f"\n--- CURRENT FOCUSED PAGE CONTENT ---\n{full_content}\n----------------------------------")

        event_summary = "\n".join(event_lines)
        logger.info(f"Sending to LLM: {event_summary[:100]}...")

        # Get recent memories to build context
        recent_memories = self.memory.get_memories(limit=10)
        memory_lines = [f"- [{m.memory_type}] {m.content}" for m in recent_memories]

        # Use FTS5 to search for relevant historical events matching the current context
        # This gives the agent "long-term cross-session recall" based on the last few events
        fts_context = ""
        if len(events) >= 2:
            search_terms = []
            for e in events[-5:]:
                if e.type == "page_focus" and "title" in e.data:
                    search_terms.append(e.data["title"][:20])
                elif e.type == "user_action" and "element" in e.data:
                    search_terms.append(str(e.data["element"])[:20])

            if search_terms:
                # Clean up search terms for FTS MATCH syntax (alphanumeric only, OR joined)
                import re
                clean_terms = [re.sub(r'[^a-zA-Z0-9\s]', ' ', term).strip() for term in search_terms if term]
                valid_terms = [t for t in clean_terms if len(t) > 2]

                if valid_terms:
                    # Search historical events
                    query = " OR ".join(valid_terms)
                    try:
                        past_events = self.memory.search_events_fts(query, limit=5)
                        if past_events:
                            fts_lines = []
                            for p in past_events:
                                source = str(p['source'])[:30]
                                fts_lines.append(f"- {p['observer']}:{p['event_type']} @ {source} (Rank {abs(p['rank']):.2f})")
                            fts_context = "【跨会话历史相似事件】\n" + "\n".join(fts_lines) + "\n\n"
                    except Exception as ex:
                        logger.warning(f"FTS search failed: {ex}")

        memory_context = "没有任何历史记忆。" if not memory_lines else "最近记忆：\n" + "\n".join(memory_lines)
        if fts_context:
            memory_context = fts_context + memory_context

        system_prompt = f"""你是一个智能工作助手，负责分析用户当前的屏幕和操作上下文事件。

【用户的历史记忆】（这是用户之前完成的工作，帮助你理解他当前行为的连贯性）：
{memory_context}

【自动技能生成】（Autonomous Skill Creation）：
如果你观察到用户完成了一系列重复性或具有明确目标的操作（如通过UI点击、输入、网络请求完成了一个多步任务），你应该将其总结为一个可复用的技能。技能是针对特定目标的过程性知识。

传入的事件序列包含：
- 窗口与网页焦点的切换（Page content snippet 提供了网页的实质正文内容）
- 网页内按钮点击与 API 网络请求 (network_api)
- IDE 代码编辑与运行断点 (ide_debug/run)

请结合【历史记忆】和最新的事件流进行思考，如果支持 <think> 标签，请使用 <think> 标签输出思考过程。然后直接返回以下格式的纯JSON文本，不要包裹在Markdown的```json ```里：
{{
  "should_remember": true/false,
  "summary": "简单总结当前用户正在做的事情，包含上下文背景和目的（不超过50字）",
  "type": "episodic/semantic",
  "tags": ["tag1", "tag2"],
  "should_ask_user": true/false,
  "question": "如果你看到用户的行为有特殊的意图但不确定，可以生成一个简短问题询问用户（比如：'你正在查阅并发相关的资料，是遇到了多线程bug吗？'），如果非常明确则留空",
  "new_skill": {{
    "name": "技能名称（如：发送工作周报）",
    "description": "详细描述该技能的作用",
    "trigger": "触发条件或用户可能说的指令",
    "steps": [
      {{"action": "click", "params": {{"element": "button_id"}}}},
      {{"action": "api_post", "params": {{"url": "/api/v1/submit", "body": "JSON payload"}}}}
    ]
  }} // 如果不需要生成新技能，则省略 new_skill 字段
}}

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
