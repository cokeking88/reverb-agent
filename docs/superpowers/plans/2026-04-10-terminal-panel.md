# Terminal Panel Implementation Plan

## Task 1: Create TUI Panel Module

**Files:**
- Create: `src/reverb_agent/ui/panel.py`

```python
"""Terminal UI panel for Reverb Agent."""

import asyncio
from datetime import datetime
from typing import List
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.console import Console
from rich.live import Live
from rich.table import Table

from reverb_agent.observers.events import ObserverEvent


class TerminalPanel:
    """Terminal UI panel with event stream and thoughts."""
    
    def __init__(self):
        self._events: List[ObserverEvent] = []
        self._thoughts: List[str] = []
        self._memories: List[str] = []
        self._console = Console()
        self._layout = None
    
    def add_event(self, event: ObserverEvent) -> None:
        self._events.append(event)
        if len(self._events) > 20:
            self._events.pop(0)
    
    def add_thought(self, thought: str) -> None:
        self._thoughts.append(thought)
        if len(self._thoughts) > 10:
            self._thoughts.pop(0)
    
    def add_memory(self, memory: str) -> None:
        self._memories.append(memory)
        if len(self._memories) > 10:
            self._memories.pop(0)
    
    def _render_event_panel(self) -> Panel:
        table = Table(show_header=False, box=None)
        table.add_column(style="cyan", width=20)
        table.add_column(style="white")
        
        for event in reversed(self._events[-10:]):
            time = datetime.fromtimestamp(event.timestamp).strftime("%H:%M")
            source = event.source.get("app") or event.source.get("file", "N/A")[:30]
            table.add_row(f"[{time}]", f"{event.observer}: {source}")
        
        return Panel(
            table,
            title="[bold]Event Stream[/]",
            border_style="blue"
        )
    
    def _render_thought_panel(self) -> Panel:
        text = Text()
        for thought in reversed(self._thoughts[-5:]):
            text.append(f"• {thought}\n", style="yellow")
        
        return Panel(
            text or Text("等待分析...", style="dim"),
            title="[bold]Thoughts[/]",
            border_style="yellow"
        )
    
    def _render_memory_panel(self) -> Panel:
        text = Text()
        for memory in reversed(self._memories[-5:]):
            text.append(f"• {memory[:50]}...\n", style="green")
        
        return Panel(
            text or Text("暂无记忆", style="dim"),
            title="[bold]Memories[/]",
            border_style="green"
        )
    
    def _render_status_panel(self) -> Panel:
        return Panel(
            "Observers: active\nLLM: ready",
            title="[bold]Status[/]",
            border_style="green"
        )
    
    def _build_layout(self) -> Layout:
        layout = Layout()
        
        layout.split_column(
            Layout(name="top", size=20),
            Layout(name="bottom")
        )
        
        layout["top"].split_row(
            Layout(name="events", ratio=1),
            Layout(name="thoughts", ratio=1)
        )
        
        layout["bottom"].split_row(
            Layout(name="memories", ratio=2),
            Layout(name="status", ratio=1)
        )
        
        return layout
    
    async def run(self) -> None:
        """Run the terminal panel."""
        self._layout = self._build_layout()
        
        with Live(self._layout, refresh_per_second=2, console=self._console) as live:
            while True:
                self._layout["events"].update(self._render_event_panel())
                self._layout["thoughts"].update(self._render_thought_panel())
                self._layout["memories"].update(self._render_memory_panel())
                self._layout["status"].update(self._render_status_panel())
                await asyncio.sleep(0.5)
```

- [ ] **Step 1: Create panel.py**
- [ ] **Step 2: Update __init__.py exports**
- [ ] **Step 3: Test the panel**
- [ ] **Step 4: Commit**

## Task 2: Integrate with CLI

**Files:**
- Modify: `src/reverb_agent/cli.py`

- [ ] **Step 1: Add panel imports and --panel option**
- [ ] **Step 2: Run panel when observe --panel**
- [ ] **Step 3: Connect events to panel**
- [ ] **Step 4: Commit**

---

## Summary

- 使用 Rich 库的 Live 实现实时终端面板
- 左侧事件流，右侧思考和记忆
- 定时刷新显示