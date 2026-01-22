"""Parse and format AI responses."""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class CodeBlock:
    """A code block extracted from response."""
    language: str
    code: str
    start_pos: int
    end_pos: int


@dataclass
class ParsedResponse:
    """Parsed AI response with extracted components."""
    raw_text: str
    text_sections: List[str]
    code_blocks: List[CodeBlock]
    has_code: bool


class ResponseParser:
    """
    Parse AI responses to extract code blocks and format text.
    """

    # Regex for code blocks
    CODE_BLOCK_PATTERN = re.compile(
        r'```(\w+)?\n(.*?)```',
        re.DOTALL
    )

    # Common language aliases
    LANGUAGE_ALIASES = {
        'py': 'python',
        'js': 'javascript',
        'ts': 'typescript',
        'rb': 'ruby',
        'rs': 'rust',
        'go': 'go',
        'cpp': 'cpp',
        'c++': 'cpp',
        'csharp': 'c_sharp',
        'c#': 'c_sharp',
    }

    def parse(self, response: str) -> ParsedResponse:
        """
        Parse an AI response.

        Args:
            response: Raw response text

        Returns:
            ParsedResponse with extracted components
        """
        code_blocks = []
        text_sections = []

        # Find all code blocks
        last_end = 0
        for match in self.CODE_BLOCK_PATTERN.finditer(response):
            # Add text before code block
            text_before = response[last_end:match.start()].strip()
            if text_before:
                text_sections.append(text_before)

            # Extract code block
            language = match.group(1) or 'text'
            language = self._normalize_language(language)
            code = match.group(2).strip()

            code_blocks.append(CodeBlock(
                language=language,
                code=code,
                start_pos=match.start(),
                end_pos=match.end(),
            ))

            last_end = match.end()

        # Add remaining text
        text_after = response[last_end:].strip()
        if text_after:
            text_sections.append(text_after)

        return ParsedResponse(
            raw_text=response,
            text_sections=text_sections,
            code_blocks=code_blocks,
            has_code=len(code_blocks) > 0,
        )

    def _normalize_language(self, language: str) -> str:
        """Normalize language name."""
        lang_lower = language.lower()
        return self.LANGUAGE_ALIASES.get(lang_lower, lang_lower)

    def extract_code_blocks(self, response: str) -> List[CodeBlock]:
        """
        Extract all code blocks from response.

        Args:
            response: Raw response text

        Returns:
            List of CodeBlock objects
        """
        return self.parse(response).code_blocks

    def get_primary_code(self, response: str) -> Optional[Tuple[str, str]]:
        """
        Get the primary (first) code block.

        Args:
            response: Raw response text

        Returns:
            Tuple of (language, code) or None
        """
        blocks = self.extract_code_blocks(response)
        if blocks:
            return (blocks[0].language, blocks[0].code)
        return None

    def format_for_display(self, response: str) -> str:
        """
        Format response for display in UI.

        Converts markdown-style formatting to plain text with
        visual indicators.

        Args:
            response: Raw response text

        Returns:
            Formatted text
        """
        text = response

        # Convert headers
        text = re.sub(r'^### (.+)$', r'>>> \1', text, flags=re.MULTILINE)
        text = re.sub(r'^## (.+)$', r'>> \1', text, flags=re.MULTILINE)
        text = re.sub(r'^# (.+)$', r'> \1', text, flags=re.MULTILINE)

        # Convert bold
        text = re.sub(r'\*\*(.+?)\*\*', r'[\1]', text)

        # Convert inline code
        text = re.sub(r'`([^`]+)`', r"'\1'", text)

        # Convert bullet points (keep as-is mostly)
        text = re.sub(r'^- ', r'• ', text, flags=re.MULTILINE)
        text = re.sub(r'^\* ', r'• ', text, flags=re.MULTILINE)

        return text

    def extract_complexity(self, response: str) -> Optional[Tuple[str, str]]:
        """
        Extract time and space complexity from response.

        Args:
            response: Raw response text

        Returns:
            Tuple of (time_complexity, space_complexity) or None
        """
        # Common patterns for complexity
        time_pattern = re.compile(
            r'[Tt]ime\s*[Cc]omplexity[:\s]*O\(([^)]+)\)',
            re.IGNORECASE
        )
        space_pattern = re.compile(
            r'[Ss]pace\s*[Cc]omplexity[:\s]*O\(([^)]+)\)',
            re.IGNORECASE
        )

        time_match = time_pattern.search(response)
        space_match = space_pattern.search(response)

        if time_match or space_match:
            time_comp = f"O({time_match.group(1)})" if time_match else "N/A"
            space_comp = f"O({space_match.group(1)})" if space_match else "N/A"
            return (time_comp, space_comp)

        return None


def parse_response(response: str) -> ParsedResponse:
    """
    Convenience function to parse a response.

    Args:
        response: Raw response text

    Returns:
        ParsedResponse object
    """
    return ResponseParser().parse(response)


def extract_code(response: str) -> List[Tuple[str, str]]:
    """
    Convenience function to extract code blocks.

    Args:
        response: Raw response text

    Returns:
        List of (language, code) tuples
    """
    blocks = ResponseParser().extract_code_blocks(response)
    return [(b.language, b.code) for b in blocks]
