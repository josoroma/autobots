"""What the API's and the worker's entry points build from their environment, without a process
(R-64: POPS-03, XMOD-08, POPS-14)."""

import asyncio
import os
from pathlib import Path
from uuid import uuid4

import pytest

from autobots.adapters.object_storage import SupabaseObjectStore
from autobots.api import main as api_main
from autobots.application.credentials.precedence import resolve_environment_key
from autobots.application.readiness import MalformedSetting
from autobots.application.tool_keys import DEFAULT_KEY_FILE
from autobots.operations import composition

ARRANGED_KEY = "sk-or-arranged-composition-0000"


def test_without_a_configuration_root_there_is_no_provider_context() -> None:
    assert composition.provider_context({}) is None
    assert composition.provider_context({"AUTOBOTS_CONFIG_ROOT": ""}) is None


def test_the_context_keeps_the_live_environment_so_a_later_key_is_seen(tmp_path: Path) -> None:
    """The mapping itself, never a copy: a key set after the context is built is the one the next
    attempt resolves (model-gateway rule)."""
    environ = {"AUTOBOTS_CONFIG_ROOT": str(tmp_path), "NODE_ENV": "test"}
    context = composition.provider_context(environ)
    assert context is not None and context.process_environment is environ
    assert resolve_environment_key(context.process_environment, context.config_root, "test") is None
    environ["OPENROUTER_API_KEY"] = ARRANGED_KEY
    found = resolve_environment_key(context.process_environment, context.config_root, "test")
    assert found is not None and found.value == ARRANGED_KEY


def test_the_context_never_shows_the_environment(tmp_path: Path) -> None:
    environ = {"AUTOBOTS_CONFIG_ROOT": str(tmp_path), "OPENROUTER_API_KEY": ARRANGED_KEY}
    assert ARRANGED_KEY not in repr(composition.provider_context(environ))


def test_the_master_key_file_defaults_once_and_can_be_overridden(tmp_path: Path) -> None:
    root = {"AUTOBOTS_CONFIG_ROOT": str(tmp_path)}
    context = composition.provider_context(root)
    assert context is not None and context.master_key_file == Path.home() / DEFAULT_KEY_FILE
    chosen = tmp_path / "master.key"
    context = composition.provider_context(
        {**root, "AUTOBOTS_PROVIDER_MASTER_KEY_FILE": str(chosen)}
    )
    assert context is not None and context.master_key_file == chosen


def test_storage_needs_both_its_address_and_its_key() -> None:
    assert composition.object_store({}) is None
    assert composition.object_store({"AUTOBOTS_SUPABASE_URL": "http://127.0.0.1:1"}) is None
    assert composition.object_store({"AUTOBOTS_SERVICE_ROLE_KEY": "arranged"}) is None
    both = {"AUTOBOTS_SUPABASE_URL": "http://127.0.0.1:1", "AUTOBOTS_SERVICE_ROLE_KEY": "arranged"}
    assert isinstance(composition.object_store(both), SupabaseObjectStore)


def test_with_no_provider_context_nothing_unattended_starts() -> None:
    check = composition.credential_check({})
    assert check is composition.no_credential
    assert asyncio.run(check(object(), uuid4())) == "credentials_required"


def test_missing_settings_are_named_together_and_never_their_values() -> None:
    environ = {"A": "first", "B": " ", "D": "fourth"}
    assert composition.require(environ, "A", "D") == ("first", "fourth")
    with pytest.raises(MalformedSetting) as missing:
        composition.require(environ, "A", "B", "C")
    assert str(missing.value) == "set B, C"


@pytest.mark.parametrize("raw", ["soon", "-1", "nan", "inf"])
def test_a_malformed_duration_names_its_variable(raw: str) -> None:
    with pytest.raises(MalformedSetting) as malformed:
        composition.seconds({"AUTOBOTS_STREAM_SECONDS": raw}, "AUTOBOTS_STREAM_SECONDS")
    assert str(malformed.value).startswith("AUTOBOTS_STREAM_SECONDS must be")
    assert raw not in str(malformed.value)


def test_a_duration_is_read_or_left_to_its_default() -> None:
    assert composition.seconds({}, "S") is None
    assert composition.seconds({"S": " "}, "S") is None
    assert composition.seconds({"S": "4"}, "S") == 4.0
    assert composition.seconds({"S": "0"}, "S") == 0.0


def test_a_process_that_cant_start_says_error_and_exits_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as stopped:
        composition.stop_unconfigured(MalformedSetting("set AUTOBOTS_DATABASE_URL"))
    assert stopped.value.code == 2
    assert capsys.readouterr().err == "ERROR: set AUTOBOTS_DATABASE_URL\n"


def configured_api(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(api_main, "configure_logging", lambda: None)
    monkeypatch.setattr(api_main, "forbid_remote_tracing", lambda _environ: None)
    for name in ("AUTOBOTS_MIN_FREE_BYTES", "AUTOBOTS_STREAM_SECONDS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AUTOBOTS_CONFIG_ROOT", str(tmp_path))


def test_the_api_builds_its_context_and_store_from_the_live_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    configured_api(monkeypatch, tmp_path)
    monkeypatch.setenv("AUTOBOTS_SUPABASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("AUTOBOTS_SERVICE_ROLE_KEY", "arranged")
    monkeypatch.setenv("AUTOBOTS_STREAM_SECONDS", "4")
    app = api_main.create_configured_app()
    assert app.state.provider_context.process_environment is os.environ
    assert isinstance(app.state.object_store, SupabaseObjectStore)
    assert app.state.stream_seconds == 4.0


def test_a_malformed_stream_lifetime_stops_the_api_with_exit_2(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    configured_api(monkeypatch, tmp_path)
    monkeypatch.setenv("AUTOBOTS_STREAM_SECONDS", "soon")
    with pytest.raises(SystemExit) as stopped:
        api_main.create_configured_app()
    assert stopped.value.code == 2
    assert capsys.readouterr().err.startswith("ERROR: AUTOBOTS_STREAM_SECONDS must be")
