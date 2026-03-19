import os
import asyncio
from typing import Optional, Set

import httpx

from .operations import confirm_rate_plan_change, preview_rate_plan_change

try:
    # preferred import
    from mcp.server.fastmcp import FastMCP
    import mcp as mcp_module
except Exception:
    FastMCP = None
    mcp_module = None


CC_BASE_URL = os.getenv("CC_BASE_URL")
CC_JASPER_BEARER = os.getenv("CC_JASPER_BEARER")
CC_ALLOWED_ACCOUNT_IDS = os.getenv("CC_ALLOWED_ACCOUNT_IDS", "")

ALLOWED_ACCOUNTS: Set[str] = {a.strip() for a in CC_ALLOWED_ACCOUNT_IDS.split(",") if a.strip()}


def _need_config():
    return not CC_BASE_URL or not CC_JASPER_BEARER


async def _fetch_json(session: httpx.AsyncClient, url: str, params: dict = None):
    try:
        resp = await session.get(url, params=params, headers={"Authorization": CC_JASPER_BEARER})
    except httpx.RequestError as exc:
        return {"error": f"request failed: {exc}"}

    try:
        return resp.json()
    except Exception:
        return {"status_code": resp.status_code, "text": resp.text}


def _register_tool(server, name: str, func):
    # Try common registration methods on FastMCP
    if hasattr(server, "register_tool"):
        try:
            server.register_tool(name, func)
            return True
        except Exception:
            pass

    if hasattr(server, "add_tool"):
        try:
            server.add_tool(name, func)
            return True
        except Exception:
            pass

    # server.tool may be a decorator
    if hasattr(server, "tool"):
        dec = getattr(server, "tool")
        try:
            # try decorator with name
            dec(name)(func)
            return True
        except TypeError:
            try:
                dec(func)
                return True
            except Exception:
                pass
        except Exception:
            pass

    return False


def main():
    """Create FastMCP instance, register tools, and run via stdio transport.

    Entry point for `python -m pia_jasper_mcp`.
    """
    if FastMCP is None:
        raise RuntimeError("mcp.server.fastmcp.FastMCP not importable - ensure MCP SDK is installed")

    server = FastMCP()

    # Define tools
    async def cc_echo(param: str):
        if _need_config():
            return {"error": "missing CC_BASE_URL or CC_JASPER_BEARER"}
        url = f"{CC_BASE_URL.rstrip('/')}/rws/api/v1/echo/{param}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            return await _fetch_json(client, url)

    async def cc_get_devices_modified_since(modifiedSince: str, accountId: Optional[str] = None):
        if _need_config():
            return {"error": "missing CC_BASE_URL or CC_JASPER_BEARER"}
        if accountId and ALLOWED_ACCOUNTS and accountId not in ALLOWED_ACCOUNTS:
            return {"error": "accountId not allowed"}

        params = {"modifiedSince": modifiedSince}
        if accountId:
            params["accountId"] = accountId

        url = f"{CC_BASE_URL.rstrip('/')}/rws/api/v1/devices/"
        async with httpx.AsyncClient(timeout=20.0) as client:
            return await _fetch_json(client, url, params=params)

    async def cc_preview_rate_plan_change(
        identifiers: str,
        targetRatePlan: str,
        accountId: Optional[str] = None,
        requestedBy: Optional[str] = None,
        reason: Optional[str] = None,
    ):
        return await preview_rate_plan_change(
            identifiers=identifiers,
            targetRatePlan=targetRatePlan,
            accountId=accountId,
            requestedBy=requestedBy,
            reason=reason,
        )

    async def cc_confirm_rate_plan_change(operationId: str, confirmedBy: str):
        return await confirm_rate_plan_change(operationId=operationId, confirmedBy=confirmedBy)

    # Register tools - try decorator style or explicit registration
    ok1 = _register_tool(server, "cc_echo", cc_echo)
    ok2 = _register_tool(server, "cc_get_devices_modified_since", cc_get_devices_modified_since)
    ok3 = _register_tool(server, "cc_preview_rate_plan_change", cc_preview_rate_plan_change)
    ok4 = _register_tool(server, "cc_confirm_rate_plan_change", cc_confirm_rate_plan_change)

    if not (ok1 and ok2 and ok3 and ok4):
        # best-effort: attempt to attach to server.tools dict if present
        if hasattr(server, "tools") and isinstance(server.tools, dict):
            server.tools["cc_echo"] = cc_echo
            server.tools["cc_get_devices_modified_since"] = cc_get_devices_modified_since
            server.tools["cc_preview_rate_plan_change"] = cc_preview_rate_plan_change
            server.tools["cc_confirm_rate_plan_change"] = cc_confirm_rate_plan_change
        else:
            # fallback: try to set attributes
            setattr(server, "cc_echo", cc_echo)
            setattr(server, "cc_get_devices_modified_since", cc_get_devices_modified_since)
            setattr(server, "cc_preview_rate_plan_change", cc_preview_rate_plan_change)
            setattr(server, "cc_confirm_rate_plan_change", cc_confirm_rate_plan_change)

    # Start the MCP server using stdio transport
    # Try top-level mcp.run first (with flexible signature), then server.run
    if mcp_module is not None and hasattr(mcp_module, "run"):
        try:
            # try passing server explicitly
            mcp_module.run(server=server, transport="stdio")
            return
        except TypeError:
            try:
                mcp_module.run(transport="stdio")
                return
            except TypeError:
                pass

    if hasattr(server, "run"):
        # server.run may be blocking
        try:
            server.run(transport="stdio")
            return
        except TypeError:
            # try asyncio style
            loop = asyncio.get_event_loop()
            run_coro = getattr(server, "run", None)
            if asyncio.iscoroutinefunction(run_coro):
                loop.run_until_complete(run_coro(transport="stdio"))
                return

    raise RuntimeError("Unable to start MCP server with stdio transport; check SDK API")
