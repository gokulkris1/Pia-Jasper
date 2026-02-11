import subprocess
import sys
import uuid
import json
import shlex
from datetime import datetime
from typing import Dict, Optional


def parse_input(text: str) -> Dict[str, str]:
    """Parse a single JASPER_RUN block into a dict of keys.

    Expected format:
    JASPER_RUN
    operation: ECHO
    param: hello-three
    """
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    if not lines or lines[0] != "JASPER_RUN":
        raise ValueError("Input must start with 'JASPER_RUN'")
    data = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        data[k.strip()] = v.strip()
    return data


def call_tool_via_sdk(proc, tool_name: str, params: dict):
    """Attempt to use the MCP client SDK to call the given tool over the
    stdio-connected subprocess. This function tries a few common client APIs
    and raises RuntimeError with guidance if none found.
    """
    try:
        # Late import so missing SDK yields a clear error
        try:
            from mcp.client.fastmcp import FastMCPClient
        except Exception:
            from mcp.client import FastMCPClient  # type: ignore
    except Exception as exc:
        raise RuntimeError("MCP client SDK not available (install the MCP SDK)") from exc

    # Try to construct client bound to the subprocess stdio
    client = None
    tried = []
    constructors = [
        (FastMCPClient, (proc.stdin, proc.stdout), {}),
        (FastMCPClient, (), {"stdin": proc.stdin, "stdout": proc.stdout}),
        (FastMCPClient, (), {"process": proc, "transport": "stdio"}),
    ]
    for cls, args, kwargs in constructors:
        try:
            client = cls(*args, **kwargs)
            break
        except Exception as e:
            tried.append((cls, args, kwargs, repr(e)))

    if client is None:
        raise RuntimeError(f"Unable to construct MCP client. Tried: {tried}")

    # Try several common method names for invoking tools
    call_methods = ["call_tool", "call", "invoke", "request", "run_tool", "run"]
    last_err = None
    for m in call_methods:
        fn = getattr(client, m, None)
        if not fn:
            continue
        try:
            # Try passing kwargs first
            result = fn(tool_name, **params)
            # If result is a coroutine, run it
            if hasattr(result, "__await__"):
                import asyncio

                result = asyncio.get_event_loop().run_until_complete(result)
            return result
        except TypeError:
            try:
                # Try positional
                args = [params.get(k) for k in params]
                result = fn(tool_name, *args)
                if hasattr(result, "__await__"):
                    import asyncio

                    result = asyncio.get_event_loop().run_until_complete(result)
                return result
            except Exception as e:
                last_err = e
        except Exception as e:
            last_err = e

    raise RuntimeError(f"Failed to call tool via client SDK: {last_err}")


def run():
    raw = sys.stdin.read()
    if not raw.strip():
        print("No input provided. Paste a JASPER_RUN block on stdin.")
        sys.exit(2)

    data = parse_input(raw)
    operation = data.get("operation")
    if not operation:
        print("operation is required")
        sys.exit(2)

    job_id = str(uuid.uuid4())
    ts = datetime.utcnow().isoformat() + "Z"

    # Teams-like immediate acceptance line
    print(f"ACCEPTED: Job {job_id}")
    sys.stdout.flush()

    # Launch MCP server subprocess
    cmd = [sys.executable, "-m", "pia_jasper_mcp"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    try:
        if operation == "ECHO":
            param = data.get("param")
            tool = "cc_echo"
            params = {"param": param} if param is not None else {}
        elif operation == "GET_DEVICES_MODIFIED_SINCE":
            modifiedSince = data.get("modifiedSince")
            accountId = data.get("accountId")
            tool = "cc_get_devices_modified_since"
            params = {"modifiedSince": modifiedSince}
            if accountId is not None:
                params["accountId"] = accountId
        else:
            raise ValueError(f"Unknown operation: {operation}")

        try:
            result = call_tool_via_sdk(proc, tool, params)
            status = "SUCCESS"
        except Exception as e:
            result = {"error": str(e)}
            status = "FAILED"

        # Teams-like completion line
        print(f"COMPLETED: Job {job_id} ({status})")
        # PROOF section: include API response JSON
        print("PROOF:")
        try:
            proof_json = json.dumps(result, indent=2, sort_keys=True)
        except Exception:
            proof_json = str(result)
        print(proof_json)

        # Also print a structured receipt for programmatic use
        receipt = {
            "job_id": job_id,
            "timestamp": ts,
            "operation": operation,
            "tool": tool,
            "status": status,
            "result": result,
        }

        print('\n' + json.dumps(receipt, indent=2))

    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        proc.wait(timeout=5)


if __name__ == "__main__":
    run()
