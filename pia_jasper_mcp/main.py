import os
import uuid
from typing import Optional

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .operations import confirm_rate_plan_change, preview_rate_plan_change

try:
    from mcp.server import fastmcp
except Exception:
    fastmcp = None

CC_BASE_URL = os.getenv("CC_BASE_URL")
CC_JASPER_BEARER = os.getenv("CC_JASPER_BEARER")
CC_ALLOWED_ACCOUNT_IDS = os.getenv("CC_ALLOWED_ACCOUNT_IDS", "")
MCP_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN")

ALLOWED_ACCOUNTS = {a.strip() for a in CC_ALLOWED_ACCOUNT_IDS.split(",") if a.strip()}

ENABLE_CORS = os.getenv("ENABLE_CORS", "false").lower() in ("1", "true", "yes")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

app = FastAPI(title="Pia Jasper MCP Proxy")

if ENABLE_CORS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS or ["*"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )


async def verify_mcp_auth(authorization: Optional[str] = Header(None)):
    if MCP_AUTH_TOKEN:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing Bearer token")
        token = authorization.split(" ", 1)[1]
        if token != MCP_AUTH_TOKEN:
            raise HTTPException(status_code=403, detail="Invalid MCP auth token")


def get_mcp_session_id(request: Request, mcp_session_id: Optional[str] = Header(None)) -> str:
    if mcp_session_id:
        return mcp_session_id
    incoming = request.headers.get("Mcp-Session-Id")
    if incoming:
        return incoming
    return str(uuid.uuid4())


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/cc/echo/{param}")
async def cc_echo(param: str, request: Request, authorization: Optional[str] = Header(None)):
    await verify_mcp_auth(authorization)
    if not CC_BASE_URL or not CC_JASPER_BEARER:
        raise HTTPException(status_code=500, detail="CC_BASE_URL or CC_JASPER_BEARER not configured")

    url = f"{CC_BASE_URL.rstrip('/')}/rws/api/v1/echo/{param}"
    params = dict(request.query_params)

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url, params=params, headers={"Authorization": CC_JASPER_BEARER})
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"upstream request failed: {exc}")

    content = None
    try:
        content = resp.json()
    except Exception:
        content = {"text": resp.text}

    if resp.status_code >= 400:
        return JSONResponse(status_code=resp.status_code, content={"error": content})

    session_id = get_mcp_session_id(request)
    return JSONResponse(status_code=200, content=content, headers={"Mcp-Session-Id": session_id})


@app.get("/cc/devices")
async def cc_get_devices_modified_since(modifiedSince: str, accountId: Optional[str] = None, request: Request = None, authorization: Optional[str] = Header(None)):
    await verify_mcp_auth(authorization)
    if accountId and ALLOWED_ACCOUNTS:
        if accountId not in ALLOWED_ACCOUNTS:
            raise HTTPException(status_code=403, detail="accountId not allowed")

    if not CC_BASE_URL or not CC_JASPER_BEARER:
        raise HTTPException(status_code=500, detail="CC_BASE_URL or CC_JASPER_BEARER not configured")

    params = {"modifiedSince": modifiedSince}
    if accountId:
        params["accountId"] = accountId

    url = f"{CC_BASE_URL.rstrip('/')}/rws/api/v1/devices/"

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.get(url, params=params, headers={"Authorization": CC_JASPER_BEARER})
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"upstream request failed: {exc}")

    try:
        content = resp.json()
    except Exception:
        content = {"text": resp.text}

    if resp.status_code >= 400:
        return JSONResponse(status_code=resp.status_code, content={"error": content})

    session_id = get_mcp_session_id(request)
    return JSONResponse(status_code=200, content=content, headers={"Mcp-Session-Id": session_id})


@app.post("/cc/rate-plan/preview")
async def cc_preview_rate_plan(payload: dict, request: Request, authorization: Optional[str] = Header(None)):
    await verify_mcp_auth(authorization)
    result = await preview_rate_plan_change(
        identifiers=payload.get("identifiers", ""),
        targetRatePlan=payload.get("targetRatePlan", ""),
        accountId=payload.get("accountId"),
        requestedBy=payload.get("requestedBy"),
        reason=payload.get("reason"),
    )
    session_id = get_mcp_session_id(request)
    status_code = 200 if result.get("status") in {"READY_FOR_CONFIRMATION", "CONFIGURATION_REQUIRED", "BLOCKED"} else 500
    return JSONResponse(status_code=status_code, content=result, headers={"Mcp-Session-Id": session_id})


@app.post("/cc/rate-plan/confirm")
async def cc_confirm_rate_plan(payload: dict, request: Request, authorization: Optional[str] = Header(None)):
    await verify_mcp_auth(authorization)
    operation_id = payload.get("operationId")
    confirmed_by = payload.get("confirmedBy")
    if not operation_id or not confirmed_by:
        raise HTTPException(status_code=400, detail="operationId and confirmedBy are required")

    try:
        result = await confirm_rate_plan_change(operationId=operation_id, confirmedBy=confirmed_by)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    session_id = get_mcp_session_id(request)
    status_code = 200 if result.get("status") in {"COMPLETED", "FAILED", "CONFIGURATION_REQUIRED"} else 500
    return JSONResponse(status_code=status_code, content=result, headers={"Mcp-Session-Id": session_id})


# Mount MCP streamable HTTP app at /mcp if available
if fastmcp is not None:
    try:
        mcp_app = fastmcp.streamable_http_app()
        app.mount("/mcp", mcp_app)
    except Exception:
        @app.get("/mcp")
        async def mcp_unavailable():
            return {"error": "MCP streamable app unavailable"}
else:
    @app.get("/mcp")
    async def mcp_unavailable():
        return {"error": "MCP streamable app not installed"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")
