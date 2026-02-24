from __future__ import annotations

import re
from typing import Any, Dict, Optional

from ..models import OP_CHANGE_RATE_PLAN, OP_SUSPEND_SIM, ParsedCommand


ICCID_RE = re.compile(r"\b(\d{10,22})\b")
DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")


class RuleParser:
    """Deterministic parser for common telecom ops phrasing."""

    mode = "rule"

    def parse(self, message: str) -> ParsedCommand:
        text = (message or "").strip()
        lower = text.lower()
        operation = self._detect_operation(lower)
        fields: Dict[str, Any] = {}
        notes = []

        iccid = self._extract_iccid(text)
        if iccid:
            fields["iccid"] = iccid

        if operation == OP_SUSPEND_SIM:
            reason = self._extract_reason(text)
            if reason:
                fields["reason"] = reason
        elif operation == OP_CHANGE_RATE_PLAN:
            rate_plan_id = self._extract_rate_plan_id(text)
            if rate_plan_id:
                fields["rate_plan_id"] = rate_plan_id
            effective_date = self._extract_effective_date(text)
            if effective_date:
                fields["effective_date"] = effective_date

        if operation is None:
            notes.append("No supported operation detected.")

        return ParsedCommand(operation=operation, fields=fields, parser_mode=self.mode, notes=notes)

    def _detect_operation(self, lower: str) -> Optional[str]:
        if not lower:
            return None

        if "rate plan" in lower or ("change" in lower and "plan" in lower):
            return OP_CHANGE_RATE_PLAN

        suspend_terms = ("suspend", "deactivate", "disable", "bar", "block")
        if any(term in lower for term in suspend_terms) and ("sim" in lower or "iccid" in lower):
            return OP_SUSPEND_SIM
        if any(term in lower for term in suspend_terms):
            return OP_SUSPEND_SIM

        return None

    def _extract_iccid(self, text: str) -> Optional[str]:
        match = ICCID_RE.search(text)
        if not match:
            return None
        return match.group(1)

    def _extract_reason(self, text: str) -> Optional[str]:
        due_match = re.search(r"\bdue to\b\s+(.+)$", text, flags=re.IGNORECASE)
        if due_match:
            return due_match.group(1).strip(" .")
        because_match = re.search(r"\bbecause\b\s+(.+)$", text, flags=re.IGNORECASE)
        if because_match:
            return because_match.group(1).strip(" .")
        return None

    def _extract_rate_plan_id(self, text: str) -> Optional[str]:
        patterns = [
            r"\brate\s*plan(?:\s*id)?\s*(?:to|=|:)?\s*([A-Za-z0-9_-]+)\b",
            r"\bplan\s*(?:id)?\s*(?:to|=|:)?\s*([A-Za-z0-9_-]+)\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            candidate = match.group(1)
            if candidate.lower() in {"for", "on", "change", "rate"}:
                continue
            return candidate

        to_match = re.search(
            r"\bchange\b.+?\bplan\b.+?\bto\b\s+([A-Za-z0-9_-]+)\b", text, flags=re.IGNORECASE
        )
        if to_match:
            return to_match.group(1)
        return None

    def _extract_effective_date(self, text: str) -> Optional[str]:
        match = re.search(r"\beffective\b[^\d]*(20\d{2}-\d{2}-\d{2})\b", text, flags=re.IGNORECASE)
        if match:
            return match.group(1)

        on_match = re.search(r"\bon\b[^\d]*(20\d{2}-\d{2}-\d{2})\b", text, flags=re.IGNORECASE)
        if on_match:
            return on_match.group(1)

        bare = DATE_RE.search(text)
        return bare.group(1) if bare else None

