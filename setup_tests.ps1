# PowerShell script to prepare the testing environment
# Usage: run from project root in PowerShell

# ensure venv exists
if (-not (Test-Path .venv)) {
    python -m venv .venv
}

# activate virtual env (bypass execution policy)
$env:VIRTUAL_ENV = "$PWD\.venv"
$env:PATH = "$PWD\.venv\Scripts;" + $env:PATH

Write-Host "Installing development dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt

Write-Host "Testing environment ready. Run 'python -m pytest' to execute tests."