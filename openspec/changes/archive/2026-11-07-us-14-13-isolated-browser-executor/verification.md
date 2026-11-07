# Verification — us-14-13-isolated-browser-executor

Change: us-14-13-isolated-browser-executor
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-07

## Summary

| Dimension | Status |
|---|---|
| Completeness | 9/9 tasks, 4 reqs |
| Correctness | 4/4 scenarios observed live on Docker, with real runs on a disposable database and a scripted driver |
| Coherence | Followed `design.md`; its decisions record what the live probes found |

## Scenarios

All observed by `scripts/qualify_browser_executor.py`, which ran `tests/db/browser_executor_check.py` against the two locally built images and a disposable database. Three consecutive runs on the final code passed 24 of 24 cases (the last took 85.6 seconds), and `executor_qualified` then read true.

| Scenario | Result | Observed |
|---|---|---|
| The browser can't reach this Mac or a private network | PASS | `https://example.com/` loads ("Example Domain"), and the proxy's log shows it allowed and connected to the address it checked (104.20.23.154). Refused, with every navigation landing on Chrome's error page and the proxy's reason recorded: `127.0.0.1`, `::1`, the stack's database and gateway ports on loopback (`port_refused`), `host.docker.internal` and `172.17.0.1` (`host_refused`), `10.0.0.1`, `192.168.1.1`, `172.16.0.1`, `100.64.0.1`, `169.254.169.254`, `localtest.me` and `127.0.0.1.nip.io` (`host_refused`, though listed for the call, so it's the address check that refuses them). A script-driven navigation from `example.com` to the metadata address, a `fetch` to `10.0.0.1`, an image from the metadata address, and WebSockets to `wss://localtest.me` and `ws://127.0.0.1` are refused. `file:///etc/passwd` fails `ERR_BLOCKED_BY_CLIENT` with no content. A blob download yields no file anywhere in the container and no completed download. A `POST` with a body is refused by the guard. With one request allowed, `example.org` is refused `request_cap`; with a 2,000-byte cap, the page is cut (`byte_cap`). The log holds only `at`, `event`, `host`, `reason` and `address`, with no `/`, `?` or `#` in any host. Chrome's own background hosts (Google sign-in, update, component servers) were refused `host_not_allowed`, and across all sessions only `example.com` was reached |
| Nothing of the host enters the container | PASS | A session started from an environment holding fake OpenRouter, Tavily, Jina and GitHub keys and the database URL: the browser runs as `pwuser`, `ReadonlyRootfs` true, `CapDrop` `ALL`, `no-new-privileges`, 1 GiB, 1 CPU, 256 processes, `/tmp` 256 MiB, no mounts or binds, only its internal network, no published port; the sidecar publishes 9223 on `127.0.0.1` only; no secret name or value and no `docker.sock` in either container's inspection; the image's first layers equal the digest-pinned Playwright image's. The gate answers 403 with no token, 403 with a wrong one, and 200 with the session's |
| Bounded and owned by one attempt | PASS | A process allocating past a narrowed 512 MiB cap is OOM-killed and the watcher ends the session (`memory_cap`); a runaway fork loop holds the container at 256 processes and ends it (`process_cap`); a 3-second cap ends it (`time_cap`). With real runs: cancelling the run through `apply_command` ends the session (`attempt_ended`), and so does expiring the job's lease. A session whose run's lease expired as if its worker crashed is removed by `sweep`, and a live one is kept. Each time the containers no longer exist, and the qualifier found no executor container or network left, and Docker's other resources unchanged (58 before and after) |
| Qualified only after the live check | PASS | `services/agent/tests/test_browser_executor.py`: `executor_qualified` is false with no report, a failed report, a report missing one required case or with one failed, or a report at another fingerprint, and true only for a passing report at today's fingerprint. Live, it read true after the passing runs |

Offline, the same test module pins the proxy's decisions: port, allowlist (including look-alike names), every answer public, connecting to the checked address, the request cap, plain HTTP refused with no path logged, and the gate's token handling. It also checks that the proxy imports nothing from Autobots.

## Checks run on the final code

| Check | Exit | Result |
|---|---|---|
| `python3.12 scripts/qualify_browser_executor.py`, three times | 0, 0, 0 | 24 of 24 each |
| `python3.12 scripts/verify.py --profile fast` | 0 | ruff, mypy, pytest (with the 26 offline executor tests), lint, typecheck, contract drift, API client and web unit tests passed |
| `python3.12 scripts/verify.py --profile harness` | 0 | passed |
| `openspec validate us-14-13-isolated-browser-executor` | 0 | valid |

## Findings

**Found and fixed while qualifying:**
- Chrome binds DevTools to loopback regardless of flags, so a Node supervisor exposes it to the internal network.
- Neither Chrome binary visibly honoured a managed policy, and `file://` loaded, so the guard now refuses every scheme but https, data, blob and about, and the unobservable policy file was removed.
- Chrome contacts Google's hosts on its own; quiet-start flags reduce it and a per-session host allowlist in the proxy refuses it.
- The process-cap watcher missed saturation: at the limit `docker exec` fails or stalls, and Docker's count shows one less. Every Docker call is now bounded, and a refused or stalled exec, or a count held at the limit, counts as the cap enforced. The fork load in the check now keeps forking.
- A page's own allocations don't reliably exceed the memory cap, so a process in the container does.
- The worker's environment needed an offline `uv sync` to the unchanged lock after new source files; no package changed.

## Limits

- **A server-side redirect to a private address wasn't observed live,** since only `example.com` and `example.org` may be reached and neither redirects there. Each redirect is a new `CONNECT`, decided like any other, as the offline tests show.
- The memory and process cases are arranged with a process in the container, not a page.
- The live check needs Docker, network to `example.com`, and the two images built; it is in no verification profile, and `executor_qualified` falls back to false without its report.
- **Not established:** browsing with a real model, H1, or product acceptance. No independent review ran, under Decision 0003.
