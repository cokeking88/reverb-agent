package com.reverb.plugin

import com.google.gson.Gson
import com.intellij.openapi.diagnostic.Logger
import org.java_websocket.client.WebSocketClient
import org.java_websocket.handshake.ServerHandshake
import java.net.URI

object ReverbWsClient {
    private val log = Logger.getInstance(ReverbWsClient::class.java)
    private var client: WebSocketClient? = null
    private val gson = Gson()
    private val uri = URI("ws://127.0.0.1:19997")

    fun connect() {
        if (client != null && !client!!.isClosed) return

        client = object : WebSocketClient(uri) {
            override fun onOpen(handshakedata: ServerHandshake?) {
                log.info("Reverb IDE WebSocket Connected")
            }
            override fun onMessage(message: String?) {}
            override fun onClose(code: Int, reason: String?, remote: Boolean) {
                log.info("Reverb IDE WebSocket Closed")
                // Reconnect loop? Or manual retry on next event.
            }
            override fun onError(ex: Exception?) {
                log.info("Reverb IDE WebSocket Error: ${ex?.message}")
            }
        }
        client?.connect()
    }

    fun sendEvent(type: String, data: Map<String, Any>) {
        try {
            if (client == null || client!!.isClosed) {
                connect()
            }
            if (client!!.isOpen) {
                val payload = mapOf("type" to type, "data" to data)
                client!!.send(gson.toJson(payload))
            }
        } catch (e: Exception) {
            log.info("Failed to send reverb event: ${e.message}")
        }
    }
}
