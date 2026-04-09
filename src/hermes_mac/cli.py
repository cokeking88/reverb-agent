"""CLI entry point for hermes-mac."""

import asyncio

import click
from rich.console import Console
from rich.table import Table

from hermes_mac.config import load_config, save_config, AppConfig, ensure_data_dir
from hermes_mac.constants import DEFAULT_LLM_PROVIDER, DEFAULT_LLM_MODEL
from hermes_mac import __version__
from hermes_mac.observers import ObserverRegistry
from hermes_mac.observers.system import SystemObserver
from hermes_mac.observers.vscode import VSCodeObserver
from hermes_mac.observers.intellij import IntelliJObserver
from hermes_mac.observers.events import ObserverEvent

console = Console()


@click.group()
@click.version_option(version=__version__)
def main():
    """Hermes-mac: PC Personal Assistant with autonomous observation."""
    pass


@main.command()
def status():
    """Show current status."""
    try:
        config = load_config()
    except Exception:
        console.print("[red]Failed to load config[/red]")
        return
    table = Table(title="Hermes-mac Status")
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
    """Initialize hermes-mac data directory."""
    config = load_config()
    data_dir = ensure_data_dir(config)
    console.print(f"[green]Initialized data directory: {data_dir}[/green]")


@main.command()
@click.option("--interval", default=5, help="Polling interval in seconds")
@click.option("--observers", default="system,vscode,intellij", help="Comma-separated list of observers to enable")
def observe(interval, observers):
    """Start observation mode."""
    enabled = [o.strip() for o in observers.split(",")]
    console.print(f"[green]Starting observation (interval: {interval}s)...[/green]")
    console.print(f"[green]Enabled observers: {', '.join(enabled)}[/green]")
    
    registry = ObserverRegistry()
    
    # Register observers based on selection
    if "system" in enabled:
        registry.register(SystemObserver(interval=interval))
    if "vscode" in enabled:
        try:
            registry.register(VSCodeObserver(interval=2))  # IDEs use shorter interval
            console.print("[green]VSCode observer enabled[/green]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not enable VSCode observer: {e}[/yellow]")
    if "intellij" in enabled:
        try:
            registry.register(IntelliJObserver(interval=2))
            console.print("[green]IntelliJ observer enabled[/green]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not enable IntelliJ observer: {e}[/yellow]")
    
    # Register global event handler
    def on_event(event: ObserverEvent):
        console.print(f"[cyan]{event.observer}[/cyan]: {event.type} - {event.source.get('app', 'N/A')}")
    
    registry.on_event(on_event)
    
    # Run until interrupted
    try:
        asyncio.run(registry.start_all())
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping observation...[/yellow]")
    finally:
        asyncio.run(registry.stop_all())


if __name__ == "__main__":
    main()
