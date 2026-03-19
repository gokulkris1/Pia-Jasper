# Pia Jasper MCP Proxy

Minimal FastAPI-based MCP server mounting the MCP streamable HTTP app and exposing a small set of proxy tools for Cisco Jasper (Control Center).

Features
- FastAPI app exposing `/mcp` (mounted MCP streamable HTTP app)
- `/health` endpoint
- `GET /cc/echo/{param}` - proxy to CC echo endpoint
- `GET /cc/devices?modifiedSince=...&accountId=...` - list devices modified since timestamp (enforces allowlist)
- `POST /cc/rate-plan/preview` - generate a confirmation preview for rate-plan changes
- `POST /cc/rate-plan/confirm` - execute a confirmed rate-plan change workflow
- Optional MCP auth via `MCP_AUTH_TOKEN`
- Optional CORS support
- JSON, CSV, and rendered table artifacts for Phase 1 operations

Phase 1 workflow

The repository now includes a confirmation-based rate-plan workflow that separates orchestration from the Jasper-specific adapter.

1. `PREVIEW_RATE_PLAN_CHANGE` resolves the identifiers, builds a before and after preview, stores a pending operation, and writes preview artifacts.
2. `CONFIRM_RATE_PLAN_CHANGE` loads the pending operation, executes the change, updates the final report, and writes result artifacts.
3. In `stub` mode the workflow uses `pia_jasper_mcp/stub_devices.sample.json` so the plumbing can be exercised without calling Jasper.
4. In `live` mode the workflow is intentionally blocked until the exact Jasper REST or SOAP rate-plan mapping is wired from the API documentation.

Local-only MCP stdio demo

1. Copy `.env.example` to `.env` and fill `CC_BASE_URL`, `CC_JASPER_BEARER` and optional `CC_ALLOWED_ACCOUNT_IDS`.
2. Install dependencies and run the MCP server locally via stdio transport:

```powershell
python -m pip install -r pia_jasper_mcp/requirements.txt
python -m pia_jasper_mcp
```

The server runs as a local MCP server using stdio. This is a demo harness and does not expose HTTP endpoints.

Agent runner

`agent_runner.py` is a tiny runner that launches the local MCP server as a subprocess and uses the MCP client SDK (stdio transport) to call tools.

Usage (example):

```powershell
# Create input file 'cmd.txt' with the following content:
JASPER_RUN
operation: ECHO
param: hello-three

# Run the agent runner (reads input from stdin):
python agent_runner.py < cmd.txt
```

Rate-plan preview example:

```powershell
JASPER_RUN
operation: PREVIEW_RATE_PLAN_CHANGE
identifiers: 8944500100000000001,15551230002
targetRatePlan: Demo-Pro-10GB
accountId: 3ie-demo
requestedBy: ggurijalaAdmin
reason: Pilot proof of plumbing
```

Confirm example:

```powershell
JASPER_RUN
operation: CONFIRM_RATE_PLAN_CHANGE
operationId: <paste operation id from preview>
confirmedBy: ggurijalaAdmin
```

The runner prints a JSON receipt with `job_id`, `timestamp`, `operation`, `tool`, `status`, and `result`.


Docker / Cloud Run

Build the image:

```bash
docker build -t gcr.io/PROJECT_ID/pia-jasper-mcp:latest .
```

Push and deploy to Cloud Run (one-line example):

```bash
gcloud run deploy pia-jasper-mcp \
  --image gcr.io/PROJECT_ID/pia-jasper-mcp:latest \
  --region=REGION \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars CC_BASE_URL=${CC_BASE_URL},CC_JASPER_BEARER='${CC_JASPER_BEARER}',CC_ALLOWED_ACCOUNT_IDS='${CC_ALLOWED_ACCOUNT_IDS}',MCP_AUTH_TOKEN='${MCP_AUTH_TOKEN}'
```

Notes
- Ensure the MCP SDK that provides `mcp.server.fastmcp` is installed in the image/environment.
- Do not commit secrets. Use Cloud Run or Secret Manager to store tokens in production.
- See `../docs/solution-architecture.md` for a business-facing architecture explanation.
