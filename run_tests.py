import subprocess
import sys

if __name__ == "__main__":
    # ensure pytest is installed
    try:
        import pytest  # type: ignore
    except ImportError:
        print("pytest not found, installing from requirements-dev.txt")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements-dev.txt"])
    sys.exit(pytest.main(["tests"]))
