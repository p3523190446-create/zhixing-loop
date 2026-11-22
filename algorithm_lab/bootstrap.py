"""Load project-local packages without changing the shared Python installation."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
DEPS = ROOT / 'tmp/algorithm_deps'
sys.path.insert(0, str(DEPS))
