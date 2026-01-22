"""Unified AI assistant interface supporting multiple backends."""

import asyncio
from typing import Callable, Optional, AsyncGenerator

from interview_assistant.core.config import get_config, AIBackend
from interview_assistant.core.events import Event, get_event_bus
from .prompts import InterviewType
from .context import ConversationContext


class AIAssistant:
    """
    Unified AI assistant supporting multiple backends.

    Supports:
    - Claude (Anthropic API)
    - Ollama (local LLM)

    Automatically uses the configured backend.
    """

    def __init__(self):
        """Initialize AI assistant."""
        self._config = get_config()
        self._event_bus = get_event_bus()

        self._claude_client = None
        self._ollama_client = None
        self._context = ConversationContext()

    def _get_backend(self):
        """Get the current backend client."""
        backend = self._config.ai.backend

        if backend == AIBackend.CLAUDE:
            return self._get_claude_client()
        else:
            return self._get_ollama_client()

    def _get_claude_client(self):
        """Get or create Claude client."""
        if self._claude_client is None:
            from .claude_client import ClaudeAssistant
            self._claude_client = ClaudeAssistant(
                api_key=self._config.ai.api_key.get_secret_value() or None,
                model=self._config.ai.claude_model,
            )
        return self._claude_client

    def _get_ollama_client(self):
        """Get or create Ollama client."""
        if self._ollama_client is None:
            from .ollama_client import OllamaClient
            self._ollama_client = OllamaClient(
                base_url=self._config.ai.ollama_url,
                model=self._config.ai.ollama_model,
            )
        return self._ollama_client

    async def get_answer(
        self,
        question: str,
        interview_type: InterviewType = InterviewType.DSA,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Generate an answer for an interview question.

        Args:
            question: The interview question
            interview_type: Type of interview
            on_token: Optional callback for streaming tokens

        Returns:
            Complete answer text
        """
        client = self._get_backend()
        return await client.get_answer(question, interview_type, on_token)

    async def stream_answer(
        self,
        question: str,
        interview_type: InterviewType = InterviewType.DSA,
    ) -> AsyncGenerator[str, None]:
        """
        Stream answer tokens as an async generator.

        Args:
            question: The interview question
            interview_type: Type of interview

        Yields:
            Answer tokens as they're generated
        """
        client = self._get_backend()
        async for token in client.stream_answer(question, interview_type):
            yield token

    def get_answer_sync(
        self,
        question: str,
        interview_type: InterviewType = InterviewType.DSA,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Synchronous wrapper for get_answer.

        Args:
            question: The interview question
            interview_type: Type of interview
            on_token: Optional callback for streaming tokens

        Returns:
            Complete answer text
        """
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self.get_answer(question, interview_type, on_token)
            )
        finally:
            loop.close()

    def clear_context(self) -> None:
        """Clear conversation context for all backends."""
        if self._claude_client:
            self._claude_client.clear_context()
        if self._ollama_client:
            self._ollama_client.clear_context()
        self._context.clear()

    def set_backend(self, backend: AIBackend) -> None:
        """
        Switch AI backend.

        Args:
            backend: New backend to use
        """
        self._config.ai.backend = backend

    async def check_backend_available(self) -> tuple[bool, str]:
        """
        Check if current backend is available.

        Returns:
            Tuple of (is_available, message)
        """
        backend = self._config.ai.backend

        if backend == AIBackend.CLAUDE:
            api_key = self._config.ai.api_key.get_secret_value()
            if not api_key:
                return False, "Claude API key not configured"
            return True, "Claude API ready"

        else:  # Ollama
            from .ollama_client import check_ollama_installed
            is_running = await check_ollama_installed()
            if not is_running:
                return False, "Ollama is not running. Start with: ollama serve"

            # Check if model is available
            from .ollama_client import get_available_models
            models = await get_available_models()
            if self._config.ai.ollama_model not in models:
                return False, f"Model '{self._config.ai.ollama_model}' not found. Pull with: ollama pull {self._config.ai.ollama_model}"

            return True, f"Ollama ready with {self._config.ai.ollama_model}"

    async def warmup(self) -> bool:
        """Warm up the AI backend to prepare for requests."""
        backend = self._config.ai.backend
        if backend == AIBackend.OLLAMA:
            client = self._get_ollama_client()
            return await client.warmup()
        return True

    async def list_ollama_models(self) -> list:
        """List available Ollama models."""
        from .ollama_client import get_available_models
        return await get_available_models()

    async def pull_ollama_model(
        self,
        model: str,
        on_progress: Optional[Callable[[str], None]] = None
    ) -> bool:
        """
        Pull an Ollama model.

        Args:
            model: Model name to pull
            on_progress: Progress callback

        Returns:
            True if successful
        """
        client = self._get_ollama_client()
        return await client.pull_model(model, on_progress)

    @property
    def current_backend(self) -> AIBackend:
        """Get current backend."""
        return self._config.ai.backend

    @property
    def current_model(self) -> str:
        """Get current model name."""
        if self._config.ai.backend == AIBackend.CLAUDE:
            return self._config.ai.claude_model
        return self._config.ai.ollama_model


# Global assistant instance
_assistant: Optional[AIAssistant] = None


def get_ai_assistant() -> AIAssistant:
    """Get the global AI assistant instance."""
    global _assistant
    if _assistant is None:
        _assistant = AIAssistant()
    return _assistant
