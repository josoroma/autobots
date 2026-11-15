"""XDUP-01 and PRUN-05: text shown to people masks every secret shape the logs mask (SP-011)."""

import json

import pytest

from autobots.application.run_projection import public_text
from autobots.logs import redact

# Synthetic shapes, assembled so no file holds a whole token. None is a real credential.
SECRETS = {
    "OpenRouter key": "sk-or-v1-" + "a1" * 16,
    "provider key": "sk-proj-" + "Z9" * 10,
    "short provider key": "sk-" + "abcd",
    "Tavily key": "tvly-dev-" + "x1" * 8,
    "Jina key": "jina_" + "b2" * 10,
    "GitHub token": "ghp_" + "C3" * 12,
    "GitHub OAuth token": "gho_" + "D4" * 12,
    "fine-grained GitHub token": "github_pat_" + "E5" * 12,
    "bearer value": "Bearer " + "f6" * 10,
    "lowercase bearer value": "bearer " + "g7" * 10,
    "signed token": "eyJhbGciOiJIUzI1NiJ9." + "eyJzdWIiOiIxIn0." + "h8" * 10,
    "unsigned token": "eyJ" + "i1" * 8,
    "credentialed URL": "https://user:" + "p4ss" * 3 + "@example.test/path",
    "database URL": "postgresql://autobots:" + "pw" * 6 + "@127.0.0.1:54322/postgres",
    "password pair": "password=" + "q9" * 6,
    "API key pair": "api_key: " + "r0" * 6,
    # The independent review: a header's scheme once hid its value from the key-value shape.
    "authorization header": "Authorization: Bearer " + "s1" * 8,
    "quoted curl header": "-H 'Authorization: Bearer " + "t2" * 8 + "'",
    "basic authorization": "Authorization: Basic " + "dXNlcjpw" + "YXNzd29yZA==",
    "JSON field": '"password": "' + "u3" * 6 + '"',
}


@pytest.mark.parametrize("secret", SECRETS.values(), ids=SECRETS.keys())
def test_logs_and_shown_text_mask_the_same_secrets(secret: str) -> None:
    text = f"The model wrote {secret} into its plan."
    for masked in (redact(text), public_text(text)):
        assert "[redacted]" in masked
        assert secret[-6:] not in masked


@pytest.mark.parametrize(
    "words",
    [
        "A task-specific checklist, then a risk-assessment.",
        "Use flask-sqlalchemy for the models.",
        "Keep the token budget under 500 and the bearer of news anonymous.",
    ],
)
def test_shown_text_keeps_ordinary_words(words: str) -> None:
    if "bearer of" in words:
        # Prose after "bearer" is masked, as in the logs: a stricter display is allowed (SP-011).
        assert public_text(words) == words.replace("bearer of", "[redacted]")
    else:
        assert public_text(words) == words


def test_logs_still_mask_a_key_inside_a_word() -> None:
    assert redact("x=prefix" + "sk-" + "a1b2c3d4e5") == "x=prefix[redacted]"


def test_shown_text_is_still_cut_to_its_limit() -> None:
    assert public_text("a" * 600) == "a" * 500
    assert public_text("abcdef", limit=3) == "abc"


@pytest.mark.parametrize(
    "text",
    [
        # One shape starting earlier must not hide another (independent review, finding 3).
        "x" + "sk-abcd" + "tvly-" + "12345678",
        "eyJ" + "0123456789" + "token=" + "v4" * 4,
    ],
)
def test_logs_mask_secrets_that_touch(text: str) -> None:
    masked = redact(text)
    assert "1234" not in masked and "v4v4" not in masked


def test_shown_approval_arguments_still_parse_and_keep_their_other_fields() -> None:
    arguments = json.dumps(
        {
            "query": "password=" + "w5" * 5,
            "url": "postgresql://user:" + "x6" * 5 + "@db.example.test/app",
            "token": "y7" * 6,
            "amount": 5,
            "to": "account-42",
        }
    )
    shown = json.loads(public_text(arguments, limit=10_000))
    assert "w5w5" not in json.dumps(shown) and "x6x6" not in json.dumps(shown)
    assert shown["token"] == "[redacted]"
    assert shown["amount"] == 5 and shown["to"] == "account-42"


def test_shown_query_strings_keep_their_other_parameters() -> None:
    shown = public_text("send?password=" + "z8" * 5 + "&amount=5&to=account-42")
    assert "z8z8" not in shown
    assert shown.endswith("&amount=5&to=account-42")
    # An ampersand inside a value, not before another parameter, stays masked.
    assert public_text("password=ab&cd done") == "password=[redacted] done"
