"""Ollama client for local LLM inference."""

import asyncio
import aiohttp
import json
from typing import Callable, Optional, AsyncGenerator, List, Dict, Any

from interview_assistant.core.events import Event, get_event_bus
from .prompts import InterviewType, get_system_prompt
from .context import ConversationContext


class OllamaClient:
    """
    Ollama client for local LLM inference.

    Supports streaming responses for real-time display.
    Ollama must be running locally (default: http://localhost:11434)
    """

    # Recommended models for coding interviews
    RECOMMENDED_MODELS = [
        "deepseek-coder-v2:16b",  # Excellent for coding
        "codellama:13b",           # Good for code
        "llama3.1:8b",             # Fast, general purpose
        "mistral:7b",              # Fast, good quality
        "mixtral:8x7b",            # High quality, needs more RAM
        "qwen2.5-coder:7b",        # Good for coding
    ]

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.1:8b",
        timeout: int = 300,  # 5 minutes - Ollama can be slow on first load
    ):
        """
        Initialize Ollama client.

        Args:
            base_url: Ollama server URL
            model: Model name to use
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout = timeout
        self._context = ConversationContext()
        self._event_bus = get_event_bus()
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        return self._session

    async def check_connection(self) -> bool:
        """
        Check if Ollama is running and accessible.

        Returns:
            True if connected successfully
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    return response.status == 200
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        """
        List available models in Ollama.

        Returns:
            List of model names
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            print(f"Error listing models: {e}")
        return []

    async def pull_model(self, model: str, on_progress: Optional[Callable[[str], None]] = None) -> bool:
        """
        Pull/download a model.

        Args:
            model: Model name to pull
            on_progress: Optional progress callback

        Returns:
            True if successful
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/pull",
                    json={"name": model},
                    timeout=aiohttp.ClientTimeout(total=3600)  # 1 hour for large models
                ) as response:
                    async for line in response.content:
                        if line:
                            try:
                                data = json.loads(line)
                                status = data.get("status", "")
                                if on_progress:
                                    on_progress(status)
                                if "success" in status.lower():
                                    return True
                            except json.JSONDecodeError:
                                pass
                    return response.status == 200
        except Exception as e:
            print(f"Error pulling model: {e}")
            return False

    async def warmup(self) -> bool:
        """
        Warm up the model by sending a simple request.
        This loads the model into memory for faster subsequent requests.

        Returns:
            True if warmup successful
        """
        try:
            session = await self._get_session()
            async with session.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                },
            ) as response:
                return response.status == 200
        except Exception as e:
            print(f"Warmup failed: {e}")
            return False

    async def get_answer(
        self,
        question: str,
        interview_type: InterviewType = InterviewType.DSA,
        on_token: Optional[Callable[[str], None]] = None,
        include_context: bool = True,
    ) -> str:
        """
        Generate an answer for an interview question.

        Args:
            question: The interview question
            interview_type: Type of interview
            on_token: Optional callback for streaming tokens
            include_context: Whether to include conversation history

        Returns:
            Complete answer text
        """
        system_prompt = get_system_prompt(interview_type)

        # Build messages
        messages = [{"role": "system", "content": system_prompt}]

        if include_context:
            messages.extend(self._context.get_messages())

        messages.append({"role": "user", "content": question})

        # Emit start event
        self._event_bus.emit(Event.AI_REQUEST_STARTED, question)

        try:
            full_response = ""
            session = await self._get_session()

            async with session.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 4096,
                    }
                },
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Ollama error: {error_text}")

                async for line in response.content:
                    if line:
                        try:
                            data = json.loads(line)
                            if "message" in data:
                                token = data["message"].get("content", "")
                                if token:
                                    full_response += token

                                    # Emit token event
                                    self._event_bus.emit(Event.AI_TOKEN_RECEIVED, token)

                                    # Call callback
                                    if on_token:
                                        on_token(token)

                            # Check if done
                            if data.get("done", False):
                                break

                        except json.JSONDecodeError:
                            pass

            # Update context
            self._context.add_user_message(question)
            self._context.add_assistant_message(full_response)

            # Emit complete event
            self._event_bus.emit(Event.AI_RESPONSE_COMPLETE, full_response)

            return full_response

        except asyncio.TimeoutError:
            error_msg = "Request timed out. Try asking a simpler question or check if Ollama is running."
            self._event_bus.emit(Event.AI_ERROR, error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Ollama error: {e}"
            self._event_bus.emit(Event.AI_ERROR, error_msg)
            raise

    async def stream_answer(
        self,
        question: str,
        interview_type: InterviewType = InterviewType.DSA,
        include_context: bool = True,
    ) -> AsyncGenerator[str, None]:
        """
        Stream answer tokens as an async generator.

        Args:
            question: The interview question
            interview_type: Type of interview
            include_context: Whether to include conversation history

        Yields:
            Answer tokens as they're generated
        """
        system_prompt = get_system_prompt(interview_type)

        messages = [{"role": "system", "content": system_prompt}]
        if include_context:
            messages.extend(self._context.get_messages())
        messages.append({"role": "user", "content": question})

        self._event_bus.emit(Event.AI_REQUEST_STARTED, question)

        try:
            full_response = ""

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": True,
                    },
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    async for line in response.content:
                        if line:
                            try:
                                data = json.loads(line)
                                if "message" in data:
                                    token = data["message"].get("content", "")
                                    if token:
                                        full_response += token
                                        self._event_bus.emit(Event.AI_TOKEN_RECEIVED, token)
                                        yield token
                            except json.JSONDecodeError:
                                pass

            self._context.add_user_message(question)
            self._context.add_assistant_message(full_response)
            self._event_bus.emit(Event.AI_RESPONSE_COMPLETE, full_response)

        except Exception as e:
            error_msg = f"Ollama error: {e}"
            self._event_bus.emit(Event.AI_ERROR, error_msg)
            raise

    def clear_context(self) -> None:
        """Clear conversation context."""
        self._context.clear()

    def set_model(self, model: str) -> None:
        """Set the model to use."""
        self.model = model

    @property
    def context(self) -> ConversationContext:
        """Get the conversation context."""
        return self._context

    @classmethod
    def get_recommended_models(cls) -> List[str]:
        """Get list of recommended models for interviews."""
        return cls.RECOMMENDED_MODELS.copy()


async def check_ollama_installed() -> bool:
    """Check if Ollama is installed and running."""
    client = OllamaClient()
    return await client.check_connection()


async def get_available_models() -> List[str]:
    """Get list of available Ollama models."""
    client = OllamaClient()
    return await client.list_models()
