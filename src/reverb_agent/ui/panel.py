"""Terminal UI panel for Reverb Agent."""

import asyncio
from datetime import datetime
from typing import List, Optional
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.console import Console
from rich.live import Live
from rich.prompt import Prompt

from reverb_agent.observers.events import ObserverEvent
from reverb_agent.logging import logger


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

        # Interactive features
        self._current_question: Optional[str] = None
        self._on_user_reply_callback: Optional[callable] = None
    
    def add_event(self, event: ObserverEvent) -> None:
        self._events.append(event)
        if len(self._events) > 30:
            self._events.pop(0)
    
    def add_thought(self, thought: str) -> None:
        self._thoughts.append(thought)
        if len(self._thoughts) > 15:
            self._thoughts.pop(0)
    
    def add_status_message(self, message: str, is_error: bool = False) -> None:
        """Add a status message to show in status panel."""
        prefix = "[red]✗[/red] " if is_error else "[green]✓[/green] "
        self._status = prefix + message
    
    def add_memory(self, memory: str) -> None:
        self._memories.append(memory)
        if len(self._memories) > 15:
            self._memories.pop(0)

    def set_question(self, question: str, callback: callable) -> None:
        """Set a question from LLM to ask the user."""
        self._current_question = question
        self._on_user_reply_callback = callback
        self.update_status(f"Action needed: Press 'y' to reply to question.")

    def clear_question(self) -> None:
        """Clear the current question."""
        self._current_question = None
        self._on_user_reply_callback = None
        self.update_status("Monitoring events...")

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

        if self._current_question:
            text.append("\n[bold cyan]💡 Question for you:[/]\n", style="cyan")
            text.append(f"{self._current_question}\n", style="cyan")
            text.append("[dim]Press 'r' to reply or 'i' to ignore[/dim]", style="dim")

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

        # Input handling task
        self._input_task = asyncio.create_task(self._keyboard_listener())

        # Track counts to detect changes
        last_event_count = 0
        last_thought_count = 0
        last_memory_count = 0
        last_status = ""
        last_question = None
        
        self._console.clear()
        
        try:
            # Lower refresh rate since we only update on changes
            with Live(self._layout, refresh_per_second=1, console=self._console) as live:
                while self._running:
                    try:
                        changed = False
                        
                        # Check each panel and only update if changed
                        if len(self._events) != last_event_count:
                            self._layout["events"].update(self._render_event_panel())
                            last_event_count = len(self._events)
                            changed = True
                        
                        if len(self._thoughts) != last_thought_count or self._current_question != last_question:
                            self._layout["thoughts"].update(self._render_thought_panel())
                            last_thought_count = len(self._thoughts)
                            last_question = self._current_question
                            changed = True
                        
                        if len(self._memories) != last_memory_count:
                            self._layout["memories"].update(self._render_memory_panel())
                            last_memory_count = len(self._memories)
                            changed = True
                        
                        if self._status != last_status:
                            self._layout["status"].update(self._render_status_panel())
                            last_status = self._status
                            changed = True
                        
                        # Only sleep if something changed, otherwise longer sleep
                        await asyncio.sleep(1.0 if changed else 2.0)
                    except Exception as e:
                        if self._running:
                            pass
                        else:
                            break
        except Exception:
            pass
    
    async def _keyboard_listener(self) -> None:
        """Listen for keyboard input in the background to handle interactive questions."""
        import sys
        import select
        import tty
        import termios

        # Store old settings
        fd = sys.stdin.fileno()
        try:
            old_settings = termios.tcgetattr(fd)
        except Exception:
            return # Probably not a real TTY

        try:
            tty.setcbreak(fd)
            while self._running:
                if select.select([sys.stdin], [], [], 0.5)[0]:
                    char = sys.stdin.read(1)
                    if char == 'r' and self._current_question:
                        # Restore terminal for normal prompt
                        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

                        # Use a clean line under the UI to ask
                        self._console.print(f"\n[cyan]{self._current_question}[/cyan]")
                        reply = Prompt.ask("[yellow]Your reply (empty to cancel)[/yellow]")

                        if reply and self._on_user_reply_callback:
                            try:
                                # Dispatch reply safely
                                self._on_user_reply_callback(reply)
                            except Exception as e:
                                logger.error(f"Error invoking reply callback: {e}")

                        self.clear_question()
                        # Set back to cbreak for listening again
                        tty.setcbreak(fd)
                    elif char == 'i' and self._current_question:
                        self.clear_question()

                await asyncio.sleep(0.1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def stop(self) -> None:
        """Stop the panel."""
        self._running = False
