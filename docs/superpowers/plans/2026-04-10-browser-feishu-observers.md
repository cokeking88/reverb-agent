# Browser & Feishu Observers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现浏览器精细化观察（URL、DOM内容、用户操作）和飞书观察（文档、消息、日程）。

**Tech Stack:** Python asyncio, AppleScript, 浏览器扩展

---

### Task 1: Implement BrowserObserver

**Files:**
- Create: `src/hermes_mac/observers/browser.py`

**实现要求：**
1. 支持 Chrome、Safari、Edge
2. 获取当前 URL 和页面标题
3. 获取选中文本（通过 AppleScript）
4. 监听标签页切换

```python
"""Browser observer for Chrome, Safari, Edge."""

import asyncio
import subprocess
from typing import List
from hermes_mac.observers.ide_observer import IDEObserver
from hermes_mac.observers.events import ObserverEvent
from hermes_mac.constants import Capability


class BrowserObserver(IDEObserver):
    """Observer for browser events."""
    
    SUPPORTED_BROWSERS = {
        "Google Chrome": "com.google.Chrome",
        "Safari": "com.apple.Safari",
        "Microsoft Edge": "com.microsoft.edgemac",
    }
    
    def __init__(self, browser: str = "Google Chrome", interval: int = 3):
        bundle_id = self.SUPPORTED_BROWSERS.get(browser, "com.google.Chrome")
        super().__init__("browser", app_bundle_id=bundle_id)
        self._browser = browser
        self._interval = interval
    
    @property
    def capabilities(self) -> List[str]:
        return [
            Capability.WINDOW_FOCUS,
            Capability.DOM_CONTENT,
            Capability.USER_ACTION,
        ]
    
    async def _poll_loop(self) -> None:
        while self._running:
            try:
                await self._check_browser()
            except Exception as e:
                print(f"Error checking browser: {e}")
            await asyncio.sleep(self._interval)
    
    async def _check_browser(self) -> None:
        # Get current URL
        script = f'''
        tell application "{self._browser}"
            if (count of windows) > 0 then
                set w to front window
                if (count of tabs of w) > 0 then
                    set t to active tab of w
                    return URL of t & "|||" & title of t
                end if
            end if
        end tell
        return ""
        '''
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            output = result.stdout.strip()
            if output and output != "|||":
                parts = output.split("|||")
                url = parts[0] if len(parts) > 0 else ""
                title = parts[1] if len(parts) > 1 else ""
                
                event = ObserverEvent(
                    observer=self.name,
                    type="page_focus",
                    source={"app": self._browser, "url": url},
                    data={"title": title, "url": url}
                )
                self._emit(event)
```

- [ ] **Step 1: Create browser.py**
- [ ] **Step 2: Update __init__.py exports**
- [ ] **Step 3: Commit**

---

### Task 2: Implement FeishuObserver

**Files:**
- Create: `src/hermes_mac/observers/feishu.py`

**实现要求：**
1. 监听飞书窗口焦点
2. 获取当前查看的文档（如果可获取）
3. 获取消息会话列表（通过 AppleScript）

```python
"""Feishu observer for Lark/Feishu desktop app."""

import asyncio
import subprocess
from typing import List
from hermes_mac.observers.ide_observer import IDEObserver
from hermes_mac.observers.events import ObserverEvent
from hermes_mac.constants import Capability


class FeishuObserver(IDEObserver):
    """Observer for Feishu/Lark desktop app."""
    
    def __init__(self, interval: int = 3):
        super().__init__("feishu", app_bundle_id="com.lark.lark")
        self._interval = interval
    
    @property
    def capabilities(self) -> List[str]:
        return [
            Capability.WINDOW_FOCUS,
            Capability.MESSAGE,
        ]
    
    async def _poll_loop(self) -> None:
        while self._running:
            try:
                await self._check_feishu()
            except Exception as e:
                print(f"Error checking Feishu: {e}")
            await asyncio.sleep(self._interval)
    
    async def _check_feishu(self) -> None:
        script = '''
        tell application "Feishu"
            if (count of windows) > 0 then
                set w to front window
                set windowTitle to name of w
                return windowTitle
            end if
        end tell
        return ""
        '''
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            window_title = result.stdout.strip()
            event = ObserverEvent(
                observer=self.name,
                type="window_focus",
                source={"app": "Feishu", "window": window_title},
                data={"window_title": window_title}
            )
            self._emit(event)
```

- [ ] **Step 1: Create feishu.py**
- [ ] **Step 2: Update __init__.py exports**
- [ ] **Step 3: Commit**

---

### Task 3: Add Browser and Feishu to CLI

**Files:**
- Modify: `src/hermes_mac/cli.py`

**实现要求：**
1. 添加 `--browser` 选项选择浏览器
2. 在 observers 列表中添加 browser 和 feishu

```python
@click.option("--interval", default=5, help="Polling interval in seconds")
@click.option("--observers", default="system,vscode,intellij,browser,feishu", help="Comma-separated list")
@click.option("--browser", default="Google Chrome", help="Browser to monitor")
def observe(interval, observers, browser):
```

- [ ] **Step 1: Update cli.py**
- [ ] **Step 2: Test**
- [ ] **Step 3: Commit**

---

## Summary

- BrowserObserver: Chrome/Safari/Edge URL/标题监听
- FeishuObserver: 飞书窗口监听
- CLI 更新支持选择浏览器