# Todo For Non-Corporate Machine

Date: 2026-03-19

## Git
1. Review current uncommitted files and decide whether to keep all of them in the next commit:
   - `README_MVP.md`
   - `pytest.ini`
   - `requirements-dev.txt`
   - `run_tests.py`
   - `setup_tests.ps1`
   - `tests/`
   - `running notes.md` (optional: keep out of product commit if you only want it as an audit note)
2. Commit the reconciled local changes on top of `main`.
3. Push `main` to `origin` once network/auth policy allows it.

## Python Environment
1. Create or activate a Python virtual environment.
2. Install app/runtime dependencies required for the MVP paths.
3. Install dev/test dependencies from `requirements-dev.txt`.

## Verification
1. Run the test suite with `python -m pytest`.
2. Fix the current endpoint contract mismatch:
   - `mvp_ops_executor.app.health()` returns `{"status": "ok"}`.
   - `tests/test_endpoints.py` expects `{"status": "healthy"}`.
3. Run the FastAPI MVP locally and verify:
   - `/health`
   - `/chat`
   - `/logs`
   - `/api/logs`
4. Confirm parser and connector tests pass under the real environment.

## Jasper Readiness
1. Provide `JASPER_BASE_URL` and `JASPER_API_TOKEN` if live Jasper integration is needed.
2. Decide whether MVP demo stays on `MockConnector` or moves to live `JasperConnector` work.
3. If live work is required, implement and validate the real Jasper connector methods.

## Documentation Cleanup
1. Decide whether `run_tests.py` should auto-install `pytest`; on restricted machines this is not desirable.
2. Decide whether `setup_tests.ps1` should remain an install script or be split into setup vs run steps.
3. Update `README_MVP.md` after the final test command and health endpoint contract are settled.