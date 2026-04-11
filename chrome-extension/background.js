/**
 * Reverb Agent Background Worker
 * Handles lifecycle events and cross-tab communication.
 */

chrome.runtime.onInstalled.addListener(() => {
  console.log("Reverb Agent Extension Installed");
});

// Optionally, we could run the WebSocket connection here in the background script
// instead of in the content script, and have the content scripts send messages here.
// But for raw event capturing, directly connecting from the content script is fine.
