"""IntelliJ observer for Android Studio and IntelliJ IDEA."""

from reverb_agent.observers.ide_observer import IDEObserver


class IntelliJObserver(IDEObserver):
    """Observer for IntelliJ-based IDEs (Android Studio, IntelliJ IDEA)."""
    
    def __init__(self, app_name: str = "Android Studio", interval: int = 2):
        if app_name == "Android Studio":
            bundle_id = "com.google.android.studio"
        else:
            bundle_id = "com.jetbrains.intellij"
        super().__init__("intellij", app_bundle_id=bundle_id, interval=interval)
        self._app_name = app_name
    
    def _get_applescript(self) -> str:
        return f'''
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
        return ""
        '''