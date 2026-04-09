# Reverb Agent

A personal AI assistant that learns from your work patterns and helps you complete tasks.

## Features

- **Autonomous Observation**: Monitors your work across multiple applications
- **Pattern Learning**: Analyzes your behavior to discover recurring workflows
- **Skill Generation**: Creates reusable skills from repeated tasks
- **Memory**: Stores learned knowledge across sessions
- **CLI-First**: Lightweight command-line interface

## Installation

```bash
pip install -e .
```

## Quick Start

```bash
# Initialize data directory
reverb init

# Configure LLM
reverb config-llm --provider ollama --model llama3

# Start observation
reverb observe

# Check status
reverb status
```

## Commands

### observe

Start the observation mode to monitor your applications.

```bash
reverb observe                    # Default (system, vscode, intellij, browser, feishu)
reverb observe --interval 5       # Set polling interval
reverb observe --observers system,vscode  # Select specific observers
reverb observe --browser Safari   # Choose browser (Chrome, Safari, Edge)
```

### status

Show current configuration.

```bash
reverb status
```

### config-llm

Configure LLM settings.

```bash
reverb config-llm --provider ollama --model llama3
reverb config-llm --provider openai --model gpt-4 --api-key YOUR_KEY
```

### memory

View learned memories.

```bash
reverb memory                     # Show recent memories
reverb memory --type episodic     # Filter by type
reverb memory --limit 20          # Limit results
```

### skills

View generated skills.

```bash
reverb skills
```

### run

Execute a skill.

```bash
reverb run <skill-id>
```

## Observers

| Observer | Description |
|----------|-------------|
| system | Monitor window focus and application changes |
| vscode | Track file changes in VSCode |
| intellij | Monitor Android Studio/IntelliJ |
| browser | Track browser tabs and URLs |
| feishu | Monitor Feishu/Lark desktop app |

## Configuration

Configuration is stored in `~/.reverb-agent/config.json`.

```json
{
  "data_dir": "~/.reverb-agent/data",
  "llm": {
    "provider": "ollama",
    "model": "llama3"
  },
  "observers": {
    "enabled": true,
    "interval": 5
  }
}
```

## Data Storage

All data is stored locally in `~/.reverb-agent/data/`:
- `reverb.db` - SQLite database for memories and sessions
- `skills/` - Generated skill definitions

## Privacy

All observation data stays local. No cloud upload.

## Requirements

- Python 3.11+
- macOS (other platforms coming soon)
- LLM endpoint (Ollama, OpenAI, etc.)