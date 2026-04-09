"""CLI entry point for hermes-mac."""

import click
from rich.console import Console
from rich.table import Table

from hermes_mac.config import load_config, save_config, AppConfig, ensure_data_dir
from hermes_mac.constants import DEFAULT_LLM_PROVIDER, DEFAULT_LLM_MODEL
from hermes_mac import __version__

console = Console()


@click.group()
@click.version_option(version=__version__)
def main():
    """Hermes-mac: PC Personal Assistant with autonomous observation."""
    pass


@main.command()
def status():
    """Show current status."""
    config = load_config()
    table = Table(title="Hermes-mac Status")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Data Directory", str(config.data_dir))
    table.add_row("LLM Provider", config.llm.provider)
    table.add_row("LLM Model", config.llm.model)
    table.add_row("Observers Enabled", str(len([o for o in config.observers.observers if config.observers.enabled])))
    
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


if __name__ == "__main__":
    main()
