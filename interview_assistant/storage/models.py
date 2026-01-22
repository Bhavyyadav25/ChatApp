"""Database models for storing Q&A history."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Text, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()


class InterviewTypeDB(enum.Enum):
    """Interview type enum for database."""
    DSA = "dsa"
    SYSTEM_DESIGN = "system_design"
    BEHAVIORAL = "behavioral"


class Session(Base):
    """Interview session model."""

    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True)
    interview_type = Column(SQLEnum(InterviewTypeDB), default=InterviewTypeDB.DSA)
    started_at = Column(DateTime, default=datetime.now)
    ended_at = Column(DateTime, nullable=True)

    # Relationships
    qa_pairs = relationship("Question", back_populates="session", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "interview_type": self.interview_type.value,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
        }


class Question(Base):
    """Question model."""

    __tablename__ = "questions"

    id = Column(String(36), primary_key=True)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=True)
    question_text = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.now)
    interview_type = Column(SQLEnum(InterviewTypeDB), default=InterviewTypeDB.DSA)

    # Relationships
    session = relationship("Session", back_populates="qa_pairs")
    answer = relationship("Answer", back_populates="question", uselist=False, cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "question": self.question_text,
            "timestamp": self.timestamp.isoformat(),
            "interview_type": self.interview_type.value,
            "answer": self.answer.to_dict() if self.answer else None,
        }


class Answer(Base):
    """Answer model."""

    __tablename__ = "answers"

    id = Column(String(36), primary_key=True)
    question_id = Column(String(36), ForeignKey("questions.id"), nullable=False)
    answer_text = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.now)
    model_used = Column(String(100), nullable=True)

    # Relationships
    question = relationship("Question", back_populates="answer")

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "question_id": self.question_id,
            "answer": self.answer_text,
            "timestamp": self.timestamp.isoformat(),
            "model_used": self.model_used,
        }
