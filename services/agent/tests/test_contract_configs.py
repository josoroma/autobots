"""Every contract model uses one of the configurations contracts/primitives.py names (refactor plan
R-61, XTYP-16, XMOD-15), so a policy such as refusing NaN changes in one place."""

import importlib
import inspect
import pkgutil
import re
from collections.abc import Iterator
from pathlib import Path

from pydantic import BaseModel, RootModel

import autobots.contracts as contracts
from autobots.contracts.primitives import LAX_CONTRACT, STRICT_CONTRACT, TOOL_CONTRACT
from autobots.persistence.records import LENIENT

NAMED = (STRICT_CONTRACT, LAX_CONTRACT, TOOL_CONTRACT)


def contract_models() -> Iterator[type[BaseModel]]:
    for module_info in pkgutil.iter_modules(contracts.__path__):
        module = importlib.import_module(f"{contracts.__name__}.{module_info.name}")
        for _, found in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(found, BaseModel)
                and found.__module__ == module.__name__
                and not issubclass(found, RootModel)
            ):
                yield found


def test_every_contract_model_uses_a_named_configuration() -> None:
    models = list(contract_models())
    assert len(models) > 200
    for model in models:
        # Persisted documents are records, lenient by their own rule (persistence/records.py).
        allowed = (LENIENT,) if model.__module__.endswith(".persisted") else NAMED
        assert any(model.model_config == config for config in allowed), model.__qualname__


def test_only_the_primitives_declare_a_configuration() -> None:
    declaring = sorted(
        path.name
        for path in Path(contracts.__file__).parent.glob("*.py")
        if re.search(r"\bConfigDict\(", path.read_text())
    )
    assert declaring == ["primitives.py"]
