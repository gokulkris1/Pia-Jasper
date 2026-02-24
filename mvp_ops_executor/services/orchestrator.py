from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from ..models import (
    ChatOutcome,
    OP_CHANGE_RATE_PLAN,
    OP_SUSPEND_SIM,
    STATUS_CANCELLED,
    STATUS_EXECUTED_FAILED,
    STATUS_EXECUTED_SUCCESS,
    STATUS_NEEDS_CONFIRMATION,
    STATUS_RECEIVED,
    STAGE_CONFIRMATION_RECEIVED,
    STAGE_CONFIRMATION_REQUESTED,
    STAGE_EXECUTION_RESULT,
    STAGE_EXECUTION_STARTED,
    STAGE_MISSING_FIELDS_REQUESTED,
    STAGE_PARSED,
    STAGE_VALIDATED,
)
from ..storage import SQLiteStorage
from ..validators import build_missing_field_question, extract_missing_field_value, validate_parsed_command
from .operations import execute_operation


YES_WORDS = {"yes", "y", "confirm", "ok", "okay"}
NO_WORDS = {"no", "n", "cancel", "stop"}


class OpsOrchestrator:
    def __init__(self, storage: SQLiteStorage, parser: Any, connector: Any) -> None:
        self.storage = storage
        self.parser = parser
        self.connector = connector
        self.logger = logging.getLogger("mvp_ops_executor.orchestrator")

    def handle_chat(self, user: str, message: str) -> Dict[str, Any]:
        user = (user or "demo-user").strip() or "demo-user"
        message = (message or "").strip()

        if not message:
            return ChatOutcome(
                request_id=self.storage.new_request_id(),
                reply="Please enter a request message.",
                status="INVALID_INPUT",
                error_code="EMPTY_MESSAGE",
                reason="message is empty",
            ).to_dict()

        pending_confirmation = self.storage.find_latest_request_by_user(user, [STATUS_NEEDS_CONFIRMATION])
        if pending_confirmation and self._is_yes_no(message):
            return self._handle_confirmation_reply(pending_confirmation, message).to_dict()

        pending_missing = self.storage.find_latest_request_by_user(user, [STATUS_RECEIVED])
        if pending_missing:
            follow_up = self._handle_missing_fields_followup(pending_missing, message)
            if follow_up is not None:
                return follow_up.to_dict()

        return self._handle_new_request(user=user, message=message).to_dict()

    def _handle_new_request(self, *, user: str, message: str) -> ChatOutcome:
        request_id = self.storage.new_request_id()
        parsed = self.parser.parse(message)
        parsed_dict = parsed.to_dict()

        state = {
            "operation": parsed.operation,
            "fields": parsed.fields,
            "normalized_fields": {},
            "missing_fields": [],
            "validation_errors": [],
            "parser_mode": parsed.parser_mode,
            "notes": parsed.notes,
        }

        self.storage.create_request(
            request_id=request_id,
            user=user,
            raw_message=message,
            parsed_json=json.dumps(state, sort_keys=True),
            status=STATUS_RECEIVED,
            operation=parsed.operation,
        )
        self.storage.append_event(
            request_id,
            STAGE_PARSED,
            {"raw_message": message, "parsed": parsed_dict, "parser_mode": parsed.parser_mode},
        )
        self._log("request_parsed", request_id=request_id, user=user, parsed=parsed_dict)

        validation = validate_parsed_command(parsed.operation, parsed.fields)
        self.storage.append_event(request_id, STAGE_VALIDATED, validation.to_dict())

        state.update(
            {
                "operation": validation.normalized_operation,
                "normalized_fields": validation.normalized_fields,
                "missing_fields": validation.missing_fields,
                "validation_errors": validation.errors,
            }
        )

        if not validation.normalized_operation or (
            validation.errors and any(e.get("error_code") == "UNSUPPORTED_OPERATION" for e in validation.errors)
        ):
            self.storage.update_request(
                request_id,
                parsed_json=json.dumps(state, sort_keys=True),
                status=STATUS_RECEIVED,
                operation=validation.normalized_operation,
            )
            return ChatOutcome(
                request_id=request_id,
                reply="Supported operations: suspend SIM or change rate plan. Please rephrase your request.",
                status=STATUS_RECEIVED,
                error_code="UNKNOWN_OR_UNSUPPORTED_OPERATION",
                reason="Could not determine a supported operation",
            )

        if validation.errors and not validation.missing_fields:
            self.storage.update_request(
                request_id,
                parsed_json=json.dumps(state, sort_keys=True),
                status=STATUS_RECEIVED,
                operation=validation.normalized_operation,
            )
            first_error = validation.errors[0]
            reply = first_error.get("reason", "Validation failed")
            return ChatOutcome(
                request_id=request_id,
                reply=reply,
                status=STATUS_RECEIVED,
                operation=validation.normalized_operation,
                error_code=first_error.get("error_code"),
                reason=reply,
            )

        if validation.missing_fields:
            missing_field = validation.missing_fields[0]
            reply = build_missing_field_question(validation.normalized_operation, missing_field)
            self.storage.update_request(
                request_id,
                parsed_json=json.dumps(state, sort_keys=True),
                status=STATUS_RECEIVED,
                operation=validation.normalized_operation,
            )
            self.storage.append_event(
                request_id,
                STAGE_MISSING_FIELDS_REQUESTED,
                {"missing_field": missing_field, "question": reply},
            )
            return ChatOutcome(
                request_id=request_id,
                reply=reply,
                status=STATUS_RECEIVED,
                operation=validation.normalized_operation,
            )

        self.storage.update_request(
            request_id,
            parsed_json=json.dumps(state, sort_keys=True),
            status=STATUS_NEEDS_CONFIRMATION,
            operation=validation.normalized_operation,
        )
        reply = self._confirmation_prompt(validation.normalized_operation, validation.normalized_fields)
        self.storage.append_event(request_id, STAGE_CONFIRMATION_REQUESTED, {"prompt": reply})
        return ChatOutcome(
            request_id=request_id,
            reply=reply,
            status=STATUS_NEEDS_CONFIRMATION,
            operation=validation.normalized_operation,
        )

    def _handle_missing_fields_followup(
        self, request_record: Dict[str, Any], message: str
    ) -> Optional[ChatOutcome]:
        state = self._load_state(request_record)
        if not state:
            return None

        missing_fields = state.get("missing_fields") or []
        operation = state.get("operation")
        if not operation or not missing_fields:
            return None

        request_id = str(request_record["id"])
        target_field = str(missing_fields[0])
        extracted_value = extract_missing_field_value(operation, target_field, message)

        if extracted_value is None:
            reply = build_missing_field_question(operation, target_field)
            self.storage.append_event(
                request_id,
                STAGE_MISSING_FIELDS_REQUESTED,
                {"missing_field": target_field, "question": reply, "followup_message": message},
            )
            return ChatOutcome(
                request_id=request_id,
                reply=reply,
                status=str(request_record["status"]),
                operation=str(operation),
                error_code="MISSING_FIELD_VALUE",
                reason=f"Could not parse value for {target_field}",
            )

        merged_fields = dict(state.get("normalized_fields") or {})
        merged_fields[target_field] = extracted_value
        self.storage.append_event(
            request_id,
            STAGE_PARSED,
            {"followup_message": message, "parsed_field": {target_field: extracted_value}},
        )

        validation = validate_parsed_command(str(operation), merged_fields)
        self.storage.append_event(request_id, STAGE_VALIDATED, validation.to_dict())

        state.update(
            {
                "fields": {**(state.get("fields") or {}), target_field: extracted_value},
                "normalized_fields": validation.normalized_fields,
                "missing_fields": validation.missing_fields,
                "validation_errors": validation.errors,
                "operation": validation.normalized_operation,
            }
        )

        if validation.errors and not validation.missing_fields:
            self.storage.update_request(
                request_id,
                parsed_json=json.dumps(state, sort_keys=True),
                status=STATUS_RECEIVED,
                operation=validation.normalized_operation,
            )
            first_error = validation.errors[0]
            return ChatOutcome(
                request_id=request_id,
                reply=first_error.get("reason", "Validation failed"),
                status=STATUS_RECEIVED,
                operation=validation.normalized_operation,
                error_code=first_error.get("error_code"),
                reason=first_error.get("reason"),
            )

        if validation.missing_fields:
            next_missing = validation.missing_fields[0]
            reply = build_missing_field_question(validation.normalized_operation, next_missing)
            self.storage.update_request(
                request_id,
                parsed_json=json.dumps(state, sort_keys=True),
                status=STATUS_RECEIVED,
                operation=validation.normalized_operation,
            )
            self.storage.append_event(
                request_id,
                STAGE_MISSING_FIELDS_REQUESTED,
                {"missing_field": next_missing, "question": reply},
            )
            return ChatOutcome(
                request_id=request_id,
                reply=reply,
                status=STATUS_RECEIVED,
                operation=validation.normalized_operation,
            )

        reply = self._confirmation_prompt(validation.normalized_operation, validation.normalized_fields)
        self.storage.update_request(
            request_id,
            parsed_json=json.dumps(state, sort_keys=True),
            status=STATUS_NEEDS_CONFIRMATION,
            operation=validation.normalized_operation,
        )
        self.storage.append_event(request_id, STAGE_CONFIRMATION_REQUESTED, {"prompt": reply})
        return ChatOutcome(
            request_id=request_id,
            reply=reply,
            status=STATUS_NEEDS_CONFIRMATION,
            operation=validation.normalized_operation,
        )

    def _handle_confirmation_reply(self, request_record: Dict[str, Any], message: str) -> ChatOutcome:
        request_id = str(request_record["id"])
        decision = self._normalize_yes_no(message)
        self.storage.append_event(
            request_id,
            STAGE_CONFIRMATION_RECEIVED,
            {"message": message, "decision": decision},
        )

        if decision == "no":
            self.storage.update_request(request_id, status=STATUS_CANCELLED)
            return ChatOutcome(
                request_id=request_id,
                reply=f"Cancelled request {request_id}.",
                status=STATUS_CANCELLED,
                operation=request_record.get("operation"),
            )

        state = self._load_state(request_record)
        if not state:
            self.storage.update_request(request_id, status=STATUS_EXECUTED_FAILED)
            self.storage.append_event(
                request_id,
                STAGE_EXECUTION_RESULT,
                {
                    "success": False,
                    "error_code": "INVALID_STATE",
                    "reason": "Missing parsed state before execution",
                },
            )
            return ChatOutcome(
                request_id=request_id,
                reply=f"FAILURE: invalid request state. request_id={request_id}",
                status=STATUS_EXECUTED_FAILED,
                error_code="INVALID_STATE",
                reason="Missing parsed state before execution",
            )

        operation = state.get("operation")
        fields = state.get("normalized_fields") or {}
        if not operation:
            self.storage.update_request(request_id, status=STATUS_EXECUTED_FAILED)
            return ChatOutcome(
                request_id=request_id,
                reply=f"FAILURE: missing operation. request_id={request_id}",
                status=STATUS_EXECUTED_FAILED,
                error_code="INVALID_STATE",
                reason="No operation in request state",
            )

        self.storage.append_event(request_id, STAGE_EXECUTION_STARTED, {"operation": operation, "fields": fields})
        self._log("execution_started", request_id=request_id, operation=operation, fields=fields)

        try:
            connector_result = execute_operation(self.connector, str(operation), fields, request_id)
        except Exception as exc:
            self.storage.update_request(request_id, status=STATUS_EXECUTED_FAILED)
            payload = {
                "success": False,
                "error_code": "EXECUTION_EXCEPTION",
                "reason": str(exc),
            }
            self.storage.append_event(request_id, STAGE_EXECUTION_RESULT, payload)
            self._log("execution_exception", request_id=request_id, error=str(exc))
            return ChatOutcome(
                request_id=request_id,
                reply=f"FAILURE: {exc}. request_id={request_id}",
                status=STATUS_EXECUTED_FAILED,
                operation=str(operation),
                error_code="EXECUTION_EXCEPTION",
                reason=str(exc),
            )

        self.storage.append_event(request_id, STAGE_EXECUTION_RESULT, connector_result.to_dict())

        if connector_result.success:
            self.storage.update_request(request_id, status=STATUS_EXECUTED_SUCCESS)
            self._log(
                "execution_success",
                request_id=request_id,
                operation=operation,
                connector_result=connector_result.to_dict(),
            )
            return ChatOutcome(
                request_id=request_id,
                reply=f"SUCCESS: {operation} completed. request_id={request_id}",
                status=STATUS_EXECUTED_SUCCESS,
                operation=str(operation),
            )

        self.storage.update_request(request_id, status=STATUS_EXECUTED_FAILED)
        self._log(
            "execution_failed",
            request_id=request_id,
            operation=operation,
            connector_result=connector_result.to_dict(),
        )
        human_reason = connector_result.reason or "Execution failed"
        return ChatOutcome(
            request_id=request_id,
            reply=f"FAILURE: {human_reason}. request_id={request_id}",
            status=STATUS_EXECUTED_FAILED,
            operation=str(operation),
            error_code=connector_result.error_code or "EXECUTION_FAILED",
            reason=human_reason,
        )

    def _confirmation_prompt(self, operation: Optional[str], fields: Dict[str, Any]) -> str:
        iccid = fields.get("iccid", "<unknown>")
        if operation == OP_SUSPEND_SIM:
            return f"About to suspend SIM {iccid}. Confirm? yes/no"
        if operation == OP_CHANGE_RATE_PLAN:
            plan = fields.get("rate_plan_id", "<unknown>")
            return f"About to change rate plan on SIM {iccid} to {plan}. Confirm? yes/no"
        return f"Confirm operation {operation} on ICCID {iccid}? yes/no"

    def _load_state(self, request_record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raw = request_record.get("parsed_json")
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except Exception:
            return None
        return data if isinstance(data, dict) else None

    def _is_yes_no(self, message: str) -> bool:
        return self._normalize_yes_no(message) is not None

    def _normalize_yes_no(self, message: str) -> Optional[str]:
        normalized = (message or "").strip().lower()
        if normalized in YES_WORDS:
            return "yes"
        if normalized in NO_WORDS:
            return "no"
        return None

    def _log(self, event: str, **payload: Any) -> None:
        try:
            self.logger.info(json.dumps({"event": event, **payload}, sort_keys=True, default=str))
        except Exception:
            self.logger.info("event=%s payload=%s", event, payload)
