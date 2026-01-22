"""SQLite database for Q&A history storage."""

import asyncio
from pathlib import Path
from typing import List, Optional
from uuid import uuid4
from datetime import datetime

from sqlalchemy import create_engine, select, delete
from sqlalchemy.orm import sessionmaker, Session as DBSession

from interview_assistant.core.config import CONFIG_DIR
from interview_assistant.core.session import QAPair, InterviewType
from .models import Base, Session, Question, Answer, InterviewTypeDB


# Database path
DB_PATH = CONFIG_DIR / "history.db"


class Database:
    """
    SQLite database manager for Q&A history.

    Provides methods for storing and retrieving
    interview questions and answers.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create engine
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            echo=False,
        )

        # Create tables
        Base.metadata.create_all(self.engine)

        # Session factory
        self.SessionLocal = sessionmaker(bind=self.engine)

    def _get_session(self) -> DBSession:
        """Get a database session."""
        return self.SessionLocal()

    def save_qa_pair(self, qa: QAPair, session_id: Optional[str] = None) -> bool:
        """
        Save a Q&A pair to the database.

        Args:
            qa: QAPair to save
            session_id: Optional session ID to associate with

        Returns:
            True if saved successfully
        """
        try:
            with self._get_session() as session:
                # Convert interview type
                interview_type = InterviewTypeDB(qa.interview_type.value)

                # Create question
                question = Question(
                    id=qa.id,
                    session_id=session_id,
                    question_text=qa.question,
                    timestamp=qa.timestamp,
                    interview_type=interview_type,
                )

                # Create answer
                answer = Answer(
                    id=str(uuid4()),
                    question_id=qa.id,
                    answer_text=qa.answer,
                    timestamp=datetime.now(),
                )

                question.answer = answer

                session.add(question)
                session.commit()
                return True

        except Exception as e:
            print(f"Error saving Q&A pair: {e}")
            return False

    def get_all_qa_pairs(self, limit: int = 100) -> List[QAPair]:
        """
        Get all Q&A pairs from database.

        Args:
            limit: Maximum number of pairs to return

        Returns:
            List of QAPair objects
        """
        try:
            with self._get_session() as session:
                stmt = select(Question).order_by(Question.timestamp.desc()).limit(limit)
                questions = session.execute(stmt).scalars().all()

                result = []
                for q in questions:
                    qa = QAPair(
                        id=q.id,
                        question=q.question_text,
                        answer=q.answer.answer_text if q.answer else "",
                        timestamp=q.timestamp,
                        interview_type=InterviewType(q.interview_type.value),
                    )
                    result.append(qa)

                return result

        except Exception as e:
            print(f"Error getting Q&A pairs: {e}")
            return []

    def get_qa_pairs_by_type(self, interview_type: InterviewType, limit: int = 50) -> List[QAPair]:
        """
        Get Q&A pairs filtered by interview type.

        Args:
            interview_type: Type of interview
            limit: Maximum number of pairs

        Returns:
            List of QAPair objects
        """
        try:
            with self._get_session() as session:
                db_type = InterviewTypeDB(interview_type.value)
                stmt = (
                    select(Question)
                    .where(Question.interview_type == db_type)
                    .order_by(Question.timestamp.desc())
                    .limit(limit)
                )
                questions = session.execute(stmt).scalars().all()

                result = []
                for q in questions:
                    qa = QAPair(
                        id=q.id,
                        question=q.question_text,
                        answer=q.answer.answer_text if q.answer else "",
                        timestamp=q.timestamp,
                        interview_type=interview_type,
                    )
                    result.append(qa)

                return result

        except Exception as e:
            print(f"Error getting Q&A pairs by type: {e}")
            return []

    def search_qa_pairs(self, query: str, limit: int = 50) -> List[QAPair]:
        """
        Search Q&A pairs by text content.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching QAPair objects
        """
        try:
            with self._get_session() as session:
                # Simple LIKE search
                pattern = f"%{query}%"
                stmt = (
                    select(Question)
                    .where(
                        (Question.question_text.like(pattern)) |
                        (Question.answer.has(Answer.answer_text.like(pattern)))
                    )
                    .order_by(Question.timestamp.desc())
                    .limit(limit)
                )
                questions = session.execute(stmt).scalars().all()

                result = []
                for q in questions:
                    qa = QAPair(
                        id=q.id,
                        question=q.question_text,
                        answer=q.answer.answer_text if q.answer else "",
                        timestamp=q.timestamp,
                        interview_type=InterviewType(q.interview_type.value),
                    )
                    result.append(qa)

                return result

        except Exception as e:
            print(f"Error searching Q&A pairs: {e}")
            return []

    def delete_qa_pair(self, qa_id: str) -> bool:
        """
        Delete a Q&A pair.

        Args:
            qa_id: ID of the Q&A pair to delete

        Returns:
            True if deleted successfully
        """
        try:
            with self._get_session() as session:
                stmt = delete(Question).where(Question.id == qa_id)
                session.execute(stmt)
                session.commit()
                return True

        except Exception as e:
            print(f"Error deleting Q&A pair: {e}")
            return False

    def clear_all(self) -> bool:
        """
        Clear all Q&A history.

        Returns:
            True if cleared successfully
        """
        try:
            with self._get_session() as session:
                session.execute(delete(Answer))
                session.execute(delete(Question))
                session.execute(delete(Session))
                session.commit()
                return True

        except Exception as e:
            print(f"Error clearing history: {e}")
            return False

    def get_stats(self) -> dict:
        """
        Get statistics about stored data.

        Returns:
            Dictionary with stats
        """
        try:
            with self._get_session() as session:
                total_questions = session.query(Question).count()
                total_sessions = session.query(Session).count()

                # Count by type
                by_type = {}
                for t in InterviewTypeDB:
                    count = session.query(Question).filter(
                        Question.interview_type == t
                    ).count()
                    by_type[t.value] = count

                return {
                    "total_questions": total_questions,
                    "total_sessions": total_sessions,
                    "by_type": by_type,
                }

        except Exception as e:
            print(f"Error getting stats: {e}")
            return {}


# Global database instance
_db: Optional[Database] = None


def get_database() -> Database:
    """Get the global database instance."""
    global _db
    if _db is None:
        _db = Database()
    return _db
