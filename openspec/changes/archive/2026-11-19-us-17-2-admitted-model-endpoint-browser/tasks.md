# Tasks

## 1. The endpoint and its admission

- [x] 1.1 Add the translation to `adapters/model_endpoint.py`, beside the server, since the layering rule keeps new `application`-to-`adapters` imports out (`test_layers.py`). It translates an OpenAI chat completion request to LangChain messages and tools, admits it through `middleware.admitted` on the given route with an `AdmittedModel`, and translates the reply back, as JSON or a stream. It refuses `content_not_qualified` and malformed requests before admission, and turns `LoopStopped` into a typed refusal. Checked by pytest under `services/agent/tests` (`test_model_endpoint.py`), with a fake middleware and model.
- [x] 1.2 Add `adapters/model_endpoint.py`. It serves the endpoint on `127.0.0.1:0` with a per-session token, one request per connection and a body cap, and answers 401 `token_required` without the token. Checked by pytest over a socket pair, since the test session blocks connects, and on real loopback by `model_endpoint_check.py`.
- [x] 1.3 Check it on a real database with `tests/db/checks/model_endpoint_check.py`, using real admission, a scripted model and HTTP requests to the endpoint:
  - one request is one admitted call on the frozen researcher route, with its ledger row and `model_calls`, and whatever model it names;
  - no key is in the reply;
  - a request past the budget, or from a cancelled run, is refused with a typed reason, with the scripted model not reached;
  - a request without the token is refused.

  Registered in `scripts/app_db.py`, and checked by the db profile.

## 2. The relay

- [x] 2.1 Add the model relay to `adapters/egress_proxy.py`, on port 9300. It forwards only `POST /v1/chat/completions` to the configured upstream, replacing `Authorization` with the session's token. Checked by pytest under `services/agent/tests` with fake streams.
- [x] 2.2 Let `BrowserExecutor.start` take the endpoint's port and token, giving the sidecar its upstream and token and mapping `host.docker.internal` to the host gateway. Checked by pytest with a recorded Docker command line.
- [x] 2.3 Rebuild the images and extend `scripts/qualify_browser_executor.py` with the relay cases, then run it. Checked by its report: every case passes, reaching only the qualification host.

## 3. Documents

- [x] 3.1 Amend PRD-Tool-Catalog BM-01 to BM-04 for the endpoint, and update the operations runbook's browser executor section and `CODEBASE.md`. Checked by reading them against Decision 0035 Y7.

## 4. Verification

- [x] 4.1 Run the fast profile, then the db profile, and score each scenario from what was observed. Checked by their exit codes and reports.
