# Pia Jasper MCP Proxy

Minimal FastAPI-based MCP server mounting the MCP streamable HTTP app and exposing a small set of proxy tools for Cisco Jasper (Control Center).

Features
- FastAPI app exposing `/mcp` (mounted MCP streamable HTTP app)
- `/health` endpoint
- `GET /cc/echo/{param}` - proxy to CC echo endpoint
- `GET /cc/devices?modifiedSince=...&accountId=...` - list devices modified since timestamp (enforces allowlist)
- Optional MCP auth via `MCP_AUTH_TOKEN`
- Optional CORS support

Local-only MCP stdio demo

1. Copy `.env.example` to `.env` and fill `CC_BASE_URL`, `CC_JASPER_BEARER` and optional `CC_ALLOWED_ACCOUNT_IDS`.
2. Install dependencies and run the MCP server locally via stdio transport:

```powershell
python -m pip install -r pia_jasper_mcp/requirements.txt
python -m pia_jasper_mcp
```

The server runs as a local MCP server using stdio. This is a demo harness and does not expose HTTP endpoints.

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
