"""Terminal UI panel for Reverb Agent."""

import asyncio
from datetime import datetime
from typing import List, Optional
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.console import Console
from rich.live import Live

from reverb_agent.observers.events import ObserverEvent


class TerminalPanel:
    """Terminal UI panel with event stream and thoughts."""
    
    def __init__(self):
        self._events: List[ObserverEvent] = []
        self._thoughts: List[str] = []
        self._memories: List[str] = []
        self._status: str = "Initializing..."
        self._console = Console()
        self._layout: Optional[Layout] = None
        self._running = False
    
    def add_event(self, event: ObserverEvent) -> None:
        self._events.append(event)
        if len(self._events) > 30:
            self._events.pop(0)
    
    def add_thought(self, thought: str) -> None:
        self._thoughts.append(thought)
        if len(self._thoughts) > 15:
            self._thoughts.pop(0)
    
    def add_memory(self, memory: str) -> None:
        self._memories.append(memory)
        if len(self._memories) > 15:
            self._memories.pop(0)
    
    def update_status(self, status: str) -> None:
        self._status = status
    
    def _render_event_panel(self) -> Panel:
        """Render event stream panel."""
        from rich.table import Table
        
        table = Table(show_header=False, box=None)
        table.add_column(style="cyan", width=8)
        table.add_column(style="white")
        
        for event in reversed(self._events[-15:]):
            time = datetime.fromtimestamp(event.timestamp).strftime("%H:%M:%S")
            source = event.source.get("app") or event.source.get("file", event.source.get("url", "N/A"))
            if len(source) > 35:
                source = source[:35] + "..."
            table.add_row(f"[dim]{time}[/]", f"{event.observer}: {source}")
        
        return Panel(
            table,
            title="[bold]Event Stream[/]",
            border_style="blue",
            padding=(0, 1)
        )
    
    def _render_thought_panel(self) -> Panel:
        """Render thoughts panel."""
        text = Text()
        for thought in reversed(self._thoughts[-8:]):
            text.append(f"• {thought}\n\n", style="yellow")
        
        return Panel(
            text or Text("Waiting for analysis...", style="dim"),
            title="[bold]Thoughts[/]",
            border_style="yellow",
            padding=(0, 1)
        )
    
    def _render_memory_panel(self) -> Panel:
        """Render memories panel."""
        text = Text()
        for memory in reversed(self._memories[-8:]):
            mem_text = memory[:60] + "..." if len(memory) > 60 else memory
            text.append(f"• {mem_text}\n", style="green")
        
        return Panel(
            text or Text("No memories yet", style="dim"),
            title="[bold]Memories[/]",
            border_style="green",
            padding=(0, 1)
        )
    
    def _render_status_panel(self) -> Panel:
        """Render status panel."""
        return Panel(
            f"[cyan]{self._status}[/cyan]",
            title="[bold]Status[/]",
            border_style="green",
            padding=(0, 1)
        )
    
    def _build_layout(self) -> Layout:
        """Build the layout structure."""
        layout = Layout()
        
        layout.split_column(
            Layout(name="top", ratio=3),
            Layout(name="bottom", ratio=1)
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
        self._running = True
        self._layout = self._build_layout()
        
        self._console.clear()
        
        try:
            with Live(self._layout, refresh_per_second=4, console=self._console) as live:
                while self._running:
                    try:
                        self._layout["events"].update(self._render_event_panel())
                        self._layout["thoughts"].update(self._render_thought_panel())
                        self._layout["memories"].update(self._render_memory_panel())
                        self._layout["status"].update(self._render_status_panel())
                        await asyncio.sleep(0.25)
                    except Exception as e:
                        if self._running:
                            pass
                        else:
                            break
        except Exception:
            pass
    
    def stop(self) -> None:
        """Stop the panel."""
        self._running = False
