"""Apply the baseline tests' real socket guard to these fixtures, and find its fake transport."""

import importlib.util
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[3] / "services/agent/tests"
sys.path.insert(0, str(TESTS))
spec = importlib.util.spec_from_file_location("baseline_conftest", TESTS / "conftest.py")
assert spec is not None and spec.loader is not None
spec.loader.exec_module(importlib.util.module_from_spec(spec))
