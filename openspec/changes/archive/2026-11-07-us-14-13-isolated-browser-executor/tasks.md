# Tasks

## 1. Images and proxy (The browser can't reach this Mac or a private network)

- [x] 1.1 Build the browser image from the digest-pinned Playwright image, with DevTools exposed to the internal network only
- [x] 1.2 Build the egress sidecar: CONNECT to named public hosts only, connected to the checked address, with caps and a host-only log, and the token-gated CDP door

## 2. Executor (Nothing of the host enters the container; Bounded and owned by one attempt)

- [x] 2.1 Start and remove one hardened session per call, with nothing of the worker's environment
- [x] 2.2 Guard requests over CDP: methods, bodies, schemes and downloads
- [x] 2.3 End a session on caps, time, a cancelled run or a lost lease, and sweep what a crashed worker left

## 3. Qualification (Qualified only after the live check)

- [x] 3.1 Qualify every refusal live on Docker with real runs on a disposable database, reaching only the qualification hosts
- [x] 3.2 Report qualified only from a passing report at the current fingerprint, and pin the logic in offline tests
- [x] 3.3 Document building and qualifying in the operations runbook
