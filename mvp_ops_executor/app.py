from __future__ import annotations

import html
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency
    load_dotenv = None

from .connectors.jasper_connector import JasperConnector
from .connectors.mock_connector import MockConnector
from .parser import build_parser
from .services.orchestrator import OpsOrchestrator
from .storage import SQLiteStorage


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
DEFAULT_DB_PATH = str(BASE_DIR / "mvp_ops_executor.db")


def _configure_logging() -> None:
    if logging.getLogger().handlers:
        return
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def _maybe_load_env() -> None:
    if load_dotenv is not None:
        load_dotenv()


def _select_connector() -> Any:
    mode = os.getenv("CONNECTOR_MODE", "mock").strip().lower()
    jasper_configured = bool(os.getenv("JASPER_BASE_URL")) and bool(os.getenv("JASPER_API_TOKEN"))

    if mode == "jasper":
        return JasperConnector()
    if mode == "auto":
        return JasperConnector() if jasper_configured else MockConnector()
    return MockConnector()


def _safe_json_loads(raw: Optional[str]) -> Any:
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return raw


def _read_template(name: str) -> str:
    path = TEMPLATES_DIR / name
    return path.read_text(encoding="utf-8")


class ChatRequest(BaseModel):
    user: str = "demo-user"
    message: str


_configure_logging()
_maybe_load_env()
logger = logging.getLogger("mvp_ops_executor.app")

storage = SQLiteStorage(os.getenv("MVP_DB_PATH", DEFAULT_DB_PATH))
parser = build_parser(os.getenv("PARSER_MODE", "rule"))
connector = _select_connector()
orchestrator = OpsOrchestrator(storage=storage, parser=parser, connector=connector)

app = FastAPI(title="Ops Executor MVP", version="0.1.0")


@app.on_event("startup")
def startup() -> None:
    storage.init_db()
    logger.info(
        json.dumps(
            {
                "event": "startup",
                "parser_mode": os.getenv("PARSER_MODE", "rule"),
                "connector_type": connector.__class__.__name__,
                "db_path": storage.db_path,
            },
            sort_keys=True,
        )
    )


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index_page() -> HTMLResponse:
    return HTMLResponse(_read_template("index.html"))


@app.post("/chat")
def chat(payload: ChatRequest) -> JSONResponse:
    result = orchestrator.handle_chat(user=payload.user, message=payload.message)
    logger.info(json.dumps({"event": "chat", "user": payload.user, **result}, sort_keys=True, default=str))
    return JSONResponse(result)


@app.get("/logs", response_class=HTMLResponse)
def logs_page() -> HTMLResponse:
    return HTMLResponse(_read_template("logs.html"))


@app.get("/api/logs")
def api_logs(limit: int = 50) -> Dict[str, Any]:
    rows = storage.list_requests(limit=max(1, min(limit, 200)))
    items = []
    for row in rows:
        items.append(
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "updated_at": row.get("updated_at"),
                "user": row["user"],
                "status": row["status"],
                "operation": row.get("operation"),
                "raw_message": row["raw_message"],
            }
        )
    return {"items": items}


@app.get("/logs/{request_id}")
def log_detail(request_id: str) -> Dict[str, Any]:
    request_row = storage.get_request(request_id)
    if not request_row:
        raise HTTPException(status_code=404, detail="request not found")

    events = storage.get_events(request_id)
    decoded_events = []
    for event in events:
        decoded_events.append(
            {
                "id": event["id"],
                "request_id": event["request_id"],
                "ts": event["ts"],
                "stage": event["stage"],
                "payload_json": _safe_json_loads(event["payload_json"]),
            }
        )

    return {
        "request": {
            **request_row,
            "parsed_json": _safe_json_loads(request_row.get("parsed_json")),
        },
        "events": decoded_events,
    }


@app.get("/logs/{request_id}/view", response_class=HTMLResponse)
def log_detail_html(request_id: str) -> HTMLResponse:
    detail = log_detail(request_id)
    escaped = html.escape(json.dumps(detail, indent=2, sort_keys=True, default=str))
    body = f"""
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8" />
        <title>Request {html.escape(request_id)}</title>
        <style>
          body {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; margin: 20px; background: #f7f7f2; }}
          a {{ color: #0a5; }}
          pre {{ background: white; border: 1px solid #ddd; padding: 16px; overflow: auto; }}
        </style>
      </head>
      <body>
        <p><a href="/logs">Back to logs</a></p>
        <h2>Request {html.escape(request_id)}</h2>
        <pre>{escaped}</pre>
      </body>
    </html>
    """
    return HTMLResponse(body)

