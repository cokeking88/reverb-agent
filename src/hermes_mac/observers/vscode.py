"""VSCode observer for detailed code monitoring."""

from hermes_mac.observers.ide_observer import IDEObserver


class VSCodeObserver(IDEObserver):
    """Observer for VSCode events using AppleScript."""
    
    def __init__(self, interval: int = 2):
        super().__init__("vscode", app_bundle_id="com.microsoft.VSCode", interval=interval)
    
    def _get_applescript(self) -> str:
        return '''
        tell application "VSCode"
            if (count of windows) > 0 then
                set w to front window
                if (count of tabs of w) > 0 then
                    return path of active tab of w
                end if
            end if
        end tell
        return ""
        '''