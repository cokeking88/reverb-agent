# IDE Observers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement VSCodeObserver and IntelliJObserver for精细化代码观察（文件内容、光标位置、代码修改）。

**Architecture:** 通过 IDE 扩展/插件获取精细化数据，事件通过 Observer 框架传递给 Agent Loop。

**Tech Stack:** Python asyncio, VSCode API (扩展), IntelliJ SDK (插件)

---

## File Structure

```
src/hermes_mac/observers/
├── vscode.py        # VSCodeObserver
├── intellij.py      # IntelliJObserver  
└── __init__.py      # Updated exports
```

### Task 1: Implement VSCodeObserver

**Files:**
- Create: `src/hermes_mac/observers/vscode.py`

**Step-by-step requirements:**

1. Create VSCodeObserver class that:
   - 继承 Observer 基类
   - 监听窗口焦点变化（当前文件）
   - 监听文件内容变化（通过 VSCode 扩展的 IPC）
   - 监听光标位置变化
   - 监听代码修改（diff）

2. VSCode 插件部分（作为子模块）：
   - 创建 `plugins/vscode-observer/` 扩展
   - 暴露 API: 当前文件路径、内容、光标位置
   - 通过 stdio 或 WebSocket 与主程序通信

3. 实现架构：
   - 主进程通过子进程启动 VSCode 插件
   - 插件通过 VSCode API 监听事件并发送消息
   - Observer 接收消息并转换为 ObserverEvent

**实现代码框架：**
```python
"""VSCode observer for detailed code monitoring."""

import asyncio
from typing import List, Optional
from pathlib import Path
from hermes_mac.observers.base import Observer
from hermes_mac.observers.events import ObserverEvent
from hermes_mac.constants import Capability


class VSCodeObserver(Observer):
    """Observer for VSCode events."""
    
    def __init__(self, plugin_path: Optional[Path] = None, interval: int = 2):
        super().__init__("vscode", app_bundle_id="com.microsoft.VSCode")
        self._plugin_path = plugin_path or self._default_plugin_path()
        self._interval = interval
        self._process = None
        self._last_file = None
        self._last_cursor = None
    
    def _default_plugin_path(self) -> Path:
        return Path(__file__).parent.parent.parent.parent / "plugins" / "vscode-observer"
    
    @property
    def capabilities(self) -> List[str]:
        return [
            Capability.FILE_CONTENT,
            Capability.CURSOR_POSITION,
            Capability.CODE_DIFF,
            Capability.WINDOW_FOCUS,
        ]
    
    async def start(self) -> None:
        await super().start()
        # 启动插件进程或连接
        self._process = await self._start_plugin()
    
    async def stop(self) -> None:
        if self._process:
            self._process.terminate()
            await self._process.wait()
        await super().stop()
    
    async def _start_plugin(self):
        # 启动 VSCode 插件进程
        pass
    
    def _on_plugin_message(self, message: dict) -> None:
        # 处理来自插件的消息，转换为 ObserverEvent
        event_type = message.get("type")
        if event_type == "file_changed":
            event = ObserverEvent(
                observer=self.name,
                type="file_focus",
                source={
                    "app": "VSCode",
                    "file": message.get("path"),
                },
                data={
                    "content": message.get("content"),
                    "cursor": message.get("cursor"),
                }
            )
            self._emit(event)
        elif event_type == "cursor_moved":
            event = ObserverEvent(
                observer=self.name,
                type="cursor_position",
                source={
                    "file": message.get("path"),
                },
                data={
                    "line": message.get("line"),
                    "column": message.get("column"),
                }
            )
            self._emit(event)
        elif event_type == "text_changed":
            event = ObserverEvent(
                observer=self.name,
                type="code_diff",
                source={
                    "file": message.get("path"),
                },
                data={
                    "changes": message.get("changes"),
                }
            )
            self._emit(event)
```

4. 简化实现策略（无需插件）：
   - 使用 AppleScript 获取 VSCode 当前文件
   - 使用 `vscode` 命令行工具（如果可用）
   - 轮询间隔获取当前状态

**简化版实现：**
```python
"""VSCode observer - simplified version using AppleScript."""

import asyncio
import subprocess
from typing import List, Optional
from hermes_mac.observers.base import Observer
from hermes_mac.observers.events import ObserverEvent
from hermes_mac.constants import Capability


class VSCodeObserver(Observer):
    """Observer for VSCode using AppleScript."""
    
    def __init__(self, interval: int = 2):
        super().__init__("vscode", app_bundle_id="com.microsoft.VSCode")
        self._interval = interval
        self._task = None
        self._last_file = None
        self._last_cursor = None
    
    @property
    def capabilities(self) -> List[str]:
        return [
            Capability.WINDOW_FOCUS,
            Capability.FILE_CONTENT,
            Capability.CURSOR_POSITION,
        ]
    
    async def start(self) -> None:
        await super().start()
        self._task = asyncio.create_task(self._poll_loop())
    
    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await super().stop()
    
    async def _poll_loop(self) -> None:
        while self._running:
            try:
                await self._check_vscode()
            except Exception as e:
                print(f"Error checking VSCode: {e}")
            await asyncio.sleep(self._interval)
    
    async def _check_vscode(self) -> None:
        script = '''
        tell application "VSCode"
            if active of document 1 then
                set filePath to path of document 1
                -- Get cursor position via selection
                set sel to selection of active text editor
                set cursorLine to start line of sel
                set cursorCol to start column of sel
                return filePath & "|||" & cursorLine & "|||" & cursorCol
            end if
        end tell
        '''
        # 简化版：只获取当前文件
        result = subprocess.run(
            ["osascript", "-e", '''
            tell application "VSCode"
                if (count of windows) > 0 then
                    set w to front window
                    if (count of tabs of w) > 0 then
                        return path of active tab of w
                    end if
                end if
            end tell
            '''],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            file_path = result.stdout.strip()
            if file_path != self._last_file:
                self._last_file = file_path
                # 读取文件内容
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                except:
                    content = ""
                event = ObserverEvent(
                    observer=self.name,
                    type="file_focus",
                    source={
                        "app": "VSCode",
                        "file": file_path,
                    },
                    data={"content": content}
                )
                self._emit(event)
```

5. Commit with message: "feat: add VSCode observer"

- [ ] **Step 1: Create vscode.py**
- [ ] **Step 2: Verify import works**
- [ ] **Step 3: Commit**

### Task 2: Implement IntelliJObserver

**Files:**
- Create: `src/hermes_mac/observers/intellij.py`

**Step-by-step requirements:**

1. 创建 IntelliJObserver 类（类似 VSCodeObserver）
2. 支持 Android Studio（bundle ID: com.google.android.studio）
3. 使用 AppleScript 获取当前文件和项目信息

```python
"""IntelliJ observer for Android Studio."""

import asyncio
import subprocess
from typing import List
from hermes_mac.observers.base import Observer
from hermes_mac.observers.events import ObserverEvent
from hermes_mac.constants import Capability


class IntelliJObserver(Observer):
    """Observer for IntelliJ-based IDEs (Android Studio)."""
    
    def __init__(self, app_name: str = "Android Studio", interval: int = 2):
        bundle_id = "com.google.android.studio" if app_name == "Android Studio" else "com.jetbrains.intellij"
        super().__init__("intellij", app_bundle_id=bundle_id)
        self._app_name = app_name
        self._interval = interval
        self._task = None
        self._last_file = None
    
    @property
    def capabilities(self) -> List[str]:
        return [
            Capability.WINDOW_FOCUS,
            Capability.FILE_CONTENT,
            Capability.CURSOR_POSITION,
            Capability.CODE_DIFF,
        ]
    
    async def start(self) -> None:
        await super().start()
        self._task = asyncio.create_task(self._poll_loop())
    
    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await super().stop()
    
    async def _poll_loop(self) -> None:
        while self._running:
            try:
                await self._check_ide()
            except Exception as e:
                print(f"Error checking {self._app_name}: {e}")
            await asyncio.sleep(self._interval)
    
    async def _check_ide(self) -> None:
        script = f'''
        tell application "{self._app_name}"
            if (count of windows) > 0 then
                set w to front window
                set filePath to ""
                try
                    set filePath to file of active editor of w
                end try
                return filePath
            end if
        end tell
        '''
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            file_path = result.stdout.strip()
            if file_path != self._last_file:
                self._last_file = file_path
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                except:
                    content = ""
                event = ObserverEvent(
                    observer=self.name,
                    type="file_focus",
                    source={
                        "app": self._app_name,
                        "file": file_path,
                    },
                    data={"content": content}
                )
                self._emit(event)
```

2. 更新 __init__.py 导出

3. Commit with message: "feat: add IntelliJ observer"

- [ ] **Step 1: Create intellij.py**
- [ ] **Step 2: Update __init__.py exports**
- [ ] **Step 3: Verify imports work**
- [ ] **Step 4: Commit**

### Task 3: Add IDE observers to CLI

**Files:**
- Modify: `src/hermes_mac/cli.py`

**Step-by-step requirements:**

1. 更新 observe 命令，支持启用/禁用特定观察器
2. 添加 `--observers` 选项来选择观察器

```python
@main.command()
@click.option("--interval", default=5, help="Polling interval in seconds")
@click.option("--observers", default="system,vscode", help="Comma-separated list of observers to enable")
def observe(interval, observers):
    """Start observation mode."""
    enabled = [o.strip() for o in observers.split(",")]
    
    registry = ObserverRegistry()
    
    if "system" in enabled:
        registry.register(SystemObserver(interval=interval))
    if "vscode" in enabled:
        registry.register(VSCodeObserver(interval=interval))
    if "intellij" in enabled:
        registry.register(IntelliJObserver(interval=interval))
    
    # ... rest of command
```

2. Import the new observers

3. Commit with message: "feat: add IDE observers to CLI"

- [ ] **Step 1: Update cli.py with IDE observer support**
- [ ] **Step 2: Test the command**
- [ ] **Step 3: Commit**

---

## Summary

This plan implements:
- VSCodeObserver for VSCode file/cursor monitoring
- IntelliJObserver for Android Studio monitoring
- CLI integration for selecting which observers to enable

**Next plan should cover:** Browser Observer, Feishu Observer, Agent Loop (LLM integration), Memory & Skills 系统