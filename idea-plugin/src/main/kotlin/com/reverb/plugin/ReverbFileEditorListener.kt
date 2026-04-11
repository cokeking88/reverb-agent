package com.reverb.plugin

import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.openapi.fileEditor.FileEditorManagerListener
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.openapi.fileEditor.FileEditorManagerEvent

class ReverbFileEditorListener : FileEditorManagerListener {
    override fun fileOpened(source: FileEditorManager, file: VirtualFile) {
        ReverbWsClient.sendEvent("file_focus", mapOf(
            "path" to file.path,
            "name" to file.name
        ))
    }

    override fun selectionChanged(event: com.intellij.openapi.fileEditor.FileEditorManagerEvent) {
        val newFile = event.newFile
        if (newFile != null) {
            ReverbWsClient.sendEvent("file_focus", mapOf(
                "path" to newFile.path,
                "name" to newFile.name
            ))
        }
    }

    override fun fileClosed(source: FileEditorManager, file: VirtualFile) {
        ReverbWsClient.sendEvent("file_closed", mapOf(
            "path" to file.path,
            "name" to file.name
        ))
    }
}
