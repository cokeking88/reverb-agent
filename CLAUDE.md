# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Purpose
- Short: Reverb Agent is a CLI-first personal assistant that observes user activity, summarizes events with an LLM, and stores "memories" locally.

Common commands (how to build, run, lint, test)
- Setup (dev install):
  - python -m pip install -e .
- Run CLI (entrypoint):
  - reverb init           # initialize data directory (creates ~/.reverb-agent/data)
  - python -m reverb_agent    # run via module
  - reverb observe        # start observation mode (see README quick-start)
- Configure LLM:
  - reverb config-llm --provider ollama --model llama3
  - reverb config-llm --provider openai --model gpt-4 --api-key YOUR_KEY
- Tests (pytest):
  - pytest                 # run all tests
  - pytest tests -q        # run the tests folder quietly
  - pytest tests/test_config.py -q   # run a single test file
  - pytest -k <expr>       # run tests matching an expression
- (Optional) Lint/format (project does not ship lint tooling; recommend using local tools if desired):
  - ruff check .
  - black .

Where configuration & data live
- Config file: ~/.reverb-agent/config.json (see src/reverb_agent/config.py:get_config_path)
  - Function reading config and .env: src/reverb_agent/config.py:47-101
  - Default data dir: src/reverb_agent/constants.py:5-7 -> DEFAULT_DATA_DIR (~/.reverb-agent/data)
- Data stored under DEFAULT_DATA_DIR:
  - reverb.db (SQLite) and skills/ (see README and constants)
  - README quick start and storage notes: README.md:103-123 and Quick Start examples README.md:21-33

Quick pointers and important notes (do not mutate without care)
- Secrets: the repository contains an .env.example and a tracked .env that appear to include an API key at line 11 in both files:
  - .env.example: line 11 (/Users/yangnanqing/projects/pc个人助手/.env.example:11)
  - .env: line 11 (/Users/yangnanqing/projects/pc个人助手/.env:11)
  - The code loads a repository .env (src/reverb_agent/config.py:47-65) and will populate LLM config from it (src/reverb_agent/config.py:79-86). Treat these as secrets and do not commit real keys.

High-level architecture (big picture)
- Top-level CLI (src/reverb_agent/cli.py)
  - click-based entrypoint exposing commands: status, config-llm, init, observe, memory, skills, run (see src/reverb_agent/cli.py:29-37 and command handlers at 36-75 and 82-369).
  - The CLI wires together configuration, observers, UI panel, and the AgentLoop.

- Configuration (src/reverb_agent/config.py)
  - load_env() reads a local .env (src/reverb_agent/config.py:47-65).
  - load_config() prefers ~/.reverb-agent/config.json and falls back to env values (src/reverb_agent/config.py:68-101).
  - save_config() writes the JSON config (src/reverb_agent/config.py:104-113).

- Observers (src/reverb_agent/observers/)
  - A registry manages multiple observers (system, vscode, intellij, browser, feishu). Observers emit ObserverEvent objects consumed by the AgentLoop.
  - The CLI registers observers conditionally and starts them via ObserverRegistry.start_all() (see src/reverb_agent/cli.py:94-127 and registry usage at 302).
  - System observer has a helper daemon that tails /tmp/reverb_daemon.log and emits window focus events by running an AppleScript; this detaches a /tmp/reverb_daemon.py script and /tmp/test_front.app (see src/reverb_agent/cli.py:130-193). Be mindful that this creates files in /tmp and starts a detached subprocess.

- Agent & LLM integration
  - LLMClient: an async client with providers for ollama (HTTP) and openai/openrouter (uses openai Async client). See src/reverb_agent/agent/llm.py:14-23 and provider dispatch at 34-41.
  - AgentLoop: central processing loop that buffers ObserverEvent, persists events, schedules LLM analysis for focus events, and may write memories via MemoryStore (see src/reverb_agent/agent/loop.py:14-24 and event processing at 26-44 and _process_events/_analyze_events at 45-102).
  - Important behavior: AgentLoop schedules LLM work in a ThreadPoolExecutor and calls asyncio.run from a worker thread (src/reverb_agent/agent/loop.py:42-44). The LLM client methods are async and expected to be awaited inside the loop.

- Memory, Skills, and Storage
  - MemoryStore and SkillManager manage persistence to reverb.db and skills/ under the data dir. These are used by the CLI and AgentLoop (references found in src/reverb_agent/agent/* and CLI usage at src/reverb_agent/cli.py:231-241 and 320-351).

- UI: TerminalPanel (src/reverb_agent/ui/panel.py)
  - If enabled, the CLI creates a TerminalPanel and runs it in a background thread/event loop to display events, LLM "thoughts", and status messages (see src/reverb_agent/cli.py:96-101 and panel thread at 280-295).

Tests
- Tests live under tests/ and are configured in pyproject.toml (tool.pytest.ini_options). Run pytest as noted above (pyproject.toml:25-27).
- Example test file: tests/test_config.py — run it with pytest tests/test_config.py -q

Repository metadata
- Packaging: pyproject.toml uses setuptools with an editable install entrypoint `reverb = "reverb_agent.cli:main"` (pyproject.toml:18-20)
- Python requirement: 3.11+ (pyproject.toml:6)

Operational cautions for automated agents
- Do not commit secrets: the repo contains a tracked .env with an API key at .env:11. If you plan to modify files, ensure you do not print or re-introduce secrets into commits or uploaded artifacts.
- External effects: observe command may write/execute files in /tmp and start a detached system daemon (/tmp/reverb_daemon.py). If an automated agent will run tests or start observers, it should avoid running observe by default.
- Network calls: LLMClient will attempt network calls to local ollama endpoint or OpenAI/openrouter; ensure tests and CI set API keys safely or mock network calls.

Useful file references (start here)
- CLI and commands: src/reverb_agent/cli.py:29-75, 82-120, 228-266, 301-316
- Config handling: src/reverb_agent/config.py:47-101, 104-120
- LLM client: src/reverb_agent/agent/llm.py:14-40, 43-66, 66-87
- Agent loop and analysis: src/reverb_agent/agent/loop.py:14-24, 26-44, 45-102
- Constants: src/reverb_agent/constants.py:5-21
- README quick-start & config examples: README.md:21-33, 103-116

If a CLAUDE.md already exists
- Suggest improvements instead of replacing; this is the initial file.

If you want, I can:
- Create this CLAUDE.md in the repository now (I will write the file), or
- Iterate on it (add/remove items you want included).

End of guidance.