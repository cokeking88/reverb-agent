"""CLI entry point for Reverb Agent."""

import asyncio
import threading
import time

import click
from rich.console import Console
from rich.table import Table

from reverb_agent.config import load_config, save_config, AppConfig, ensure_data_dir
from reverb_agent.constants import DEFAULT_LLM_PROVIDER, DEFAULT_LLM_MODEL, IDE_OBSERVER_INTERVAL
from reverb_agent import __version__
from reverb_agent.agent import LLMClient, AgentLoop, MemoryStore, SkillManager
from pathlib import Path
from reverb_agent.observers import ObserverRegistry
from reverb_agent.observers.system import SystemObserver
from reverb_agent.observers.vscode import VSCodeObserver
from reverb_agent.observers.intellij import IntelliJObserver
from reverb_agent.observers.browser import BrowserObserver
from reverb_agent.observers.feishu import FeishuObserver
from reverb_agent.observers.events import ObserverEvent
from reverb_agent.ui import TerminalPanel

console = Console()


@click.group()
@click.version_option(version=__version__)
def main():
    """Reverb Agent: Learn from your work, help you grow."""
    pass


@main.command()
def status():
    """Show current status."""
    try:
        config = load_config()
    except Exception:
        console.print("[red]Failed to load config[/red]")
        return
    table = Table(title="Reverb Agent Status")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Data Directory", str(config.data_dir))
    table.add_row("LLM Provider", config.llm.provider)
    table.add_row("LLM Model", config.llm.model)
    table.add_row("Observers Enabled", str(config.observers.enabled))
    
    console.print(table)


@main.command()
@click.option("--provider", default=DEFAULT_LLM_PROVIDER, help="LLM provider (ollama, openai, openrouter)")
@click.option("--model", default=DEFAULT_LLM_MODEL, help="LLM model name")
@click.option("--endpoint", default=None, help="API endpoint URL")
@click.option("--api-key", default=None, help="API key")
def config_llm(provider, model, endpoint, api_key):
    """Configure LLM settings."""
    config = load_config()
    config.llm.provider = provider
    config.llm.model = model
    if endpoint:
        config.llm.endpoint = endpoint
    if api_key:
        config.llm.api_key = api_key
    save_config(config)
    console.print(f"[green]LLM configured: {provider}/{model}[/green]")


@main.command()
def init():
    """Initialize Reverb Agent data directory."""
    config = load_config()
    data_dir = ensure_data_dir(config)
    console.print(f"[green]Initialized data directory: {data_dir}[/green]")


@main.command()
@click.option("--interval", default=5, help="Polling interval in seconds")
@click.option("--observers", default="system,vscode,intellij,browser,feishu", help="Comma-separated list of observers to enable")
@click.option("--browser", default="Google Chrome", help="Browser to monitor (Google Chrome, Safari, Microsoft Edge)")
@click.option("--panel/--no-panel", default=True, help="Show terminal panel UI")
def observe(interval, observers, browser, panel):
    """Start observation mode."""
    enabled = [o.strip() for o in observers.split(",")]
    console.print(f"[green]Starting observation (interval: {interval}s)...[/green]")
    console.print(f"[green]Enabled observers: {', '.join(enabled)}[/green]")
    console.print(f"[green]Panel: {'enabled' if panel else 'disabled'}[/green]")
    
    registry = ObserverRegistry()
    
    # Create terminal panel
    terminal_panel = None
    if panel:
        terminal_panel = TerminalPanel()
    
    # Register observers based on selection
    if "system" in enabled:
        registry.register(SystemObserver(interval=interval))
    if "vscode" in enabled:
        try:
            registry.register(VSCodeObserver(interval=IDE_OBSERVER_INTERVAL))
            console.print("[green]VSCode observer enabled[/green]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not enable VSCode observer: {e}[/yellow]")
    if "intellij" in enabled:
        try:
            registry.register(IntelliJObserver(interval=IDE_OBSERVER_INTERVAL))
            console.print("[green]IntelliJ observer enabled[/green]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not enable IntelliJ observer: {e}[/yellow]")
    if "browser" in enabled:
        try:
            registry.register(BrowserObserver(browser=browser, interval=3))
            console.print(f"[green]Browser observer enabled ({browser})[/green]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not enable Browser observer: {e}[/yellow]")
    if "feishu" in enabled:
        try:
            registry.register(FeishuObserver(interval=3))
            console.print("[green]Feishu observer enabled[/green]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not enable Feishu observer: {e}[/yellow]")
    
    # Event handler
    def on_event(event: ObserverEvent):
        if terminal_panel:
            terminal_panel.add_event(event)
        console.print(f"[cyan]{event.observer}[/cyan]: {event.type} - {event.source.get('app', 'N/A')}")
    
    registry.on_event(on_event)
    
    # Start panel in background thread
    panel_thread = None
    if terminal_panel:
        terminal_panel.update_status("Observers starting...")
        panel_thread = threading.Thread(target=lambda: asyncio.run(terminal_panel.run()))
        panel_thread.start()
        time.sleep(0.5)
    
    # Run until interrupted
    try:
        if panel:
            terminal_panel.update_status(f"Monitoring: {', '.join(enabled)}")
        asyncio.run(registry.start_all())
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping observation...[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
    finally:
        asyncio.run(registry.stop_all())
        if terminal_panel:
            terminal_panel.stop()
            if panel_thread:
                panel_thread.join(timeout=2)


@main.command()
@click.option("--type", "memory_type", default=None, help="Filter by type (episodic, semantic, user_model)")
@click.option("--limit", default=10, help="Number of memories to show")
def memory(memory_type, limit):
    """Show memories."""
    config = load_config()
    db_path = config.data_dir / "reverb.db"
    store = MemoryStore(str(db_path))
    
    memories = store.get_memories(memory_type=memory_type, limit=limit)
    
    if not memories:
        console.print("[yellow]No memories found.[/yellow]")
        return
    
    for m in memories:
        console.print(f"[cyan]{m.memory_type}[/cyan]: {m.content[:100]}...")


@main.command()
def skills():
    """Show skills."""
    config = load_config()
    skills_dir = config.data_dir / "skills"
    manager = SkillManager(skills_dir)
    
    skill_list = manager.list_skills()
    
    if not skill_list:
        console.print("[yellow]No skills found.[/yellow]")
        return
    
    for s in skill_list:
        console.print(f"[cyan]{s.name}[/cyan]: {s.description}")
        console.print(f"  Trigger: {s.trigger}, Used: {s.usage_count} times")


@main.command()
@click.argument("skill_id")
async def run(skill_id):
    """Run a skill."""
    config = load_config()
    skills_dir = config.data_dir / "skills"
    manager = SkillManager(skills_dir)
    
    result = await manager.execute_skill(skill_id)
    console.print(f"[green]{result}[/green]")


if __name__ == "__main__":
    main()
