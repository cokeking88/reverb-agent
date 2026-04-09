"""Constants for hermes-mac."""

from pathlib import Path

# Default data directory
DEFAULT_DATA_DIR = Path.home() / ".hermes-mac" / "data"

# Config file name
CONFIG_FILE_NAME = "config.json"

# Database file name
DB_FILE_NAME = "hermes.db"

# Observers configuration
DEFAULT_OBSERVER_INTERVAL = 5  # seconds

# LLM defaults
DEFAULT_LLM_PROVIDER = "ollama"
DEFAULT_LLM_MODEL = "llama3"


# Observer capability types
class Capability:
    WINDOW_FOCUS = "window_focus"
    FILE_CONTENT = "file_content"
    CURSOR_POSITION = "cursor_position"
    CODE_DIFF = "code_diff"
    DOM_CONTENT = "dom_content"
    USER_ACTION = "user_action"
    MESSAGE = "message"
    MEETING = "meeting"
    COMMAND = "command"