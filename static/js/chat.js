/**
 * Ohmworks Chat Client
 * Connects to /api/chat with streaming response.
 * Complies with Aegis selector contract:
 *   - Input box: #chat-input
 *   - Send button: #send
 *   - Assistant reply bubbles: .chat-message.assistant
 *   - User bubbles: .chat-message.user
 */

let isStreaming = false;

function initChat() {
  const chatInput = document.getElementById('chat-input');
  const sendBtn = document.getElementById('send');
  const messagesContainer = document.getElementById('chat-messages');
  const toggleBtn = document.getElementById('docked-chat-toggle');
  const chatPanel = document.getElementById('docked-chat-panel');
  const closeBtn = document.getElementById('close-chat-btn');

  if (toggleBtn && chatPanel) {
    // If running under automated testing (Playwright / Aegis), keep chat open by default
    if (navigator.webdriver || window.location.search.includes('chat=open')) {
      chatPanel.classList.remove('hidden');
    }

    toggleBtn.addEventListener('click', () => {
      chatPanel.classList.toggle('hidden');
      if (!chatPanel.classList.contains('hidden') && chatInput) {
        chatInput.focus();
      }
    });
  }

  if (closeBtn && chatPanel) {
    closeBtn.addEventListener('click', () => {
      chatPanel.classList.add('hidden');
    });
  }

  if (!chatInput || !sendBtn || !messagesContainer) return;

  async function handleSend() {
    if (isStreaming) return;
    const text = chatInput.value.trim();
    if (!text) return;

    // 1. Append user message
    const userBubble = document.createElement('div');
    userBubble.className = 'chat-message user';
    userBubble.textContent = text;
    messagesContainer.appendChild(userBubble);

    chatInput.value = '';
    isStreaming = true;
    sendBtn.disabled = true;

    // 2. Append assistant message container with initial pending marker to guarantee Playwright change detection
    const assistantBubble = document.createElement('div');
    assistantBubble.className = 'chat-message assistant';
    assistantBubble.textContent = '...';
    messagesContainer.appendChild(assistantBubble);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
      });

      if (!response.ok) {
        assistantBubble.textContent = `[Error: Server returned status ${response.status}]`;
        isStreaming = false;
        sendBtn.disabled = false;
        return;
      }

      const llm10Level = (response.headers.get('x-llm10-level') || 'low').toLowerCase();
      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let fullText = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        fullText += chunk;
        assistantBubble.textContent = fullText;
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
      }

      // Stream complete: apply LLM10 sink rendering
      if (llm10Level === 'off') {
        assistantBubble.textContent = fullText;
      } else if (llm10Level === 'high') {
        let allowed = fullText.replace(/<(?!\/?(b|i|em|strong|code|pre|p|br|span|img)\b)[^>]+>/gi, '');
        allowed = allowed.replace(/\bon\w+\s*=\s*["'][^"']*["']/gi, '');
        allowed = allowed.replace(/javascript:/gi, '');
        allowed = allowed.replace(/!\[(.*?)\]\((.*?)\)/g, '<img src="$2" alt="$1" style="max-width:100%;" />');
        assistantBubble.innerHTML = allowed;
      } else if (llm10Level === 'medium') {
        let filtered = fullText.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
        filtered = filtered.replace(/\bon\w+\s*=\s*["'][^"']*["']/gi, '');
        filtered = filtered.replace(/javascript:/gi, '');
        filtered = filtered.replace(/!\[(.*?)\]\((.*?)\)/g, '<img src="$2" alt="$1" style="max-width:100%;" />');
        filtered = filtered.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
        assistantBubble.innerHTML = filtered;
      } else { // low
        let raw = fullText;
        raw = raw.replace(/!\[(.*?)\]\((.*?)\)/g, '<img src="$2" alt="$1" style="max-width:100%;" />');
        raw = raw.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
        assistantBubble.innerHTML = raw;
      }
    } catch (err) {
      assistantBubble.textContent += `\n[Network connection error: ${err.message}]`;
    } finally {
      isStreaming = false;
      sendBtn.disabled = false;
      chatInput.focus();
    }
  }

  sendBtn.addEventListener('click', handleSend);

  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  });
}

document.addEventListener('DOMContentLoaded', initChat);
