# Pia Jasper Solution Architecture

## What The System Does

The solution is an operations agent for Cisco Jasper. A user requests a SIM action in Microsoft Teams, the system validates the request, shows the before and after view, asks for confirmation, executes the change, verifies the outcome, and returns a clear audit trail.

## Plain-English Flow

1. A business user asks for a SIM change in Teams.
2. The agent converts the request into a structured operation.
3. The system validates the target account, identifiers, and requested action.
4. The system reads the current state from Jasper.
5. The system shows a preview with current state and target state.
6. The user confirms the action.
7. The system executes the operation in Jasper.
8. The system re-reads the state to verify the change.
9. The system returns success or failure, before and after evidence, logs, JSON, and CSV.

## Working Architecture

```text
Business User
   |
   v
Microsoft Teams Bot
   |
   v
Request Interpreter
   |
   +--> Safety and Policy Checks
   |
   +--> Jasper Operations Engine
             |
             +--> Preview current SIM state
             +--> Build before/after table
             +--> Wait for confirmation
             +--> Execute Jasper operation
             +--> Re-query for final state
   |
   v
Audit Logs and Artifacts
   |
   v
Reply to User in Teams
```

## Main Components

### Teams Bot

The user-facing channel. It receives requests and shows confirmations and results. It should not contain business logic.

### Request Interpreter

This layer turns natural language into a structured operation such as `RATE_PLAN_CHANGE` with identifiers, account, and target rate plan.

### Safety And Policy Checks

This is the control point that reduces operational risk. It validates:

- authenticated user identity
- explicit account context
- supported operation type
- batch size limits
- confirmation requirement before any write
- audit metadata such as requester and reason

### Jasper Operations Engine

This is the implementation core. It performs the technical Jasper workflow:

- resolve IMSI, ICCID, or MSISDN to the right SIM
- fetch current state
- fetch target details
- generate preview table
- execute the confirmed change
- verify the final state
- return pass and fail rows for partial success handling

### Audit And Reporting

Every operation should produce:

- JSON receipt for system integration
- CSV report for business users
- rendered before and after table
- raw timestamps and operator identity
- Jasper request and response evidence where available

## Security Model

The design avoids common leakage and misuse risks in several ways.

1. Separate user channel from execution engine.
2. Store secrets outside the codebase.
3. Require preview and explicit confirmation before writes.
4. Keep full audit trails for every action.
5. Enforce batch limits and account context.
6. Re-query Jasper after execution instead of trusting only HTTP success codes.
7. Support partial success reporting so mixed outcomes are visible.

## Delivery Phases

### Phase 1

One operation: rate plan change.
One customer path: test account first.
Input can come from CLI while the backend is stabilized.

### Phase 2

Add Microsoft Teams as the main front end. The execution engine remains the same.

### Phase 3

Expand to more Jasper operations and more customer accounts.

## Current Repo Position

The current repository already contains:

- an MCP server surface
- a local runner
- a simple Jasper proxy layer

The missing pieces for business-ready operation handling are:

- preview and confirmation workflow
- operation persistence and audit artifacts
- rate-plan change implementation
- Teams integration
- final Jasper-specific endpoint mapping for the live adapter