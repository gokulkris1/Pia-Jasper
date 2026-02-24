from __future__ import annotations

from typing import Any, Dict

from ..connectors.base import BaseConnector, ConnectorResult
from ..models import OP_CHANGE_RATE_PLAN, OP_SUSPEND_SIM


def execute_operation(
    connector: BaseConnector, operation: str, fields: Dict[str, Any], request_id: str
) -> ConnectorResult:
    if operation == OP_SUSPEND_SIM:
        return connector.suspend_sim(
            iccid=str(fields["iccid"]),
            reason=fields.get("reason"),
            request_id=request_id,
        )
    if operation == OP_CHANGE_RATE_PLAN:
        return connector.change_rate_plan(
            iccid=str(fields["iccid"]),
            rate_plan_id=str(fields["rate_plan_id"]),
            effective_date=fields.get("effective_date"),
            request_id=request_id,
        )
    raise ValueError(f"Unsupported operation: {operation}")
