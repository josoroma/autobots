## Why

US-14.13, [PRD-Tool-Catalog BX-01 to BX-05](../../../../docs/PRD/PRD-Tool-Catalog.md#isolated-browser-executor) and [Decision 0018](../../../docs/engineering/decisions/0018-browser-executor.md) B1 to B3 and B8: `browse_goal` (US-14.12) needs a browser that can't reach this Mac, its services, its files or its credentials.

## What Changes

- **Images** (`infra/browser/`): the browser from the Playwright 1.64.1 image pinned by digest, running Chrome for Testing in its new headless mode under a Node supervisor that exposes DevTools to the internal network only; the egress sidecar from a Python image pinned by digest, standard library only.
- **Egress proxy** (`adapters/egress_proxy.py`): only `CONNECT` to port 443 of the hosts the call names; every DNS answer must be public, and it connects to the address it checked; request and byte caps; a log of hosts and decisions with no paths or queries. A **CDP gate** published on `127.0.0.1` only, on a random port, needs the session token.
- **Executor** (`adapters/browser_executor.py`): one session per call on its own internal and outbound networks; the browser non-root, all capabilities dropped, `no-new-privileges`, read-only root, 256 MiB `tmpfs`, 1 CPU, 1 GiB, 256 processes, no mounts and nothing of the worker's environment. A **request guard** over CDP refuses any request that isn't a GET or HEAD, or carries a body, and any scheme but https, data, blob and about, which the proxy can't see inside TLS, and denies downloads. A watcher removes the session on the time cap, a memory or process cap enforcement read from the container's cgroup counters, or the attempt losing its run, and a sweeper removes labelled sessions a crashed worker left.
- **Qualification** (`scripts/qualify_browser_executor.py`): every refusal live on Docker, with real runs on a disposable database and a scripted driver, reaching only `example.com` and `example.org`. `executor_qualified` is true only from a passing report at the current fingerprint.

## Capabilities

### New Capabilities

- `browser-executor`: the isolated browser executor.

### Modified Capabilities

None.

## Impact

`infra/browser/`, `adapters/egress_proxy.py`, `adapters/browser_executor.py`, `scripts/qualify_browser_executor.py`, `tests/db/browser_executor_check.py`, `tests/test_browser_executor.py` and the operations runbook. Two images built locally from base images pinned by digest; no Python package added (`websockets` 17.4 was already locked).
