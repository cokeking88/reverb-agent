/**
 * Reverb Agent - Browser Observer Content Script
 *
 * Injects into all pages to listen for interactions like
 * clicks, inputs, scrolls, and captures basic DOM content.
 */

const REVERB_WS_PORT = 19999;
let ws = null;
let reconnectTimer = null;

// Connect to the local Reverb Agent websocket server
function connect() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return;
  }

  ws = new WebSocket(`ws://127.0.0.1:${REVERB_WS_PORT}/browser-events`);

  ws.onopen = () => {
    console.log("Reverb Agent: Connected to local observer server");
    if (reconnectTimer) {
      clearInterval(reconnectTimer);
      reconnectTimer = null;
    }

    // Send initial page load event with basic DOM info
    sendEvent("page_load", {
      title: document.title,
      url: window.location.href,
      content: document.body.innerText.substring(0, 1000) // First 1000 chars for context
    });
  };

  ws.onclose = () => {
    // console.log("Reverb Agent: Disconnected. Reconnecting in 5s...");
    ws = null;
    if (!reconnectTimer) {
      reconnectTimer = setInterval(connect, 5000);
    }
  };

  ws.onerror = (err) => {
    // console.error("Reverb Agent WS Error:", err);
  };
}

function sendEvent(type, data) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    try {
      ws.send(JSON.stringify({
        type: type,
        timestamp: Date.now(),
        data: data
      }));
    } catch (e) {
      console.error("Failed to send event:", e);
    }
  }
}

// 1. Listen for Clicks
document.addEventListener("click", (e) => {
  const target = e.target;
  if (!target) return;

  // Extract meaningful info about what was clicked
  const tag = target.tagName.toLowerCase();
  const text = target.innerText ? target.innerText.trim().substring(0, 50) : "";
  const id = target.id || "";
  const className = target.className && typeof target.className === 'string' ? target.className : "";

  // Try to find an aria-label, alt text, or value
  const ariaLabel = target.getAttribute('aria-label') || target.getAttribute('alt') || target.value || "";

  sendEvent("user_click", {
    tag: tag,
    text: text || ariaLabel,
    id: id,
    class: className,
    url: window.location.href
  });
}, { capture: true, passive: true });

// 2. Listen for Inputs (debounced)
let inputTimeout = null;
document.addEventListener("input", (e) => {
  const target = e.target;
  if (!target || !['input', 'textarea'].includes(target.tagName.toLowerCase())) return;

  if (inputTimeout) clearTimeout(inputTimeout);

  inputTimeout = setTimeout(() => {
    const id = target.id || "";
    const name = target.name || "";
    const type = target.type || "";

    // DO NOT send actual password values
    let value = target.value || "";
    if (type === "password") value = "***HIDDEN***";

    sendEvent("user_input", {
      tag: target.tagName.toLowerCase(),
      id: id,
      name: name,
      type: type,
      value_preview: value.substring(0, 100), // Preview only
      url: window.location.href
    });
  }, 1500); // 1.5s debounce for typing
}, { capture: true, passive: true });


// Initialize connection
connect();
