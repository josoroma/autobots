## Decisions

- **Probe window:** an in-process 20-entry window on the API's app state, filled by every `database_conditions` call that reaches the database: readiness, local status and admission's readiness gate. The p95 is the nearest rank, rounded up to whole milliseconds. A restart empties it. This needs no table and no tracing.
- **Applied migrations:** read through a security-definer function. The history belongs to whichever runner applied it (`autobots_install.migrations` or `autobots_disposable.migrations`), and the runtime role may read neither. The function returns only the count of migration file names, which excludes the install's Storage policy row.
- **Storage bytes:** the workspace's published artifact sizes. That is what the server already records, without reading Storage's own tables.
- **Catalog fetch time:** the catalog isn't cached, so the value is how long this page load's existing availability check took. It adds no request.
- **Loopback check:** the API inspects its own descriptors and adds no network call. Each TCP socket is duplicated. One that is bound, with a port, and has no peer is a listener, because macOS doesn't answer `SO_ACCEPTCONN`. The check passes only if every listener is on loopback. It returns null when there is none, as under a test client.
- **Verdict:** counted client-side from the checks shown, so N and M always match them. The worker count comes from the same heartbeat window as the worker check.
- **Adapter wording:** the API returns the exact package name, but the page says "LangGraph checkpoint adapter <release>". The existing leak checks treat "postgres" in page text as an address, and they stay as they are.
