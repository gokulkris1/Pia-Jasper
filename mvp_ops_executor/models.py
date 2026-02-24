from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


STATUS_RECEIVED = "RECEIVED"
STATUS_NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"
STATUS_EXECUTED_SUCCESS = "EXECUTED_SUCCESS"
STATUS_EXECUTED_FAILED = "EXECUTED_FAILED"
STATUS_CANCELLED = "CANCELLED"

STAGE_PARSED = "PARSED"
STAGE_VALIDATED = "VALIDATED"
STAGE_MISSING_FIELDS_REQUESTED = "MISSING_FIELDS_REQUESTED"
STAGE_CONFIRMATION_REQUESTED = "CONFIRMATION_REQUESTED"
STAGE_CONFIRMATION_RECEIVED = "CONFIRMATION_RECEIVED"
STAGE_EXECUTION_STARTED = "EXECUTION_STARTED"
STAGE_EXECUTION_RESULT = "EXECUTION_RESULT"

OP_SUSPEND_SIM = "SUSPEND_SIM"
OP_CHANGE_RATE_PLAN = "CHANGE_RATE_PLAN"

SUPPORTED_OPERATIONS = {OP_SUSPEND_SIM, OP_CHANGE_RATE_PLAN}


@dataclass
class ParsedCommand:
    operation: Optional[str]
    fields: Dict[str, Any] = field(default_factory=dict)
    parser_mode: str = "rule"
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationResult:
    is_valid: bool
    normalized_operation: Optional[str]
    normalized_fields: Dict[str, Any] = field(default_factory=dict)
    missing_fields: List[str] = field(default_factory=list)
    errors: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ChatOutcome:
    request_id: str
    reply: str
    status: str
    operation: Optional[str] = None
    error_code: Optional[str] = None
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        return {k: v for k, v in payload.items() if v is not None}

