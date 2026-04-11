package com.reverb.plugin

import com.intellij.openapi.editor.actionSystem.EditorActionHandler
import com.intellij.openapi.editor.actionSystem.EditorActionManager
import com.intellij.openapi.actionSystem.IdeActions
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.actionSystem.DataContext
import com.intellij.openapi.editor.Caret
import com.intellij.openapi.ide.CopyPasteManager
import java.awt.datatransfer.DataFlavor

class ReverbCopyPasteListener {
    fun register() {
        val actionManager = EditorActionManager.getInstance()
        
        // Wrap Copy Action
        val originalCopy = actionManager.getActionHandler(IdeActions.ACTION_EDITOR_COPY)
        actionManager.setActionHandler(IdeActions.ACTION_EDITOR_COPY, object : EditorActionHandler() {
            override fun doExecute(editor: Editor, caret: Caret?, dataContext: DataContext?) {
                originalCopy.execute(editor, caret, dataContext)
                val contents = CopyPasteManager.getInstance().contents
                val text = contents?.getTransferData(DataFlavor.stringFlavor) as? String
                if (text != null && text.length > 5) {
                    ReverbWsClient.sendEvent("user_action", mapOf(
                        "action" to "copy",
                        "element" to "editor",
                        "text" to text.take(200) // Prevent huge payloads
                    ))
                }
            }
        })

        // Wrap Paste Action
        val originalPaste = actionManager.getActionHandler(IdeActions.ACTION_EDITOR_PASTE)
        actionManager.setActionHandler(IdeActions.ACTION_EDITOR_PASTE, object : EditorActionHandler() {
            override fun doExecute(editor: Editor, caret: Caret?, dataContext: DataContext?) {
                val contents = CopyPasteManager.getInstance().contents
                val text = contents?.getTransferData(DataFlavor.stringFlavor) as? String
                if (text != null && text.length > 5) {
                    ReverbWsClient.sendEvent("user_action", mapOf(
                        "action" to "paste",
                        "element" to "editor",
                        "text" to text.take(200)
                    ))
                }
                originalPaste.execute(editor, caret, dataContext)
            }
        })
    }
}
