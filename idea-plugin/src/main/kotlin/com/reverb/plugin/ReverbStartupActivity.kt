package com.reverb.plugin

import com.intellij.openapi.project.Project
import com.intellij.openapi.startup.StartupActivity
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.editor.EditorFactory

class ReverbStartupActivity : StartupActivity {
    override fun runActivity(project: Project) {
        ReverbWsClient.connect()

        // Register action listeners that can't be registered via plugin.xml topics
        ApplicationManager.getApplication().invokeLater {
            try {
                ReverbCopyPasteListener().register()
            } catch (e: Exception) {
                // Ignore if already registered
            }
        }

        // Register document listener directly to the global EditorFactory
        ApplicationManager.getApplication().invokeLater {
            val factory = EditorFactory.getInstance()
            val eventMulticaster = factory.eventMulticaster
            try {
                eventMulticaster.addDocumentListener(ReverbDocumentListener(), project)
            } catch (e: Exception) {
                // Ignore if already registered
            }
        }
    }
}
