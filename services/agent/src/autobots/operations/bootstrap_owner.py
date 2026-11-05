"""Create the local owner through the supported Auth admin API, with public signup left disabled.

Values come from the environment, so a password or key never appears in a process list:
AUTOBOTS_SUPABASE_URL, AUTOBOTS_SERVICE_ROLE_KEY, AUTOBOTS_OWNER_PASSWORD, AUTOBOTS_DATABASE_URL.
Prints only the new identifiers. Exit codes: 0 created, 1 refused, 2 missing configuration.
"""

import argparse
import json
import os
import sys
from urllib import error, request
from uuid import UUID, uuid4

import psycopg

REQUIRED = (
    "AUTOBOTS_SUPABASE_URL",
    "AUTOBOTS_SERVICE_ROLE_KEY",
    "AUTOBOTS_OWNER_PASSWORD",
    "AUTOBOTS_DATABASE_URL",
)


def create_auth_user(base_url: str, service_key: str, email: str, password: str) -> UUID:
    """Direct writes to Auth internals are forbidden, so this goes through its API."""
    body = json.dumps({"email": email, "password": password, "email_confirm": True}).encode()
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }
    url = f"{base_url}/auth/v1/admin/users"
    with request.urlopen(request.Request(url, data=body, headers=headers), timeout=20) as reply:
        return UUID(json.loads(reply.read())["id"])


def create_workspace(database_url: str, user_id: UUID, name: str) -> UUID:
    workspace_id = uuid4()
    with psycopg.connect(database_url) as connection:
        connection.execute(
            "insert into public.workspaces (id, name) values (%s, %s)",
            (workspace_id, name),
        )
        connection.execute(
            "insert into public.workspace_members (workspace_id, user_id, role) "
            "values (%s, %s, 'owner')",
            (workspace_id, user_id),
        )
    return workspace_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--workspace-name", required=True)
    args = parser.parse_args()
    missing = [name for name in REQUIRED if not os.environ.get(name)]
    if missing:
        print(f"ERROR: set {', '.join(missing)}.", file=sys.stderr)
        return 2
    try:
        user_id = create_auth_user(
            os.environ["AUTOBOTS_SUPABASE_URL"],
            os.environ["AUTOBOTS_SERVICE_ROLE_KEY"],
            args.email,
            os.environ["AUTOBOTS_OWNER_PASSWORD"],
        )
        workspace_id = create_workspace(
            os.environ["AUTOBOTS_DATABASE_URL"], user_id, args.workspace_name
        )
    except (error.URLError, psycopg.Error, ValueError, KeyError) as failure:
        print(f"ERROR: bootstrap was refused: {type(failure).__name__}.", file=sys.stderr)
        return 1
    print(json.dumps({"user_id": str(user_id), "workspace_id": str(workspace_id)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
