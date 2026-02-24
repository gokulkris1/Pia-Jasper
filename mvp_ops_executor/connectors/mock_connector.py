from __future__ import annotations

import uuid
from typing import Optional

from .base import BaseConnector, ConnectorResult


class MockConnector(BaseConnector):
    """Deterministic Jasper-like responses for local demos."""

    name = "mock"

    def suspend_sim(self, *, iccid: str, reason: Optional[str], request_id: str) -> ConnectorResult:
        if iccid.endswith("0000"):
            return ConnectorResult(
                success=False,
                operation="SUSPEND_SIM",
                error_code="DEVICE_NOT_FOUND",
                reason=f"SIM with ICCID {iccid} was not found",
                data={"connector": self.name, "mock": True},
                external_request_id=self._external_id("suspend", request_id),
            )
        if iccid.endswith("9999"):
            return ConnectorResult(
                success=False,
                operation="SUSPEND_SIM",
                error_code="UPSTREAM_TIMEOUT",
                reason="Mock Jasper timeout while suspending SIM",
                data={"connector": self.name, "mock": True},
                external_request_id=self._external_id("suspend", request_id),
            )

        return ConnectorResult(
            success=True,
            operation="SUSPEND_SIM",
            data={
                "connector": self.name,
                "mock": True,
                "iccid": iccid,
                "new_status": "SUSPENDED",
                "reason": reason,
            },
            external_request_id=self._external_id("suspend", request_id),
        )

    def change_rate_plan(
        self,
        *,
        iccid: str,
        rate_plan_id: str,
        effective_date: Optional[str],
        request_id: str,
    ) -> ConnectorResult:
        bad_rate_plans = {"BAD", "INVALID", "UNKNOWN"}
        if rate_plan_id.upper() in bad_rate_plans or rate_plan_id.upper().startswith("BAD_"):
            return ConnectorResult(
                success=False,
                operation="CHANGE_RATE_PLAN",
                error_code="INVALID_RATE_PLAN",
                reason=f"Rate plan {rate_plan_id} is not valid",
                data={"connector": self.name, "mock": True, "iccid": iccid},
                external_request_id=self._external_id("rateplan", request_id),
            )

        if iccid.endswith("0000"):
            return ConnectorResult(
                success=False,
                operation="CHANGE_RATE_PLAN",
                error_code="DEVICE_NOT_FOUND",
                reason=f"SIM with ICCID {iccid} was not found",
                data={"connector": self.name, "mock": True},
                external_request_id=self._external_id("rateplan", request_id),
            )

        return ConnectorResult(
            success=True,
            operation="CHANGE_RATE_PLAN",
            data={
                "connector": self.name,
                "mock": True,
                "iccid": iccid,
                "rate_plan_id": rate_plan_id,
                "effective_date": effective_date,
            },
            external_request_id=self._external_id("rateplan", request_id),
        )

    def _external_id(self, namespace: str, request_id: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"mock://{namespace}/{request_id}"))

