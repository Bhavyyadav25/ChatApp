"""Text post-processing for transcriptions."""

import re
from typing import List, Optional


class TextProcessor:
    """
    Post-process transcribed text for better quality.

    Handles cleanup, punctuation, and formatting.
    """

    # Common filler words to optionally remove
    FILLER_WORDS = [
        "um", "uh", "er", "ah", "like", "you know",
        "basically", "actually", "literally", "so", "well",
    ]

    # Common corrections
    CORRECTIONS = {
        "gonna": "going to",
        "wanna": "want to",
        "gotta": "got to",
        "kinda": "kind of",
        "sorta": "sort of",
        "dunno": "don't know",
        "lemme": "let me",
        "gimme": "give me",
    }

    def __init__(
        self,
        remove_fillers: bool = False,
        apply_corrections: bool = True,
        capitalize_sentences: bool = True,
    ):
        """
        Initialize text processor.

        Args:
            remove_fillers: Remove filler words
            apply_corrections: Apply common corrections
            capitalize_sentences: Capitalize first letter of sentences
        """
        self.remove_fillers = remove_fillers
        self.apply_corrections = apply_corrections
        self.capitalize_sentences = capitalize_sentences

    def process(self, text: str) -> str:
        """
        Process transcribed text.

        Args:
            text: Raw transcription

        Returns:
            Processed text
        """
        if not text:
            return text

        # Basic cleanup
        text = self._clean_whitespace(text)

        # Remove fillers if enabled
        if self.remove_fillers:
            text = self._remove_filler_words(text)

        # Apply corrections if enabled
        if self.apply_corrections:
            text = self._apply_corrections(text)

        # Capitalize sentences if enabled
        if self.capitalize_sentences:
            text = self._capitalize_sentences(text)

        return text.strip()

    def _clean_whitespace(self, text: str) -> str:
        """Clean up whitespace."""
        # Remove multiple spaces
        text = re.sub(r'\s+', ' ', text)
        # Remove space before punctuation
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)
        # Add space after punctuation if missing
        text = re.sub(r'([.,!?;:])([A-Za-z])', r'\1 \2', text)
        return text.strip()

    def _remove_filler_words(self, text: str) -> str:
        """Remove filler words from text."""
        words = text.split()
        filtered = []

        for i, word in enumerate(words):
            word_lower = word.lower().strip('.,!?;:')

            # Check single filler words
            if word_lower in self.FILLER_WORDS:
                continue

            # Check multi-word fillers
            skip = False
            for filler in self.FILLER_WORDS:
                if ' ' in filler:
                    filler_words = filler.split()
                    if i + len(filler_words) <= len(words):
                        phrase = ' '.join(w.lower().strip('.,!?;:')
                                         for w in words[i:i+len(filler_words)])
                        if phrase == filler:
                            skip = True
                            break

            if not skip:
                filtered.append(word)

        return ' '.join(filtered)

    def _apply_corrections(self, text: str) -> str:
        """Apply common word corrections."""
        for wrong, correct in self.CORRECTIONS.items():
            # Case-insensitive replacement
            pattern = re.compile(re.escape(wrong), re.IGNORECASE)
            text = pattern.sub(correct, text)
        return text

    def _capitalize_sentences(self, text: str) -> str:
        """Capitalize the first letter of sentences."""
        # Split by sentence endings
        sentences = re.split(r'([.!?]+\s*)', text)

        result = []
        for i, part in enumerate(sentences):
            if i % 2 == 0 and part:  # Sentence content
                part = part[0].upper() + part[1:] if part else part
            result.append(part)

        return ''.join(result)

    def extract_question(self, text: str) -> Optional[str]:
        """
        Extract a question from the text.

        Looks for question patterns and returns the question.

        Args:
            text: Transcribed text

        Returns:
            Extracted question or None
        """
        # Look for text ending with question mark
        questions = re.findall(r'[^.!?]*\?', text)
        if questions:
            return questions[-1].strip()

        # Look for question words
        question_starters = [
            "what", "how", "why", "when", "where", "who",
            "which", "can you", "could you", "would you",
            "is there", "are there", "do you", "does",
            "tell me", "explain", "describe",
        ]

        text_lower = text.lower()
        for starter in question_starters:
            if starter in text_lower:
                # Extract from the question word to the end
                idx = text_lower.find(starter)
                return text[idx:].strip()

        # Return the whole text as a potential question
        return text if text else None

    def is_question(self, text: str) -> bool:
        """
        Check if text appears to be a question.

        Args:
            text: Text to check

        Returns:
            True if text appears to be a question
        """
        if not text:
            return False

        # Check for question mark
        if '?' in text:
            return True

        # Check for question words at the start
        question_words = [
            "what", "how", "why", "when", "where", "who", "which",
            "can", "could", "would", "should", "is", "are", "do", "does",
            "tell", "explain", "describe", "walk",
        ]

        first_word = text.split()[0].lower().strip('.,!?;:') if text.split() else ""
        return first_word in question_words


def clean_transcription(text: str) -> str:
    """
    Quick utility to clean transcription text.

    Args:
        text: Raw transcription

    Returns:
        Cleaned text
    """
    processor = TextProcessor()
    return processor.process(text)
