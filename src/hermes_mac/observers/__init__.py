"""Observer subsystem."""

from hermes_mac.observers.browser import BrowserObserver
from hermes_mac.observers.base import Observer
from hermes_mac.observers.events import ObserverEvent
from hermes_mac.observers.registry import ObserverRegistry
from hermes_mac.observers.system import SystemObserver
from hermes_mac.observers.vscode import VSCodeObserver
from hermes_mac.observers.intellij import IntelliJObserver

__all__ = ["Observer", "ObserverEvent", "ObserverRegistry", "SystemObserver", "VSCodeObserver", "IntelliJObserver", "BrowserObserver"]