from __future__ import annotations

from ..models import ParsedCommand
from .rule_parser import RuleParser


class LLMParser:
    """
    Placeholder parser mode. For the MVP we keep execution deterministic and offline-safe.
    If PARSER_MODE=llm is enabled without a real implementation, we fall back to RuleParser.
    """

    mode = "llm"

    def __init__(self) -> None:
        self._fallback = RuleParser()

    def parse(self, message: str) -> ParsedCommand:
        parsed = self._fallback.parse(message)
        parsed.parser_mode = "llm_fallback_to_rule"
        parsed.notes.append("LLM parser is not configured in MVP; used RuleParser fallback.")
        return parsed
