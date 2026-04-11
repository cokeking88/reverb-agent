package com.reverb.plugin

import com.intellij.openapi.editor.event.DocumentEvent
import com.intellij.openapi.editor.event.DocumentListener
import com.intellij.openapi.fileEditor.FileDocumentManager

class ReverbDocumentListener : DocumentListener {
    private var lastEditTime = 0L

    override fun documentChanged(event: DocumentEvent) {
        val now = System.currentTimeMillis()
        if (now - lastEditTime < 3000) { // Increased debounce to 3 seconds to reduce noise
            return
        }
        lastEditTime = now

        val file = FileDocumentManager.getInstance().getFile(event.document)
        if (file != null) {
            val name = file.name
            val path = file.path

            // Get the line number of the edit
            val offset = event.offset

            // Handle edge cases where document might be empty
            if (event.document.textLength == 0) {
                ReverbWsClient.sendEvent("user_action", mapOf(
                    "action" to "edit",
                    "element" to "$name:0",
                    "path" to path,
                    "text" to "(cleared file)"
                ))
                return
            }

            val lineNumber = event.document.getLineNumber(minOf(offset, maxOf(0, event.document.textLength - 1)))

            // Try to extract a snippet around the edit (current line + surrounding a bit)
            val startLine = maxOf(0, lineNumber - 1)
            val endLine = minOf(event.document.lineCount - 1, lineNumber + 1)
            val startOffset = event.document.getLineStartOffset(startLine)
            val endOffset = event.document.getLineEndOffset(endLine)

            val snippet = if (endOffset > startOffset) {
                event.document.getText(com.intellij.openapi.util.TextRange(startOffset, endOffset)).trim()
            } else {
                "(empty line)"
            }

            // Avoid sending huge payloads if they pasted a massive block (caught by CopyPasteListener mostly anyway)
            val truncatedSnippet = if (snippet.length > 300) snippet.substring(0, 300) + "..." else snippet

            ReverbWsClient.sendEvent("user_action", mapOf(
                "action" to "edit",
                "element" to "$name:${lineNumber + 1}", // 1-based for humans
                "path" to path,
                "text" to truncatedSnippet
            ))
        }
    }
}
