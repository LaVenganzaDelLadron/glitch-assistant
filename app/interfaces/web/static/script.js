// app/interfaces/web/static/script.js
(function () {
    'use strict';

    const chatContainer = document.getElementById('chat-container');
    const messageInput = document.getElementById('message-input');
    const sendBtn = document.getElementById('send-btn');
    const loading = document.getElementById('loading');
    const newChatBtn = document.getElementById('new-chat-btn');

    // Simple markdown-like renderer for chat responses
    function renderMarkdown(text) {
        if (!text) return '';

        // Escape HTML
        let html = text
            .replace(/&/g, '&amp;')
            .replace(/</g, '<')
            .replace(/>/g, '>');

        // Code blocks (fenced)
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
            const langClass = lang ? ` class="language-${lang}"` : '';
            return `<pre><code${langClass}>${code.trim()}</code></pre>`;
        });

        // Inline code
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

        // Bold and italic
        html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

        // Blockquotes
        html = html.replace(/^>\s?(.+)$/gm, '<blockquote>$1</blockquote>');

        // Unordered lists
        html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
        html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');

        // Ordered lists
        html = html.replace(/^\d+\.\s+(.+)$/gm, '<li>$1</li>');

        // Horizontal rules
        html = html.replace(/^---$/gm, '<hr>');

        // Paragraphs (double newlines)
        const paragraphs = html.split(/\n\n+/);
        html = paragraphs.map(p => {
            const trimmed = p.trim();
            if (!trimmed) return '';
            // Skip if already wrapped in block-level tags
            if (/^<(?:ul|ol|li|pre|blockquote|hr|h[1-6])/.test(trimmed)) return trimmed;
            return `<p>${trimmed.replace(/\n/g, '<br>')}</p>`;
        }).join('\n');

        return html;
    }

    function addMessage(role, content, meta) {
        const div = document.createElement('div');
        div.className = `message ${role}`;

        const bubble = document.createElement('div');
        bubble.className = 'bubble';

        if (role === 'assistant') {
            bubble.innerHTML = renderMarkdown(content);
        } else {
            bubble.textContent = content;
        }

        div.appendChild(bubble);

        if (meta) {
            const metaDiv = document.createElement('div');
            metaDiv.className = 'message-meta';
            if (meta.model) {
                const badge = document.createElement('span');
                badge.className = 'usage-badge';
                badge.textContent = `Model: ${meta.model}`;
                metaDiv.appendChild(badge);
            }
            if (meta.usage) {
                const badge = document.createElement('span');
                badge.className = 'usage-badge';
                badge.textContent = `Tokens: ${meta.usage.total_tokens || '?'}`;
                metaDiv.appendChild(badge);
            }
            div.appendChild(metaDiv);
        }

        chatContainer.appendChild(div);
        scrollToBottom();
    }

    function scrollToBottom() {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    async function sendMessage() {
        const message = messageInput.value.trim();
        if (!message) return;

        // Add user message
        addMessage('user', message);
        messageInput.value = '';
        messageInput.style.height = 'auto';

        // Show loading
        sendBtn.disabled = true;
        loading.classList.add('active');

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message }),
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || 'Request failed');
            }

            const data = await response.json();

            // Add assistant response
            addMessage('assistant', data.content, {
                model: data.model,
                usage: data.usage,
            });
        } catch (error) {
            addMessage('assistant', `**Error:** ${error.message}`);
        } finally {
            sendBtn.disabled = false;
            loading.classList.remove('active');
            messageInput.focus();
        }
    }

    async function resetConversation() {
        if (!confirm('Start a new conversation? This will clear the chat history.')) return;

        try {
            const response = await fetch('/api/reset', { method: 'POST' });
            if (!response.ok) throw new Error('Reset failed');
            chatContainer.innerHTML = '';
            addMessage('assistant', 'Conversation reset. How can I help you?');
        } catch (error) {
            addMessage('assistant', `**Error resetting:** ${error.message}`);
        }
    }

    // Auto-resize textarea
    messageInput.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 150) + 'px';
    });

    // Send on Enter (Shift+Enter for newline)
    messageInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    sendBtn.addEventListener('click', sendMessage);
    newChatBtn.addEventListener('click', resetConversation);

    // Welcome message
    addMessage('assistant', 'Hello! I am **Glitch Assistant**, your AI software engineering assistant. How can I help you today?');

    // Focus input on load
    messageInput.focus();
})();
