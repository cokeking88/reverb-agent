"""CLI entry point for Reverb Agent."""

import asyncio
import os
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
            import websockets
            registry.register(BrowserObserver(browser=browser, interval=3))
            console.print(f"[green]Browser observer enabled (WS Extension Mode)[/green]")
        except ImportError:
            console.print("[yellow]Warning: 'websockets' package required for browser extension mode. Run: pip install websockets[/yellow]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not enable Browser observer: {e}[/yellow]")
    if "feishu" in enabled:
        try:
            registry.register(FeishuObserver(interval=3))
            console.print("[green]Feishu observer enabled[/green]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not enable Feishu observer: {e}[/yellow]")
    
    # System observer - start daemon and tail log
    if "system" in enabled:
        import subprocess
        import threading
        
        # Check if daemon already running
        daemon_check = subprocess.run(
            ["pgrep", "-f", "reverb_daemon.py"],
            capture_output=True
        )
        
        if daemon_check.returncode != 0:
            # Create AppleScript if not exists
            if not os.path.exists("/tmp/test_front.app"):
                with open("/tmp/test_front.app", "w") as f:
                    f.write("""tell application "System Events"
    try
        set x to name of first application process whose frontmost is true
        return x
    on error
        return "ERR"
    end try
end tell""")
            
            # Also create daemon script in /tmp
            daemon_script = '''#!/usr/bin/env python3
import subprocess
import os
import time

LOG = "/tmp/reverb_daemon.log"
last = ""

while True:
    try:
        result = subprocess.run(
            ["osascript", "/tmp/test_front.app"],
            capture_output=True, text=True, timeout=2
        )
        app = result.stdout.strip()
        if app and app != last:
            with open(LOG, "a") as f:
                f.write(time.strftime("%H:%M:%S") + ": " + app + "\\n")
            last = app
    except:
        pass
    time.sleep(1)
'''
            with open("/tmp/reverb_daemon.py", "w") as f:
                f.write(daemon_script)
            os.chmod("/tmp/reverb_daemon.py", 0o755)
            
            # Start daemon detached in /tmp - this is the key!
            subprocess.Popen(
                ["/usr/bin/python3", "/tmp/reverb_daemon.py"],
                cwd="/tmp",
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True
            )
            console.print("[yellow]Started system monitor[/yellow]")
        
# Tail the log file and add to event stream
        LOG = "/tmp/reverb_daemon.log"
        
        def tail_and_emit():
            import os
            last_line = ""
            while True:
                try:
                    if os.path.exists(LOG):
                        with open(LOG, 'r') as f:
                            lines = f.readlines()
                        if lines:
                            latest = lines[-1].strip()
                            # Format is "HH:MM:SS: app" - find colon-space position
                            idx = latest.find(': ')
                            if idx > 0 and latest != last_line:
                                last_line = latest
                                app = latest[idx+2:].strip()  # Get app after ": "
                                if app:
                                    event = ObserverEvent(
                                        observer="system",
                                        type="window_focus",
                                        source={"app": app, "window": ""},
                                        data={}
                                    )
                                    if terminal_panel:
                                        terminal_panel.add_event(event)
                                    if agent_loop:
                                        agent_loop.on_event(event)
                except:
                    pass
                time.sleep(0.5)
        
        # Store tail function for later start
        tail_func = tail_and_emit
    
    # Setup AgentLoop for LLM analysis
    llm_client = None
    agent_loop = None
    try:
        config = load_config()
        db_path = config.data_dir / "reverb.db"
        memory_store = MemoryStore(str(db_path))
        llm_client = LLMClient(
            provider=config.llm.provider,
            model=config.llm.model,
            endpoint=config.llm.endpoint,
            api_key=config.llm.api_key
        )
        agent_loop = AgentLoop(llm_client, memory_store)
        
        # Build status message
        status_msg = f"{config.llm.provider}/{config.llm.model}"
        if config.llm.endpoint:
            status_msg += f" ({config.llm.endpoint})"
        
        console.print(f"[green]LLM enabled: {status_msg}[/green]")
        if terminal_panel:
            terminal_panel.add_status_message(f"LLM: {status_msg}", is_error=False)
    except Exception as e:
        error_msg = str(e)[:60]
        console.print(f"[yellow]LLM error: {error_msg}[/yellow]")
        if terminal_panel:
            terminal_panel.add_status_message(f"LLM error: {error_msg}", is_error=True)
    
    # Callback for LLM questions
    def on_thought(thought: str, question: str = None, reply_callback: callable = None):
        if terminal_panel:
            if thought:
                terminal_panel.add_thought(thought)
            if question and reply_callback:
                terminal_panel.set_question(question, reply_callback)

    if agent_loop:
        agent_loop.set_callback(on_thought)
    
    # Event handler - send to both panel and AgentLoop
    def on_event(event: ObserverEvent):
        if terminal_panel:
            terminal_panel.add_event(event)
        if agent_loop:
            agent_loop.on_event(event)

    registry.on_event(on_event)

    # Store main event loop before blocking wait
    main_loop = None

    # Pass main loop to agent_loop so it can schedule things from worker threads
    if agent_loop:
        agent_loop.set_main_loop(None)

    # Start system observer tail after agent_loop is ready
    if "system" in enabled:
        tail_thread = threading.Thread(target=tail_func, daemon=True, name="tail_and_emit")
        tail_thread.start()

    # Start panel in background thread
    panel_thread = None
    if terminal_panel:
        terminal_panel.update_status("Observers starting...")

        def run_panel():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(terminal_panel.run())
            finally:
                loop.close()

        panel_thread = threading.Thread(target=run_panel)
        panel_thread.start()
        time.sleep(0.5)

    # Run until interrupted
    try:
        if panel:
            terminal_panel.update_status(f"Monitoring: {', '.join(enabled)}")

        async def main_runner():
            nonlocal main_loop
            main_loop = asyncio.get_running_loop()
            if agent_loop:
                agent_loop.set_main_loop(main_loop)

            await registry.start_all()

            # Keep running
            while True:
                await asyncio.sleep(1)

        asyncio.run(main_runner())

    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping observation...[/yellow]")
    finally:
        # Stop observers properly in a new loop if needed or just let it close
        try:
            asyncio.run(registry.stop_all())
        except Exception:
            pass
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
