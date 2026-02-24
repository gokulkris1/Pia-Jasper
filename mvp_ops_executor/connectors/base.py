from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ConnectorResult:
    success: bool
    operation: str
    data: Dict[str, Any] = field(default_factory=dict)
    external_request_id: Optional[str] = None
    error_code: Optional[str] = None
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        return {k: v for k, v in payload.items() if v is not None}


class BaseConnector(ABC):
    @abstractmethod
    def suspend_sim(self, *, iccid: str, reason: Optional[str], request_id: str) -> ConnectorResult:
        raise NotImplementedError

    @abstractmethod
    def change_rate_plan(
        self,
        *,
        iccid: str,
        rate_plan_id: str,
        effective_date: Optional[str],
        request_id: str,
    ) -> ConnectorResult:
        raise NotImplementedError

