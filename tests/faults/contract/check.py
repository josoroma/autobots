"""Compare the model's generated JSON Schema with a recorded contract."""

import json
import sys
from pathlib import Path

from models import RunSummary

expected = json.loads(Path(sys.argv[1]).read_text())
if RunSummary.model_json_schema() != expected:
    print("CONTRACT DRIFT: the generated schema differs from the recorded contract")
    raise SystemExit(1)
print("contract matches")
