package com.reverb.plugin

import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.openapi.fileEditor.FileEditorManagerListener
import com.intellij.openapi.vfs.VirtualFile

class ReverbFileEditorListener : FileEditorManagerListener {
    override fun fileOpened(source: FileEditorManager, file: VirtualFile) {
        ReverbWsClient.sendEvent("file_focus", mapOf(
            "path" to file.path,
            "name" to file.name
        ))
    }

    override fun fileClosed(source: FileEditorManager, file: VirtualFile) {
        ReverbWsClient.sendEvent("file_closed", mapOf(
            "path" to file.path,
            "name" to file.name
        ))
    }
}
