package com.reverb.plugin

import com.intellij.xdebugger.breakpoints.XBreakpoint
import com.intellij.xdebugger.breakpoints.XBreakpointListener
import com.intellij.xdebugger.breakpoints.XLineBreakpoint

class ReverbBreakpointListener : XBreakpointListener<XBreakpoint<*>> {
    override fun breakpointAdded(breakpoint: XBreakpoint<*>) {
        if (breakpoint is XLineBreakpoint<*>) {
            ReverbWsClient.sendEvent("ide_debug", mapOf(
                "action" to "breakpoint_added",
                "file" to breakpoint.fileUrl,
                "line" to breakpoint.line
            ))
        }
    }

    override fun breakpointRemoved(breakpoint: XBreakpoint<*>) {
        if (breakpoint is XLineBreakpoint<*>) {
            ReverbWsClient.sendEvent("ide_debug", mapOf(
                "action" to "breakpoint_removed",
                "file" to breakpoint.fileUrl,
                "line" to breakpoint.line
            ))
        }
    }
}
