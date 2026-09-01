import sys
from pathlib import Path

# Tests import backend modules by their package-relative names
# (e.g. `from models.task import Task`), matching how the app runs.
BACKEND = Path(__file__).resolve().parent.parent / "backend"

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
