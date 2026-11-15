# @autobots/db-types

`src/generated.ts` is the exposure snapshot of the `public` schema: a row type for each table, holding only the columns `authenticated` can select. `scripts/app_db.py types` regenerates it from the SQL migrations, and `scripts/app_db.py qualify`, in the `db` profile, fails when it drifts, so a grant that reveals or hides a column shows up in review (Decision 0029 F6). It is never hand-written. Private schemas are deliberately absent. No package imports it, so it exports no module (SQLI-06).
