"""Create the local owner through the supported Auth admin API, with public signup left disabled.

Values come from the environment, so a password or key never appears in a process list:
AUTOBOTS_SUPABASE_URL, AUTOBOTS_SERVICE_ROLE_KEY, AUTOBOTS_OWNER_PASSWORD, AUTOBOTS_DATABASE_URL.
It prints only identifiers.

The order keeps an Auth user from being left without its workspace (POPS-15, SP-015, SP-018):

1. One database transaction inserts the workspace and checks the member grant, which proves the
   URL, the grants and the name before any user exists. A refusal here leaves nothing.
2. Auth creates the user. A 4xx refusal rolls the workspace back and leaves nothing. A 5xx, or an
   answer that is lost or cut short, is unresolved: the user may exist, and the runbook says how to
   find it and finish with `--user-id`.
3. The owner membership commits with the workspace. If this fails, it prints `workspace_incomplete`
   with the user's ID, and `--user-id <id>` finishes it for that existing user. Then a transaction
   lock on the ID is held, Auth is only read, to confirm the user, and a user who already owns a
   workspace is refused.

The transaction stays open across the one Auth call, which this one-shot command accepts. Each
socket operation of that call waits up to AUTH_SECONDS.
Exit codes: 0 created, 1 refused, incomplete or unresolved, 2 missing configuration or arguments.
"""

import argparse
import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager
from http.client import HTTPException
from typing import Any, Protocol
from urllib import error, request
from uuid import UUID, uuid4

import psycopg

from autobots.operations.cli import EXIT_REFUSED, Refused, command, uuid_argument
from autobots.operations.composition import DATABASE_URL, SERVICE_KEY, STORAGE_URL, require

PASSWORD = "AUTOBOTS_OWNER_PASSWORD"
REQUIRED = (STORAGE_URL, SERVICE_KEY, PASSWORD, DATABASE_URL)
# Finishing for an existing user reads Auth, and sets no password.
REQUIRED_TO_FINISH = (STORAGE_URL, SERVICE_KEY, DATABASE_URL)
AUTH_SECONDS = 20
SERVER_ERROR = 500


class Auth(Protocol):
    """The two Auth admin calls bootstrap makes."""

    def create_user(self, email: str, password: str) -> UUID: ...

    def user_exists(self, user_id: UUID) -> bool: ...


class Rows(Protocol):
    def fetchone(self) -> tuple[Any, ...] | None: ...


class Connection(Protocol):
    """A runtime-role psycopg connection, as far as bootstrap uses it."""

    def execute(self, query: str, params: Sequence[object], /) -> Rows: ...

    def commit(self) -> None: ...


Connect = Callable[[str], AbstractContextManager[Connection]]


class AuthAdmin:
    """Auth's admin API through the gateway. Direct writes to Auth internals are forbidden."""

    def __init__(self, base_url: str, service_key: str) -> None:
        self._base_url = base_url
        self._service_key = service_key

    def _send(self, path: str, body: bytes | None = None) -> dict[str, Any]:
        headers = {
            "apikey": self._service_key,
            "Authorization": f"Bearer {self._service_key}",
            "Content-Type": "application/json",
        }
        url = f"{self._base_url}/auth/v1/admin/users{path}"
        with request.urlopen(
            request.Request(url, data=body, headers=headers), timeout=AUTH_SECONDS
        ) as reply:
            answer: dict[str, Any] = json.loads(reply.read())
            return answer

    def create_user(self, email: str, password: str) -> UUID:
        body = json.dumps({"email": email, "password": password, "email_confirm": True}).encode()
        return UUID(self._send("", body)["id"])

    def user_exists(self, user_id: UUID) -> bool:
        try:
            return UUID(self._send(f"/{user_id}")["id"]) == user_id
        except error.HTTPError as failure:
            if failure.code == 404:
                return False
            raise


class Incomplete(Exception):
    """Auth created the user, and its workspace didn't commit."""

    def __init__(self, user_id: UUID, failure: Exception) -> None:
        super().__init__(type(failure).__name__)
        self.user_id = user_id
        self.failure = type(failure).__name__


class Unresolved(Exception):
    """Auth's answer to creating the user was lost, so the user may exist."""


def _prepare(connection: Connection, name: str) -> UUID:
    """The workspace, uncommitted, and proof that its owner can be added, before any user exists."""
    workspace_id = uuid4()
    connection.execute(
        "insert into public.workspaces (id, name) values (%s, %s)", (workspace_id, name)
    )
    row = connection.execute(
        "select has_table_privilege('public.workspace_members', 'insert')", ()
    ).fetchone()
    if row is None or not row[0]:
        raise Refused("the database role can't add a workspace member, so nothing was created")
    return workspace_id


def _created_user(auth: Auth, email: str, password: str) -> UUID:
    """Only a 4xx is a refusal with nothing created. A 5xx can come after Auth created the user,
    and a timeout, a lost connection, a reply cut short (`HTTPException`) or one without an ID
    leaves that unknown too, so each of those is unresolved."""
    try:
        return auth.create_user(email, password)
    except error.HTTPError as failure:
        if failure.code >= SERVER_ERROR:
            raise Unresolved(f"HTTP {failure.code}") from None
        raise Refused(
            f"Auth refused the user (HTTP {failure.code}), for example an email already in use, "
            "so nothing was created"
        ) from None
    except (OSError, HTTPException, ValueError, KeyError) as failure:
        raise Unresolved(type(failure).__name__) from None


def _existing_user(connection: Connection, auth: Auth, user_id: UUID) -> UUID:
    """Held by a transaction lock on the user's ID, so two finishes for one user can't each pass
    the ownership check and create a workspace."""
    connection.execute("select pg_advisory_xact_lock(hashtextextended(%s, 0))", (str(user_id),))
    owned = connection.execute(
        "select workspace_id from public.workspace_members where user_id = %s and role = 'owner' "
        "order by workspace_id limit 1",
        (user_id,),
    ).fetchone()
    if owned is not None:
        raise Refused(f"that user already owns workspace {owned[0]}, so nothing was created")
    try:
        exists = auth.user_exists(user_id)
    except error.HTTPError as failure:
        raise Refused(
            f"Auth refused the lookup (HTTP {failure.code}), so nothing was created"
        ) from None
    except (OSError, HTTPException, ValueError, KeyError) as failure:
        raise Refused(
            f"Auth didn't answer the lookup ({type(failure).__name__}), so nothing was created"
        ) from None
    if not exists:
        raise Refused("Auth has no user with that ID, so nothing was created")
    return user_id


def bootstrap(
    connect: Connect,
    database_url: str,
    auth: Auth,
    workspace_name: str,
    *,
    email: str | None = None,
    password: str = "",
    user_id: UUID | None = None,
) -> dict[str, str]:
    """The owner and its workspace, in the order the module describes. `user_id` finishes one
    whose workspace didn't commit; otherwise `email` and `password` create the user."""
    try:
        with connect(database_url) as connection:
            workspace_id = _prepare(connection, workspace_name)
            if user_id is not None:
                owner = _existing_user(connection, auth, user_id)
            else:
                owner = _created_user(auth, email or "", password)
            try:
                connection.execute(
                    "insert into public.workspace_members (workspace_id, user_id, role) "
                    "values (%s, %s, 'owner')",
                    (workspace_id, owner),
                )
                connection.commit()
            except psycopg.Error as failure:
                raise Incomplete(owner, failure) from None
    except psycopg.Error as failure:
        raise Refused(
            f"the database refused ({type(failure).__name__}), so nothing was created"
        ) from None
    return {"user_id": str(owner), "workspace_id": str(workspace_id)}


def _run(
    arguments: argparse.Namespace, environ: Mapping[str, str], auth: Auth | None, connect: Connect
) -> int:
    if arguments.user_id is not None:
        base, key, database_url = require(environ, *REQUIRED_TO_FINISH)
        password = ""
    else:
        base, key, password, database_url = require(environ, *REQUIRED)
    try:
        created = bootstrap(
            connect,
            database_url,
            auth or AuthAdmin(base, key),
            arguments.workspace_name,
            email=arguments.email,
            password=password,
            user_id=arguments.user_id,
        )
    except Incomplete as stopped:
        print(json.dumps({"status": "workspace_incomplete", "user_id": str(stopped.user_id)}))
        print(
            f"INCOMPLETE: Auth created user {stopped.user_id}, and its workspace didn't commit "
            f"({stopped.failure}). Fix the cause, then finish it with: --user-id "
            f"{stopped.user_id} --workspace-name <name>",
            file=sys.stderr,
        )
        return EXIT_REFUSED
    except Unresolved as lost:
        print(
            f"UNRESOLVED: Auth's answer was lost or failed ({lost}), so the user for that email "
            "may exist. Nothing else was created. Run it again: if Auth says the email is in use, "
            "find that user's ID and finish it with: --user-id <id> --workspace-name <name> "
            "(docs/engineering/runbooks/local-app.md).",
            file=sys.stderr,
        )
        return EXIT_REFUSED
    print(json.dumps(created))
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    auth: Auth | None = None,
    connect: Connect = psycopg.connect,
) -> int:
    """The keyword arguments are for a check's fakes. Only Python can pass them."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    who = parser.add_mutually_exclusive_group(required=True)
    who.add_argument("--email")
    who.add_argument(
        "--user-id",
        type=uuid_argument,
        help="Finish the workspace for an Auth user an earlier run created.",
    )
    parser.add_argument("--workspace-name", required=True)
    arguments = parser.parse_args(argv)
    values = os.environ if environ is None else environ
    return command(lambda: _run(arguments, values, auth, connect))


if __name__ == "__main__":
    raise SystemExit(main())
