package com.reverb.plugin

import com.google.gson.Gson
import com.intellij.openapi.diagnostic.Logger
import org.java_websocket.client.WebSocketClient
import org.java_websocket.handshake.ServerHandshake
import java.net.URI

import com.intellij.openapi.application.ApplicationManager

object ReverbWsClient {
    private val log = Logger.getInstance(ReverbWsClient::class.java)
    private var client: WebSocketClient? = null
    private val gson = Gson()
    private val uri = URI("ws://127.0.0.1:19997")

    fun connect() {
        if (client != null && !client!!.isClosed) return

        client = object : WebSocketClient(uri) {
            override fun onOpen(handshakedata: ServerHandshake?) {
                log.warn("Reverb IDE WebSocket Connected to 19997")
            }
            override fun onMessage(message: String?) {}
            override fun onClose(code: Int, reason: String?, remote: Boolean) {
                log.warn("Reverb IDE WebSocket Closed: $reason")
                client = null
            }
            override fun onError(ex: Exception?) {
                log.warn("Reverb IDE WebSocket Error: ${ex?.message}")
            }
        }
        ApplicationManager.getApplication().executeOnPooledThread {
            try {
                client?.connectBlocking()
            } catch (e: Exception) {
                log.warn("Reverb IDE WebSocket Failed to connect: ${e.message}")
                client = null
            }
        }
    }

    fun sendEvent(type: String, data: Map<String, Any>) {
        ApplicationManager.getApplication().executeOnPooledThread {
            try {
                if (client == null || client!!.isClosed) {
                    connect()
                    // wait up to 1 second for background connect
                    for (i in 1..10) {
                        if (client != null && client!!.isOpen) break
                        Thread.sleep(100)
                    }
                }

                if (client != null && client!!.isOpen) {
                    val payload = mapOf("type" to type, "data" to data)
                    val jsonStr = gson.toJson(payload)
                    client!!.send(jsonStr)
                    log.warn("Sent Reverb Event: $jsonStr")
                } else {
                    log.warn("Cannot send Reverb Event: WS is not open (reconnecting in background...)")
                }
            } catch (e: Exception) {
                log.warn("Failed to send reverb event: ${e.message}")
            }
        }
    }
}
