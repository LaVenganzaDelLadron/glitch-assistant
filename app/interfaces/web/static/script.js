// app/interfaces/web/static/script.js
(function () {
    'use strict';

    const chatContainer = document.getElementById('chat-container');
    const messageInput = document.getElementById('message-input');
    const sendBtn = document.getElementById('send-btn');
    const loading = document.getElementById('loading');
    const newChatBtn = document.getElementById('new-chat-btn');

    // Markdown renderer with pipe-to-table support
    function renderMarkdown(text) {
        if (!text) return '';

        // Escape HTML
        let html = text
            .replace(/&/g, '&amp;')
            .replace(/</g, '<')
            .replace(/>/g, '>');

        // Code blocks (fenced)
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, function (_, lang, code) {
            var langClass = lang ? ' class="language-' + lang + '"' : '';
            return '<pre><code' + langClass + '>' + code.trim() + '</code></pre>';
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

        // ── Table rendering ──────────────────────────────
        html = html.replace(
            /((?:^[^\n]*\|[^\n]*\n?)+\n?)/gm,
            function (block) {
                var lines = block.trim().split('\n');
                if (lines.length < 2) return block;

                var sepLine = lines[1] || '';
                var isSeparator = /^[\s\|:\-]+$/.test(sepLine) && /\|/.test(sepLine) && /-{3,}/.test(sepLine);
                if (!isSeparator) return block;

                var separators = sepLine.split('|').filter(function (s) { return s.trim() !== ''; });
                var alignments = separators.map(function (sep) {
                    var trimmed = sep.trim();
                    if (trimmed.charAt(0) === ':' && trimmed.charAt(trimmed.length - 1) === ':') return 'center';
                    if (trimmed.charAt(trimmed.length - 1) === ':') return 'right';
                    return 'left';
                });

                var headerCells = lines[0].split('|').filter(function (c) { return c.trim() !== ''; }).map(function (c) { return c.trim(); });
                var dataRows = lines.slice(2).filter(function (row) { return row.trim() !== '' && /\|/.test(row); });

                var tableHtml = '<div class="table-wrapper"><table>';
                tableHtml += '<thead><tr>';
                headerCells.forEach(function (cell, i) {
                    var align = alignments[i] || 'left';
                    tableHtml += '<th style="text-align:' + align + '">' + cell + '</th>';
                });
                tableHtml += '</tr></thead>';
                tableHtml += '<tbody>';
                dataRows.forEach(function (row) {
                    var cells = row.split('|').filter(function (c) { return c.trim() !== ''; }).map(function (c) { return c.trim(); });
                    if (cells.length === 0) return;
                    tableHtml += '<tr>';
                    cells.forEach(function (cell, i) {
                        var align = alignments[i] || 'left';
                        tableHtml += '<td style="text-align:' + align + '">' + cell + '</td>';
                    });
                    tableHtml += '</tr>';
                });
                tableHtml += '</tbody></table></div>';
                return tableHtml;
            }
        );

        // Paragraphs (double newlines)
        var paragraphs = html.split(/\n\n+/);
        html = paragraphs.map(function (p) {
            var trimmed = p.trim();
            if (!trimmed) return '';
            if (/^<(?:table|div|ul|ol|li|pre|blockquote|hr|h[1-6])/.test(trimmed)) return trimmed;
            return '<p>' + trimmed.replace(/\n/g, '<br>') + '</p>';
        }).join('\n');

        return html;
    }

    function addMessage(role, content, meta) {
        var div = document.createElement('div');
        div.className = 'message ' + role;

        var bubble = document.createElement('div');
        bubble.className = 'bubble';

        if (role === 'assistant') {
            bubble.innerHTML = renderMarkdown(content);
        } else {
            bubble.textContent = content;
        }

        div.appendChild(bubble);

        if (meta) {
            var metaDiv = document.createElement('div');
            metaDiv.className = 'message-meta';
            if (meta.model) {
                var badge = document.createElement('span');
                badge.className = 'usage-badge';
                badge.textContent = 'Model: ' + meta.model;
                metaDiv.appendChild(badge);
            }
            if (meta.usage) {
                var badge = document.createElement('span');
                badge.className = 'usage-badge';
                badge.textContent = 'Tokens: ' + (meta.usage.total_tokens || '?');
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
        var message = messageInput.value.trim();
        if (!message) return;

        addMessage('user', message);
        messageInput.value = '';
        messageInput.style.height = 'auto';

        sendBtn.disabled = true;
        loading.classList.add('active');

        try {
            var response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: message }),
            });

            if (!response.ok) {
                var err = await response.json();
                throw new Error(err.detail || 'Request failed');
            }

            var data = await response.json();

            addMessage('assistant', data.content, {
                model: data.model,
                usage: data.usage,
            });
        } catch (error) {
            addMessage('assistant', '**Error:** ' + error.message);
        } finally {
            sendBtn.disabled = false;
            loading.classList.remove('active');
            messageInput.focus();
        }
    }

    async function resetConversation() {
        if (!confirm('Start a new conversation? This will clear the chat history.')) return;

        try {
            var response = await fetch('/api/reset', { method: 'POST' });
            if (!response.ok) throw new Error('Reset failed');
            chatContainer.innerHTML = '';
            addMessage('assistant', 'Conversation reset. How can I help you?');
        } catch (error) {
            addMessage('assistant', '**Error resetting:** ' + error.message);
        }
    }

    // Auto-resize textarea
    messageInput.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 120) + 'px';
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

    messageInput.focus();
})();
