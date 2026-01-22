"""Interview session state management."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from .events import Event, get_event_bus


class InterviewType(str, Enum):
    """Types of interviews supported."""
    DSA = "dsa"
    SYSTEM_DESIGN = "system_design"
    BEHAVIORAL = "behavioral"


@dataclass
class QAPair:
    """A question-answer pair."""
    id: str = field(default_factory=lambda: str(uuid4()))
    question: str = ""
    answer: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    interview_type: InterviewType = InterviewType.DSA

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "question": self.question,
            "answer": self.answer,
            "timestamp": self.timestamp.isoformat(),
            "interview_type": self.interview_type.value,
        }


@dataclass
class InterviewSession:
    """
    Manages the state of an interview session.

    Tracks questions, answers, and session metadata.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    interview_type: InterviewType = InterviewType.DSA
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: Optional[datetime] = None
    qa_pairs: List[QAPair] = field(default_factory=list)

    # Current state
    is_recording: bool = False
    is_processing: bool = False
    current_question: str = ""
    current_answer: str = ""

    def __post_init__(self):
        self._event_bus = get_event_bus()

    def start_recording(self) -> None:
        """Start recording audio."""
        self.is_recording = True
        self._event_bus.emit(Event.RECORDING_STARTED)

    def stop_recording(self) -> None:
        """Stop recording audio."""
        self.is_recording = False
        self._event_bus.emit(Event.RECORDING_STOPPED)

    def set_interview_type(self, interview_type: InterviewType) -> None:
        """Change the interview type."""
        self.interview_type = interview_type
        self._event_bus.emit(Event.INTERVIEW_TYPE_CHANGED, interview_type)

    def set_current_question(self, question: str) -> None:
        """Set the current transcribed question."""
        self.current_question = question
        self._event_bus.emit(Event.TRANSCRIPTION_COMPLETE, question)

    def append_to_answer(self, token: str) -> None:
        """Append a token to the current answer (for streaming)."""
        self.current_answer += token
        self._event_bus.emit(Event.AI_TOKEN_RECEIVED, token)

    def complete_qa_pair(self) -> QAPair:
        """Complete the current Q&A pair and add to history."""
        qa_pair = QAPair(
            question=self.current_question,
            answer=self.current_answer,
            interview_type=self.interview_type,
        )
        self.qa_pairs.append(qa_pair)

        # Reset current state
        self.current_question = ""
        self.current_answer = ""
        self.is_processing = False

        self._event_bus.emit(Event.AI_RESPONSE_COMPLETE, qa_pair)
        self._event_bus.emit(Event.HISTORY_UPDATED, self.qa_pairs)

        return qa_pair

    def clear_current(self) -> None:
        """Clear current question and answer."""
        self.current_question = ""
        self.current_answer = ""
        self.is_processing = False

    def end_session(self) -> None:
        """End the interview session."""
        self.ended_at = datetime.now()
        self.is_recording = False
        self.is_processing = False
        self._event_bus.emit(Event.SESSION_ENDED, self)

    def get_conversation_history(self) -> List[dict]:
        """Get conversation history for AI context."""
        history = []
        for qa in self.qa_pairs[-10:]:  # Last 10 Q&A pairs
            history.append({"role": "user", "content": qa.question})
            history.append({"role": "assistant", "content": qa.answer})
        return history

    def to_dict(self) -> dict:
        """Convert session to dictionary."""
        return {
            "id": self.id,
            "interview_type": self.interview_type.value,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "qa_pairs": [qa.to_dict() for qa in self.qa_pairs],
        }


class SessionManager:
    """Manages interview sessions."""

    def __init__(self):
        self._current_session: Optional[InterviewSession] = None
        self._sessions: List[InterviewSession] = []
        self._event_bus = get_event_bus()

    @property
    def current_session(self) -> Optional[InterviewSession]:
        """Get the current active session."""
        return self._current_session

    def start_session(self, interview_type: InterviewType = InterviewType.DSA) -> InterviewSession:
        """Start a new interview session."""
        # End current session if exists
        if self._current_session:
            self.end_session()

        self._current_session = InterviewSession(interview_type=interview_type)
        self._sessions.append(self._current_session)
        self._event_bus.emit(Event.SESSION_STARTED, self._current_session)

        return self._current_session

    def end_session(self) -> Optional[InterviewSession]:
        """End the current session."""
        if self._current_session:
            self._current_session.end_session()
            session = self._current_session
            self._current_session = None
            return session
        return None

    def get_session(self) -> InterviewSession:
        """Get current session, creating one if needed."""
        if not self._current_session:
            self.start_session()
        return self._current_session

    def get_all_sessions(self) -> List[InterviewSession]:
        """Get all sessions."""
        return self._sessions.copy()
