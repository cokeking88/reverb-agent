package com.reverb.plugin

import com.intellij.openapi.project.Project
import com.intellij.openapi.startup.StartupActivity
import com.intellij.openapi.application.ApplicationManager

class ReverbStartupActivity : StartupActivity {
    override fun runActivity(project: Project) {
        ReverbWsClient.connect()

        // Register action listeners that can't be registered via plugin.xml topics
        ApplicationManager.getApplication().invokeLater {
            ReverbCopyPasteListener().register()
        }
    }
}
