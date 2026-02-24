from __future__ import annotations

from .llm_parser import LLMParser
from .rule_parser import RuleParser


def build_parser(mode: str = "rule"):
    normalized = (mode or "rule").strip().lower()
    if normalized == "llm":
        return LLMParser()
    return RuleParser()

