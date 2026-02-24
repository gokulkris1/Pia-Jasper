from __future__ import annotations

import os
from typing import Optional

from .base import BaseConnector, ConnectorResult


class JasperConnector(BaseConnector):
    """
    Jasper connector stub for future integration.
    Keep method signatures identical to MockConnector so the orchestrator can swap connectors transparently.
    """

    name = "jasper"

    def __init__(self) -> None:
        self.base_url = os.getenv("JASPER_BASE_URL", "").strip()
        self.api_token = os.getenv("JASPER_API_TOKEN", "").strip()

    def suspend_sim(self, *, iccid: str, reason: Optional[str], request_id: str) -> ConnectorResult:
        return ConnectorResult(
            success=False,
            operation="SUSPEND_SIM",
            error_code="JASPER_NOT_IMPLEMENTED",
            reason="JasperConnector.suspend_sim is a stub. Add Jasper API call wrapper here.",
            data={
                "connector": self.name,
                "base_url_configured": bool(self.base_url),
                "api_token_configured": bool(self.api_token),
                "iccid": iccid,
                "reason": reason,
                "request_id": request_id,
                "todo": "Implement deterministic Jasper wrapper call and response normalization.",
            },
        )

    def change_rate_plan(
        self,
        *,
        iccid: str,
        rate_plan_id: str,
        effective_date: Optional[str],
        request_id: str,
    ) -> ConnectorResult:
        return ConnectorResult(
            success=False,
            operation="CHANGE_RATE_PLAN",
            error_code="JASPER_NOT_IMPLEMENTED",
            reason="JasperConnector.change_rate_plan is a stub. Add Jasper API call wrapper here.",
            data={
                "connector": self.name,
                "base_url_configured": bool(self.base_url),
                "api_token_configured": bool(self.api_token),
                "iccid": iccid,
                "rate_plan_id": rate_plan_id,
                "effective_date": effective_date,
                "request_id": request_id,
                "todo": "Implement deterministic Jasper wrapper call and response normalization.",
            },
        )
