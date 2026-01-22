"""Conversation context management for AI interactions."""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime


@dataclass
class Message:
    """A conversation message."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, str]:
        """Convert to API format."""
        return {
            "role": self.role,
            "content": self.content,
        }


class ConversationContext:
    """
    Manages conversation history for AI context.

    Handles message history, context windowing, and
    token limit management.
    """

    def __init__(
        self,
        max_messages: int = 20,
        max_tokens: int = 8000,
    ):
        """
        Initialize conversation context.

        Args:
            max_messages: Maximum number of messages to keep
            max_tokens: Approximate maximum tokens in context
        """
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self._messages: List[Message] = []

    def add_user_message(self, content: str) -> None:
        """Add a user message to the context."""
        self._messages.append(Message(role="user", content=content))
        self._trim_context()

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to the context."""
        self._messages.append(Message(role="assistant", content=content))
        self._trim_context()

    def _trim_context(self) -> None:
        """Trim context to stay within limits."""
        # Trim by message count
        if len(self._messages) > self.max_messages:
            self._messages = self._messages[-self.max_messages:]

        # Estimate tokens and trim if needed
        total_tokens = self._estimate_tokens()
        while total_tokens > self.max_tokens and len(self._messages) > 2:
            self._messages.pop(0)
            total_tokens = self._estimate_tokens()

    def _estimate_tokens(self) -> int:
        """Estimate total tokens in context."""
        # Rough estimate: ~4 characters per token
        total_chars = sum(len(m.content) for m in self._messages)
        return total_chars // 4

    def get_messages(self) -> List[Dict[str, str]]:
        """Get messages in API format."""
        return [m.to_dict() for m in self._messages]

    def get_last_user_message(self) -> Optional[str]:
        """Get the last user message."""
        for m in reversed(self._messages):
            if m.role == "user":
                return m.content
        return None

    def get_last_assistant_message(self) -> Optional[str]:
        """Get the last assistant message."""
        for m in reversed(self._messages):
            if m.role == "assistant":
                return m.content
        return None

    def clear(self) -> None:
        """Clear all messages."""
        self._messages = []

    def clear_last_exchange(self) -> None:
        """Remove the last user-assistant exchange."""
        # Remove last assistant message
        if self._messages and self._messages[-1].role == "assistant":
            self._messages.pop()
        # Remove last user message
        if self._messages and self._messages[-1].role == "user":
            self._messages.pop()

    @property
    def message_count(self) -> int:
        """Get number of messages in context."""
        return len(self._messages)

    @property
    def is_empty(self) -> bool:
        """Check if context is empty."""
        return len(self._messages) == 0

    def to_summary(self) -> str:
        """
        Get a summary of the conversation.

        Useful for logging or display.
        """
        if not self._messages:
            return "No conversation history"

        lines = []
        for m in self._messages:
            prefix = "Q:" if m.role == "user" else "A:"
            content = m.content[:100] + "..." if len(m.content) > 100 else m.content
            lines.append(f"{prefix} {content}")

        return "\n".join(lines)


class ContextManager:
    """
    Manages multiple conversation contexts.

    Useful for different interview sessions or topics.
    """

    def __init__(self):
        self._contexts: Dict[str, ConversationContext] = {}
        self._current_id: Optional[str] = None

    def create_context(self, context_id: str) -> ConversationContext:
        """Create a new conversation context."""
        context = ConversationContext()
        self._contexts[context_id] = context
        self._current_id = context_id
        return context

    def get_context(self, context_id: str) -> Optional[ConversationContext]:
        """Get a context by ID."""
        return self._contexts.get(context_id)

    def get_or_create(self, context_id: str) -> ConversationContext:
        """Get existing context or create new one."""
        if context_id not in self._contexts:
            return self.create_context(context_id)
        self._current_id = context_id
        return self._contexts[context_id]

    @property
    def current(self) -> Optional[ConversationContext]:
        """Get the current context."""
        if self._current_id:
            return self._contexts.get(self._current_id)
        return None

    def delete_context(self, context_id: str) -> None:
        """Delete a context."""
        if context_id in self._contexts:
            del self._contexts[context_id]
            if self._current_id == context_id:
                self._current_id = None

    def clear_all(self) -> None:
        """Clear all contexts."""
        self._contexts.clear()
        self._current_id = None
