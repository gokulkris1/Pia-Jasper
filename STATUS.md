# Pia-Jasper — Project Status

**Last updated:** 2026-03-19

---

## What This Project Is

An AI agent that executes SIM management operations on **Cisco Jasper Control Center** on behalf of a service provider admin. Eventually integrated into **MS Teams** so admins can chat/call the agent to trigger operations and receive before/after state tables and success/failure feedback.

**Jasper instance:** `https://3ie.jasper.com`
**Test account:** `3IE Internal Demo Account`
**Admin user:** `ggurijalaAdmin`

---

## Phases

| Phase | Description | Status |
|-------|-------------|--------|
| **1** | One operation (Update Rate Plan), one account, CLI/file input | 🔄 In Progress |
| **2** | MS Teams bot — separate workstream, bot user + personal Teams | ⏳ Not started |
| **3** | Merge Teams + operations, scale to more ops and customers | ⏳ Not started |

---

## Phase 1 — Current Focus

### Target Operation: **Update Rate Plan**
- Input: ICCID(s), target rate plan name/ID
- Output: Before/after table, 200 OK proof, re-query confirmation

### What's Built

| Component | File | Status |
|-----------|------|--------|
| MCP server (stdio) | `pia_jasper_mcp/server.py` | ✅ Done |
| Rate plan preview tool | `pia_jasper_mcp/operations.py` | ✅ Done |
| Rate plan confirm tool | `pia_jasper_mcp/operations.py` | ✅ Done |
| Echo / device query tools | `pia_jasper_mcp/server.py` | ✅ Done |
| Stub device data for local testing | `pia_jasper_mcp/stub_devices.sample.json` | ✅ Done |
| CLI agent runner | `agent_runner.py` | ✅ Done |
| FastAPI HTTP wrapper | `pia_jasper_mcp/main.py` | ✅ Done |

### What's NOT Done Yet

- [ ] **Live Jasper API auth** — `CC_BASE_URL` and `CC_JASPER_BEARER` env vars must be configured; OAuth token flow not yet wired up
- [ ] **Real API calls** — currently running against stub data; need to hit `https://3ie.jasper.com` with real bearer token
- [ ] **End-to-end test** — run `PREVIEW_RATE_PLAN_CHANGE` → `CONFIRM_RATE_PLAN_CHANGE` against live Jasper and verify before/after
- [ ] **Rate plan list lookup** — need to resolve rate plan name → ID via API (endpoint TBD from API spec)
- [ ] **MS Teams integration** — Phase 2, not started

---

## How to Run (Local CLI)

```bash
# 1. Install dependencies
pip install -r pia_jasper_mcp/requirements.txt

# 2. Set env vars (copy and fill in)
cp pia_jasper_mcp/.env.example pia_jasper_mcp/.env

# 3. Run a preview (stub mode — no real creds needed)
echo "JASPER_RUN
operation: PREVIEW_RATE_PLAN_CHANGE
identifiers: 8944501234567890123
targetRatePlan: MyPlan
accountId: 3IE-DEMO
requestedBy: admin" | python agent_runner.py

# 4. Confirm the change (use operationId from preview output)
echo "JASPER_RUN
operation: CONFIRM_RATE_PLAN_CHANGE
operationId: <id-from-preview>
confirmedBy: admin" | python agent_runner.py
```

---

## Key Decisions

- Agent asks for **confirmation before executing** (preview → confirm two-step flow)
- All operations scoped to **test account only** until end-to-end is proven
- MS Teams and operations are **separate workstreams** to be merged in Phase 3
- Input: CLI or file; output: before/after table + PROOF JSON

---

## Next Steps

1. Get a valid Jasper bearer token for `https://3ie.jasper.com`
2. Set `CC_BASE_URL` and `CC_JASPER_BEARER` in `.env`
3. Run echo test to confirm connectivity: `operation: ECHO`
4. Run live `PREVIEW_RATE_PLAN_CHANGE` against a real ICCID in the test account
5. Confirm the change and verify SIM state updated in Jasper UI
