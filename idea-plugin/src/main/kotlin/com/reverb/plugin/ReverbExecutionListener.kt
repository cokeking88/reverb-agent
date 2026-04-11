package com.reverb.plugin

import com.intellij.execution.ExecutionListener
import com.intellij.execution.process.ProcessHandler
import com.intellij.execution.runners.ExecutionEnvironment
import com.intellij.openapi.project.Project

class ReverbExecutionListener : ExecutionListener {
    override fun processStarted(executorId: String, env: ExecutionEnvironment, handler: ProcessHandler) {
        ReverbWsClient.sendEvent("ide_execution", mapOf(
            "action" to "started",
            "executor" to executorId,
            "configuration" to (env.runProfile.name ?: "Unknown")
        ))
    }

    override fun processTerminated(executorId: String, env: ExecutionEnvironment, handler: ProcessHandler, exitCode: Int) {
        ReverbWsClient.sendEvent("ide_execution", mapOf(
            "action" to "terminated",
            "executor" to executorId,
            "configuration" to (env.runProfile.name ?: "Unknown"),
            "exitCode" to exitCode
        ))
    }
}
