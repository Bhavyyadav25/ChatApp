"""Web server to view answers on phone/tablet."""

import asyncio
import threading
import json
from typing import Optional
from aiohttp import web

from interview_assistant.core.events import Event, get_event_bus


class WebViewer:
    """
    Simple web server to view interview answers on another device (phone/tablet).

    Access from your phone at: http://<your-computer-ip>:8765
    """

    def __init__(self, port: int = 8765):
        self.port = port
        self._app = None
        self._runner = None
        self._site = None
        self._thread = None
        self._loop = None

        self._current_question = ""
        self._current_answer = ""
        self._answer_chunks = []

        self._event_bus = get_event_bus()
        self._setup_events()

    def _setup_events(self):
        """Subscribe to events."""
        self._event_bus.subscribe(Event.TRANSCRIPTION_COMPLETE, self._on_question)
        self._event_bus.subscribe(Event.AI_TOKEN_RECEIVED, self._on_token)
        self._event_bus.subscribe(Event.AI_RESPONSE_COMPLETE, self._on_answer_complete)

    def _on_question(self, text: str):
        """Handle new question."""
        self._current_question = text
        self._current_answer = ""
        self._answer_chunks = []

    def _on_token(self, token: str):
        """Handle streaming token."""
        self._answer_chunks.append(token)
        self._current_answer = "".join(self._answer_chunks)

    def _on_answer_complete(self, answer: str):
        """Handle complete answer."""
        self._current_answer = answer

    async def _handle_index(self, request):
        """Serve the main page."""
        html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Interview Assistant</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
            min-height: 100vh;
            padding: 16px;
        }
        .container { max-width: 800px; margin: 0 auto; }
        h1 {
            font-size: 1.2rem;
            color: #7c3aed;
            margin-bottom: 16px;
            text-align: center;
        }
        .status {
            text-align: center;
            padding: 8px;
            border-radius: 8px;
            margin-bottom: 16px;
            font-size: 0.9rem;
        }
        .status.connected { background: #065f46; color: #6ee7b7; }
        .status.disconnected { background: #7f1d1d; color: #fca5a5; }
        .section {
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .section h2 {
            font-size: 0.8rem;
            color: #a78bfa;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .question {
            font-size: 1rem;
            line-height: 1.5;
            color: #fbbf24;
        }
        .answer {
            font-size: 0.95rem;
            line-height: 1.6;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        .answer code {
            background: rgba(0,0,0,0.3);
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Fira Code', monospace;
        }
        .answer pre {
            background: rgba(0,0,0,0.4);
            padding: 12px;
            border-radius: 8px;
            overflow-x: auto;
            margin: 8px 0;
        }
        .typing::after {
            content: '|';
            animation: blink 1s infinite;
        }
        @keyframes blink {
            0%, 50% { opacity: 1; }
            51%, 100% { opacity: 0; }
        }
        .empty { color: #666; font-style: italic; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Interview Assistant</h1>
        <div id="status" class="status disconnected">Connecting...</div>

        <div class="section">
            <h2>Question</h2>
            <div id="question" class="question empty">Waiting for question...</div>
        </div>

        <div class="section">
            <h2>Answer</h2>
            <div id="answer" class="answer empty">Answer will appear here...</div>
        </div>
    </div>

    <script>
        const questionEl = document.getElementById('question');
        const answerEl = document.getElementById('answer');
        const statusEl = document.getElementById('status');

        function formatAnswer(text) {
            // Basic markdown-like formatting
            return text
                .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
                .replace(/`([^`]+)`/g, '<code>$1</code>')
                .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        }

        function poll() {
            fetch('/api/state')
                .then(r => r.json())
                .then(data => {
                    statusEl.textContent = 'Connected';
                    statusEl.className = 'status connected';

                    if (data.question) {
                        questionEl.textContent = data.question;
                        questionEl.className = 'question';
                    } else {
                        questionEl.textContent = 'Waiting for question...';
                        questionEl.className = 'question empty';
                    }

                    if (data.answer) {
                        answerEl.innerHTML = formatAnswer(data.answer);
                        answerEl.className = 'answer' + (data.streaming ? ' typing' : '');
                    } else {
                        answerEl.textContent = 'Answer will appear here...';
                        answerEl.className = 'answer empty';
                    }
                })
                .catch(err => {
                    statusEl.textContent = 'Disconnected - Retrying...';
                    statusEl.className = 'status disconnected';
                });
        }

        // Poll every 500ms
        setInterval(poll, 500);
        poll();
    </script>
</body>
</html>"""
        return web.Response(text=html, content_type='text/html')

    async def _handle_state(self, request):
        """Return current state as JSON."""
        return web.json_response({
            'question': self._current_question,
            'answer': self._current_answer,
            'streaming': len(self._answer_chunks) > 0 and self._current_answer != "".join(self._answer_chunks),
        })

    def _run_server(self):
        """Run the server in a thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        self._app = web.Application()
        self._app.router.add_get('/', self._handle_index)
        self._app.router.add_get('/api/state', self._handle_state)

        self._runner = web.AppRunner(self._app)
        self._loop.run_until_complete(self._runner.setup())

        self._site = web.TCPSite(self._runner, '0.0.0.0', self.port)
        self._loop.run_until_complete(self._site.start())

        self._loop.run_forever()

    def start(self) -> str:
        """
        Start the web server.

        Returns:
            URL to access the viewer
        """
        if self._thread and self._thread.is_alive():
            return self._get_url()

        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()

        # Get local IP
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except Exception:
            ip = "localhost"

        url = f"http://{ip}:{self.port}"
        print(f"\n{'='*50}")
        print(f"Phone Viewer available at: {url}")
        print(f"Open this URL on your phone to see answers!")
        print(f"{'='*50}\n")

        return url

    def _get_url(self) -> str:
        """Get the server URL."""
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except Exception:
            ip = "localhost"
        return f"http://{ip}:{self.port}"

    def stop(self):
        """Stop the server."""
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)


# Global instance
_web_viewer: Optional[WebViewer] = None


def get_web_viewer() -> WebViewer:
    """Get the global web viewer instance."""
    global _web_viewer
    if _web_viewer is None:
        _web_viewer = WebViewer()
    return _web_viewer
