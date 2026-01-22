"""AI integration modules."""

from .claude_client import ClaudeAssistant
from .ollama_client import OllamaClient
from .assistant import AIAssistant, get_ai_assistant
from .prompts import get_system_prompt, InterviewType
from .context import ConversationContext

__all__ = [
    "ClaudeAssistant",
    "OllamaClient",
    "AIAssistant",
    "get_ai_assistant",
    "get_system_prompt",
    "InterviewType",
    "ConversationContext",
]
