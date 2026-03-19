# Ops Executor MVP (FastAPI)

This adds a standalone MVP execution path under `mvp_ops_executor/` and does not modify the existing MCP flow.

## What it does

- Accepts telecom service requests in a simple chat UI
- Deterministically parses and validates the request
- Asks for explicit confirmation (`yes/no`)
- Executes one operation via a connector wrapper (`MockConnector` by default)
- Stores a full request timeline in SQLite (`requests` + `request_events`)
- Exposes log pages/endpoints for demo and debugging

## Implemented operations

- `SUSPEND_SIM` (required: `iccid`, optional: `reason`)
- `CHANGE_RATE_PLAN` (required: `iccid`, `rate_plan_id`, optional: `effective_date`)

## Endpoints

- `GET /` chat UI
- `POST /chat` send `{ "user": "...", "message": "..." }`
- `GET /logs` logs UI
- `GET /logs/{id}` JSON request + events
- `GET /api/logs` recent requests list (used by logs UI)
- `GET /health` health check

## Run locally

### 1) Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux (if needed):

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies

```powershell
pip install fastapi uvicorn python-dotenv
```

### 3) Configure environment

```powershell
Copy-Item .env.example .env
```

Defaults are offline-safe (`RuleParser` + `MockConnector`).

### 4) Start the app

```powershell
python -m uvicorn mvp_ops_executor.app:app --reload
```

Open `http://127.0.0.1:8000/`.

---

### Running Tests

A suite of unit and integration tests is included under the `tests/` directory. To run them:

1. Install dev dependencies:
   ```powershell
   python -m pip install -r requirements-dev.txt
   ```
2. Execute pytest:
   ```powershell
   python -m pytest tests/  # or simply `pytest` if installed globally
   ```

Tests cover parsers, connectors, and API endpoints. Ensure `pytest` is available in your Python environment before running.

For Cisco Jasper integration, set up `JASPER_BASE_URL` and `JASPER_API_TOKEN` in `.env` and add connector-specific tests.

## Demo flow (required MVP scenario)

1. In the chat page, send:
   `Suspend SIM 8944123412341234567 immediately due to non payment`
2. App responds with:
   `About to suspend SIM <iccid>. Confirm? yes/no`
3. Send:
   `yes`
4. App executes through the connector and returns `SUCCESS`/`FAILURE` with `request_id`
5. Open `/logs` and inspect the same `request_id` timeline

## Notes

- `MockConnector` is deterministic and simulates success/failure without Jasper credentials.
- `JasperConnector` is a stub with the same method signatures and clear TODO placeholders.
- `LLMParser` mode is scaffolded behind `PARSER_MODE=llm` but intentionally falls back to `RuleParser` in this MVP for offline reliability.

