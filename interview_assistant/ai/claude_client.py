"""Claude AI client for generating interview answers."""

import asyncio
from typing import Callable, Optional, AsyncGenerator

from interview_assistant.core.events import Event, get_event_bus
from interview_assistant.core.config import get_config
from .prompts import InterviewType, get_system_prompt
from .context import ConversationContext


class ClaudeAssistant:
    """
    Async Claude API client for generating interview answers.

    Supports streaming responses for real-time display.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-5-20250929",
    ):
        """
        Initialize Claude assistant.

        Args:
            api_key: Anthropic API key (uses config if not provided)
            model: Model to use for generation
        """
        self._api_key = api_key
        self._model = model
        self._client = None
        self._context = ConversationContext()
        self._event_bus = get_event_bus()

    def _get_client(self):
        """Get or create the Anthropic client."""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic

                api_key = self._api_key
                if not api_key:
                    config = get_config()
                    api_key = config.ai.api_key.get_secret_value()

                if not api_key:
                    raise ValueError("No API key provided. Set ANTHROPIC_API_KEY or configure in settings.")

                self._client = AsyncAnthropic(api_key=api_key)
            except ImportError:
                raise ImportError("anthropic package not installed. Run: pip install anthropic")

        return self._client

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
        client = self._get_client()

        # Get system prompt
        system_prompt = get_system_prompt(interview_type)

        # Build messages
        messages = []
        if include_context:
            messages = self._context.get_messages()

        # Add current question
        messages.append({"role": "user", "content": question})

        # Emit start event
        self._event_bus.emit(Event.AI_REQUEST_STARTED, question)

        try:
            full_response = ""

            async with client.messages.stream(
                model=self._model,
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    full_response += text

                    # Emit token event
                    self._event_bus.emit(Event.AI_TOKEN_RECEIVED, text)

                    # Call callback if provided
                    if on_token:
                        on_token(text)

            # Update context
            self._context.add_user_message(question)
            self._context.add_assistant_message(full_response)

            # Emit complete event
            self._event_bus.emit(Event.AI_RESPONSE_COMPLETE, full_response)

            return full_response

        except Exception as e:
            error_msg = f"Error generating response: {e}"
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
        client = self._get_client()

        system_prompt = get_system_prompt(interview_type)

        messages = []
        if include_context:
            messages = self._context.get_messages()
        messages.append({"role": "user", "content": question})

        self._event_bus.emit(Event.AI_REQUEST_STARTED, question)

        try:
            full_response = ""

            async with client.messages.stream(
                model=self._model,
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    full_response += text
                    self._event_bus.emit(Event.AI_TOKEN_RECEIVED, text)
                    yield text

            self._context.add_user_message(question)
            self._context.add_assistant_message(full_response)
            self._event_bus.emit(Event.AI_RESPONSE_COMPLETE, full_response)

        except Exception as e:
            error_msg = f"Error generating response: {e}"
            self._event_bus.emit(Event.AI_ERROR, error_msg)
            raise

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
        """Clear conversation context."""
        self._context.clear()

    def set_model(self, model: str) -> None:
        """Set the model to use."""
        self._model = model

    @property
    def context(self) -> ConversationContext:
        """Get the conversation context."""
        return self._context

    @property
    def model(self) -> str:
        """Get the current model."""
        return self._model


class AIAssistantManager:
    """
    Manages AI assistant instances and integrates with the app.
    """

    def __init__(self):
        self._assistant: Optional[ClaudeAssistant] = None
        self._event_bus = get_event_bus()

    def get_assistant(self) -> ClaudeAssistant:
        """Get or create the AI assistant."""
        if self._assistant is None:
            config = get_config()
            self._assistant = ClaudeAssistant(
                model=config.ai.model,
            )
        return self._assistant

    async def process_question(
        self,
        question: str,
        interview_type: InterviewType,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Process a question and generate an answer.

        Args:
            question: Interview question
            interview_type: Type of interview
            on_token: Token callback

        Returns:
            Generated answer
        """
        assistant = self.get_assistant()
        return await assistant.get_answer(question, interview_type, on_token)

    def reset(self) -> None:
        """Reset the assistant (clear context)."""
        if self._assistant:
            self._assistant.clear_context()
