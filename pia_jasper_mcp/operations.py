import csv
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _artifact_root() -> Path:
    configured = os.getenv("PIA_JASPER_ARTIFACT_DIR")
    if configured:
        return Path(configured)
    return _project_root() / ".pia_jasper"


def _pending_root() -> Path:
    return _artifact_root() / "pending"


def _reports_root() -> Path:
    return _artifact_root() / "reports"


def _stub_data_path() -> Path:
    configured = os.getenv("PIA_JASPER_STUB_DATA")
    if configured:
        return Path(configured)
    return _project_root() / "pia_jasper_mcp" / "stub_devices.sample.json"


def _max_batch() -> int:
    return int(os.getenv("PIA_JASPER_MAX_BATCH", "100"))


def _parse_identifiers(raw: str) -> List[str]:
    values = []
    for part in raw.replace("\r", "\n").replace(",", "\n").split("\n"):
        value = part.strip()
        if value:
            values.append(value)
    seen = set()
    deduped = []
    for value in values:
        if value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped


def _identifier_type(value: str) -> str:
    digits_only = value.isdigit()
    if digits_only and len(value) == 19:
        return "ICCID"
    if digits_only and len(value) >= 14:
        return "IMSI"
    if digits_only and 8 <= len(value) <= 15:
        return "MSISDN"
    return "UNKNOWN"


def _ensure_dirs() -> None:
    _pending_root().mkdir(parents=True, exist_ok=True)
    _reports_root().mkdir(parents=True, exist_ok=True)


def _pending_file(operation_id: str) -> Path:
    return _pending_root() / f"{operation_id}.json"


def _report_dir(operation_id: str) -> Path:
    return _reports_root() / operation_id


def _write_json(path: Path, payload: Dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)


def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "inputIdentifier",
        "identifierType",
        "accountId",
        "accountName",
        "iccid",
        "imsi",
        "msisdn",
        "beforeRatePlan",
        "targetRatePlan",
        "afterRatePlan",
        "previewStatus",
        "executionStatus",
        "message",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in headers})
    return str(path)


def _markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No rows"

    headers = [
        "inputIdentifier",
        "accountName",
        "beforeRatePlan",
        "targetRatePlan",
        "afterRatePlan",
        "executionStatus",
        "message",
    ]
    lines = [
        "| Identifier | Account | Before | Target | After | Status | Message |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        values = [
            row.get("inputIdentifier", ""),
            row.get("accountName", ""),
            row.get("beforeRatePlan", ""),
            row.get("targetRatePlan", ""),
            row.get("afterRatePlan", ""),
            row.get("executionStatus", row.get("previewStatus", "")),
            row.get("message", ""),
        ]
        escaped = [str(value).replace("|", "\\|") for value in values]
        lines.append(f"| {' | '.join(escaped)} |")
    return "\n".join(lines)


def _save_pending(operation_id: str, payload: Dict[str, Any]) -> None:
    _write_json(_pending_file(operation_id), payload)


def _load_pending(operation_id: str) -> Dict[str, Any]:
    path = _pending_file(operation_id)
    if not path.exists():
        raise FileNotFoundError(f"Pending operation not found: {operation_id}")
    return json.loads(path.read_text(encoding="utf-8"))


class StubJasperAdapter:
    def __init__(self, data_path: Path):
        self.data_path = data_path

    def _load_inventory(self) -> List[Dict[str, Any]]:
        return json.loads(self.data_path.read_text(encoding="utf-8"))

    def _save_inventory(self, inventory: List[Dict[str, Any]]) -> None:
        self.data_path.write_text(json.dumps(inventory, indent=2), encoding="utf-8")

    def _match_device(self, inventory: List[Dict[str, Any]], identifier: str, account_id: Optional[str]) -> Optional[Dict[str, Any]]:
        matches = []
        for device in inventory:
            if account_id and device.get("accountId") != account_id:
                continue
            if identifier in {device.get("iccid"), device.get("imsi"), device.get("msisdn")}:
                matches.append(device)
        if len(matches) == 1:
            return matches[0]
        return None

    async def preview_rate_plan_change(
        self,
        identifiers: List[str],
        target_rate_plan: str,
        account_id: Optional[str],
    ) -> Dict[str, Any]:
        inventory = self._load_inventory()
        rows = []
        ready_count = 0
        for identifier in identifiers:
            device = self._match_device(inventory, identifier, account_id)
            row = {
                "inputIdentifier": identifier,
                "identifierType": _identifier_type(identifier),
                "targetRatePlan": target_rate_plan,
                "afterRatePlan": "",
                "executionStatus": "PENDING_CONFIRMATION",
            }
            if device is None:
                row.update(
                    {
                        "previewStatus": "NOT_FOUND",
                        "executionStatus": "SKIPPED",
                        "message": "No unique device found in stub inventory for the given identifier/account.",
                    }
                )
            else:
                ready_count += 1
                row.update(
                    {
                        "previewStatus": "READY",
                        "accountId": device.get("accountId", ""),
                        "accountName": device.get("accountName", ""),
                        "iccid": device.get("iccid", ""),
                        "imsi": device.get("imsi", ""),
                        "msisdn": device.get("msisdn", ""),
                        "beforeRatePlan": device.get("ratePlan", ""),
                        "message": "Ready for confirmation.",
                    }
                )
            rows.append(row)

        return {
            "adapterMode": "stub",
            "readyCount": ready_count,
            "rows": rows,
            "status": "READY_FOR_CONFIRMATION" if ready_count else "BLOCKED",
            "warnings": [
                "Stub mode is active. Jasper is not being called in this mode.",
            ],
        }

    async def execute_rate_plan_change(self, pending: Dict[str, Any], confirmed_by: str) -> Dict[str, Any]:
        inventory = self._load_inventory()
        by_iccid = {device.get("iccid"): device for device in inventory}
        executed_rows = []
        success_count = 0
        failure_count = 0

        for row in pending.get("rows", []):
            row_copy = dict(row)
            row_copy["confirmedBy"] = confirmed_by
            if row.get("previewStatus") != "READY":
                row_copy["executionStatus"] = "SKIPPED"
                executed_rows.append(row_copy)
                failure_count += 1
                continue

            device = by_iccid.get(row.get("iccid"))
            if not device:
                row_copy["executionStatus"] = "FAILED"
                row_copy["message"] = "Device disappeared from stub inventory before execution."
                executed_rows.append(row_copy)
                failure_count += 1
                continue

            device["ratePlan"] = pending["targetRatePlan"]
            row_copy["afterRatePlan"] = pending["targetRatePlan"]
            row_copy["executionStatus"] = "SUCCESS"
            row_copy["message"] = "Stub rate plan updated successfully."
            executed_rows.append(row_copy)
            success_count += 1

        self._save_inventory(inventory)

        return {
            "adapterMode": "stub",
            "rows": executed_rows,
            "successCount": success_count,
            "failureCount": failure_count,
            "status": "COMPLETED" if success_count else "FAILED",
            "warnings": [
                "Stub mode is active. Jasper is not being called in this mode.",
            ],
        }


class LiveJasperAdapter:
    async def preview_rate_plan_change(
        self,
        identifiers: List[str],
        target_rate_plan: str,
        account_id: Optional[str],
    ) -> Dict[str, Any]:
        rows = []
        for identifier in identifiers:
            rows.append(
                {
                    "inputIdentifier": identifier,
                    "identifierType": _identifier_type(identifier),
                    "targetRatePlan": target_rate_plan,
                    "previewStatus": "UNCONFIGURED",
                    "executionStatus": "SKIPPED",
                    "message": "Live Jasper rate-plan mapping is not implemented yet. Wire the exact REST or SOAP operation from the Jasper API guide.",
                    "accountId": account_id or "",
                    "accountName": "",
                    "beforeRatePlan": "",
                    "afterRatePlan": "",
                }
            )

        return {
            "adapterMode": "live",
            "readyCount": 0,
            "rows": rows,
            "status": "CONFIGURATION_REQUIRED",
            "warnings": [
                "Live mode is selected, but the Jasper rate-plan adapter still needs the exact API mapping from the uploaded documentation.",
            ],
        }

    async def execute_rate_plan_change(self, pending: Dict[str, Any], confirmed_by: str) -> Dict[str, Any]:
        rows = []
        for row in pending.get("rows", []):
            row_copy = dict(row)
            row_copy["confirmedBy"] = confirmed_by
            row_copy["executionStatus"] = "SKIPPED"
            row_copy["message"] = "Execution blocked because live Jasper rate-plan mapping is not implemented yet."
            rows.append(row_copy)

        return {
            "adapterMode": "live",
            "rows": rows,
            "successCount": 0,
            "failureCount": len(rows),
            "status": "CONFIGURATION_REQUIRED",
            "warnings": [
                "Live mode is selected, but the Jasper rate-plan adapter still needs the exact API mapping from the uploaded documentation.",
            ],
        }


def _adapter() -> Any:
    mode = os.getenv("PIA_JASPER_MODE", "live").strip().lower()
    if mode == "stub":
        return StubJasperAdapter(_stub_data_path())
    return LiveJasperAdapter()


async def preview_rate_plan_change(
    identifiers: str,
    targetRatePlan: str,
    accountId: Optional[str] = None,
    requestedBy: Optional[str] = None,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    _ensure_dirs()
    parsed_identifiers = _parse_identifiers(identifiers)
    if not parsed_identifiers:
        return {
            "status": "BLOCKED",
            "message": "At least one IMSI, ICCID, or MSISDN is required.",
            "rows": [],
        }

    if len(parsed_identifiers) > _max_batch():
        return {
            "status": "BLOCKED",
            "message": f"Batch size {len(parsed_identifiers)} exceeds the configured limit of {_max_batch()}.",
            "rows": [],
        }

    operation_id = str(uuid.uuid4())
    adapter = _adapter()
    preview = await adapter.preview_rate_plan_change(parsed_identifiers, targetRatePlan, accountId)

    pending = {
        "operationId": operation_id,
        "operationType": "RATE_PLAN_CHANGE",
        "createdAt": _utc_now(),
        "requestedBy": requestedBy or "unknown",
        "reason": reason or "",
        "accountId": accountId or "",
        "targetRatePlan": targetRatePlan,
        "identifiers": parsed_identifiers,
        "adapterMode": preview.get("adapterMode", "unknown"),
        "status": preview.get("status", "UNKNOWN"),
        "rows": preview.get("rows", []),
        "warnings": preview.get("warnings", []),
        "confirmationRequired": True,
    }
    _save_pending(operation_id, pending)

    preview_report_dir = _report_dir(operation_id)
    preview_json = _write_json(preview_report_dir / "preview.json", pending)
    preview_csv = _write_csv(preview_report_dir / "preview.csv", pending["rows"])

    return {
        **pending,
        "message": "Preview generated. Confirmation is required before execution." if pending["status"] == "READY_FOR_CONFIRMATION" else "Preview generated, but execution is currently blocked.",
        "table": _markdown_table(pending["rows"]),
        "artifacts": {
            "previewJson": preview_json,
            "previewCsv": preview_csv,
            "pendingOperation": str(_pending_file(operation_id)),
        },
    }


async def confirm_rate_plan_change(operationId: str, confirmedBy: str) -> Dict[str, Any]:
    _ensure_dirs()
    pending = _load_pending(operationId)
    adapter = _adapter()
    execution = await adapter.execute_rate_plan_change(pending, confirmedBy)

    completed = {
        **pending,
        "status": execution.get("status", "UNKNOWN"),
        "confirmedAt": _utc_now(),
        "confirmedBy": confirmedBy,
        "rows": execution.get("rows", []),
        "warnings": execution.get("warnings", []),
        "successCount": execution.get("successCount", 0),
        "failureCount": execution.get("failureCount", 0),
    }
    _save_pending(operationId, completed)

    report_dir = _report_dir(operationId)
    result_json = _write_json(report_dir / "result.json", completed)
    result_csv = _write_csv(report_dir / "result.csv", completed["rows"])

    return {
        **completed,
        "table": _markdown_table(completed["rows"]),
        "artifacts": {
            "resultJson": result_json,
            "resultCsv": result_csv,
            "pendingOperation": str(_pending_file(operationId)),
        },
    }