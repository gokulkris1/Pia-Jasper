from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, Optional

from .models import OP_CHANGE_RATE_PLAN, OP_SUSPEND_SIM, SUPPORTED_OPERATIONS, ValidationResult


REQUIRED_FIELDS = {
    OP_SUSPEND_SIM: ["iccid"],
    OP_CHANGE_RATE_PLAN: ["iccid", "rate_plan_id"],
}

ICCID_RE = re.compile(r"\b(\d{10,22})\b")
DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
RATE_PLAN_RE = re.compile(r"\b([A-Za-z0-9_-]{2,64})\b")


def validate_parsed_command(operation: Optional[str], fields: Dict[str, Any]) -> ValidationResult:
    errors = []
    normalized_fields: Dict[str, Any] = {}
    normalized_operation = operation.upper() if operation else None

    if not normalized_operation:
        return ValidationResult(
            is_valid=False,
            normalized_operation=None,
            normalized_fields={},
            missing_fields=["operation"],
            errors=[{"error_code": "UNKNOWN_OPERATION", "reason": "No supported operation detected"}],
        )

    if normalized_operation not in SUPPORTED_OPERATIONS:
        return ValidationResult(
            is_valid=False,
            normalized_operation=normalized_operation,
            normalized_fields={},
            missing_fields=[],
            errors=[
                {
                    "error_code": "UNSUPPORTED_OPERATION",
                    "reason": f"Unsupported operation: {normalized_operation}",
                }
            ],
        )

    raw_iccid = fields.get("iccid")
    if raw_iccid is not None:
        digits = re.sub(r"\D", "", str(raw_iccid))
        if not digits:
            errors.append({"error_code": "INVALID_ICCID", "reason": "ICCID must contain digits"})
        elif not re.fullmatch(r"\d{10,22}", digits):
            errors.append({"error_code": "INVALID_ICCID", "reason": "ICCID must be 10-22 digits"})
        else:
            normalized_fields["iccid"] = digits

    if "reason" in fields and fields.get("reason") is not None:
        reason = str(fields.get("reason")).strip()
        if reason:
            normalized_fields["reason"] = reason[:255]

    if normalized_operation == OP_CHANGE_RATE_PLAN:
        raw_rate_plan_id = fields.get("rate_plan_id")
        if raw_rate_plan_id is not None:
            rate_plan_id = str(raw_rate_plan_id).strip()
            if not rate_plan_id:
                errors.append({"error_code": "INVALID_RATE_PLAN_ID", "reason": "rate_plan_id is empty"})
            else:
                normalized_fields["rate_plan_id"] = rate_plan_id

        raw_effective_date = fields.get("effective_date")
        if raw_effective_date:
            raw_effective_date = str(raw_effective_date).strip()
            try:
                date.fromisoformat(raw_effective_date)
            except ValueError:
                errors.append(
                    {
                        "error_code": "INVALID_EFFECTIVE_DATE",
                        "reason": "effective_date must be YYYY-MM-DD",
                    }
                )
            else:
                normalized_fields["effective_date"] = raw_effective_date

    missing_fields = [
        required for required in REQUIRED_FIELDS.get(normalized_operation, []) if required not in normalized_fields
    ]
    is_valid = not missing_fields and not errors

    return ValidationResult(
        is_valid=is_valid,
        normalized_operation=normalized_operation,
        normalized_fields=normalized_fields,
        missing_fields=missing_fields,
        errors=errors,
    )


def build_missing_field_question(operation: Optional[str], missing_field: str) -> str:
    if missing_field == "operation":
        return "Which operation do you want: suspend SIM or change rate plan?"
    if missing_field == "iccid":
        if operation == OP_SUSPEND_SIM:
            return "What is the ICCID for the SIM to suspend?"
        if operation == OP_CHANGE_RATE_PLAN:
            return "What is the ICCID for the SIM whose rate plan should change?"
        return "What is the ICCID?"
    if missing_field == "rate_plan_id":
        return "What is the target rate_plan_id?"
    if missing_field == "effective_date":
        return "What is the effective date (YYYY-MM-DD)?"
    return f"Please provide {missing_field}."


def extract_missing_field_value(operation: Optional[str], field_name: str, message: str) -> Optional[Any]:
    text = (message or "").strip()
    if not text:
        return None

    if field_name == "iccid":
        match = ICCID_RE.search(text)
        return match.group(1) if match else None

    if field_name == "rate_plan_id":
        if operation == OP_CHANGE_RATE_PLAN:
            labeled = re.search(
                r"\brate\s*plan(?:\s*id)?\s*(?:to|=|:)?\s*([A-Za-z0-9_-]+)\b",
                text,
                flags=re.IGNORECASE,
            )
            if labeled:
                return labeled.group(1)
        token_match = RATE_PLAN_RE.search(text)
        return token_match.group(1) if token_match else None

    if field_name == "effective_date":
        match = DATE_RE.search(text)
        return match.group(1) if match else None

    if field_name == "reason":
        return text

    return None

