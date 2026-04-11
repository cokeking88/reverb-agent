package com.reverb.plugin

import com.intellij.openapi.editor.event.DocumentEvent
import com.intellij.openapi.editor.event.DocumentListener
import com.intellij.openapi.fileEditor.FileDocumentManager

class ReverbDocumentListener : DocumentListener {
    private var lastEditTime = 0L

    override fun documentChanged(event: DocumentEvent) {
        val now = System.currentTimeMillis()
        if (now - lastEditTime < 1000) {
            return // Debounce for 1 second
        }
        lastEditTime = now

        val file = FileDocumentManager.getInstance().getFile(event.document)
        if (file != null) {
            ReverbWsClient.sendEvent("user_action", mapOf(
                "action" to "edit",
                "element" to file.name,
                "text" to "" // Don't send whole document, just the fact they typed
            ))
        }
    }
}
