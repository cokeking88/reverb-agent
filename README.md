# Reverb Agent: 自主学习型个人助手

A personal AI assistant that learns from your work patterns and helps you complete tasks. By observing your workflow, it autonomously extracts reusable skills to automate your recurring processes.

## ✨ 核心特性 (Features)

- **多端全景观察 (Omni-channel Observation)**
  - 🖥️ **System Observer**: Monitors global foreground window switching with zero-overhead native macOS AppKit.
  - 🌐 **Browser Extension**: A custom Chrome Extension that monitors web interactions (clicks, inputs), extracts page content, and **intercepts underlying API network requests (XHR/Fetch)**.
  - 💻 **IntelliJ IDEA Plugin**: Listens to JetBrains IDEs to capture the current edited file, line numbers, and real-time code snippet context.
  - 💬 **VSCode / Feishu Observers**: Tracks file changes and collaboration app status.

- **多级认知记忆引擎 (Multi-Level Cognitive Architecture)**
  Inspired by Hermes Agent and Honcho, Reverb Agent's cognitive loop is divided into four layers:
  1. **User Profile**: Your habits and workflow preferences.
  2. **Semantic Memory**: System rules and project structure context.
  3. **Episodic Memory**: Recent situational memory, including **cross-session FTS5 retrieval** of similar historical events.
  4. **Procedural Memory**: Locally persisted workflow skills that the agent has already learned.

- **自主技能生成 (Autonomous Skill Creation)**
  When the LLM observes you completing a structured, goal-oriented workflow (e.g., filling a web form -> clicking submit -> triggering a backend API POST), it automatically extracts a reusable JSON Skill and saves it locally in `~/.reverb-agent/data/skills/`. You can later invoke the Agent to perform this task for you.

- **流式可解释 UI (Web UI Console)**
  A real-time FastAPI + WebSockets dashboard (`http://127.0.0.1:19998`) that displays event streams, streaming `<think>` blocks from the LLM, and allows two-way chat interventions if the LLM needs to clarify your intent.

## Installation

```bash
pip install -e .
```

## Quick Start

```bash
# Initialize data directory
reverb init

# Configure LLM (e.g. OpenAI, Anthropic, Ollama)
reverb config-llm --provider openai --model gpt-4o --api-key YOUR_KEY

# Start observation (starts background monitoring and Web UI)
reverb observe

# Check status
reverb status
```

## CLI Commands

### observe
Start the observation mode to monitor your applications.
```bash
reverb observe                    # Default (system, vscode, intellij, browser, feishu)
reverb observe --interval 5       # Set polling interval
reverb observe --observers system,vscode  # Select specific observers
reverb observe --no-panel         # Run without Web UI
```

### search
Search your historical events and memories using the **FTS5 full-text search engine**.
```bash
reverb search "AWS Console"
reverb search "github PR" --limit 20
```

### memory
View learned memories categorized by the multi-level cognitive engine.
```bash
reverb memory                     # Show recent memories
reverb memory --type episodic     # Filter by type (episodic, semantic, user_profile)
```

### skills & run
View and execute autonomously generated skills.
```bash
reverb skills
reverb run <skill-id>
```

## 📚 Documentation
For detailed architecture and design patterns (especially how the learning loop works), see:
- [Hermes Agent 闭环学习机制与集成原理 (Hermes Integration Design)](docs/hermes_integration_design.md)

## Configuration & Data Storage
Configuration is stored in `~/.reverb-agent/config.json`.
All data is stored locally in `~/.reverb-agent/data/`:
- `reverb.db` - SQLite database with FTS5 virtual tables for memories and sessions
- `skills/` - Autonomously generated JSON skill definitions

## Privacy
All observation data, FTS indexing, and skill generation happen entirely on your local machine. No data is sent to the cloud, except the necessary payloads sent to your configured LLM provider for analysis.

## Requirements
- Python 3.11+
- macOS (requires `pyobjc` for native window tracking)
- An LLM endpoint (OpenAI, Anthropic, OpenRouter, Ollama)
- Chrome Extension (load unpacked from `chrome-extension/`)
- IDEA Plugin (build and install from `idea-plugin/`)