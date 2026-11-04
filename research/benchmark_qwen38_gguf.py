#!/usr/bin/env python3
"""Bounded, standard-library SSE timing probe for an already running local server.

One warm-up and three measured requests, each capped at 128 generated tokens.
This script never loads models, starts servers, executes tools, or installs code.
Timing samples deliberately request a longer answer: truncation is not task success.

  python3 research/benchmark_qwen38_gguf.py
  python3 research/benchmark_qwen38_gguf.py --self-test  # no HTTP calls or report writes
  python3 research/benchmark_qwen38_gguf.py --summarize-report research/qwen38-gguf-performance.json
"""

import argparse
import contextlib
import datetime as dt
import hashlib
import ipaddress
import io
import json
import math
import os
from pathlib import Path
import signal
import statistics
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request


OUTPUT_TOKENS = 128
MEASURED_RUNS = 3
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_SSE_LINE_BYTES = 64 * 1024
MAX_SSE_EVENTS = 10000
CHECKPOINT_INTERVAL_SECONDS = 1.0

SYSTEM_PROMPT = (
    "You are auditing a local automated workflow service. Use only the supplied "
    "incident records. Distinguish observations from hypotheses. Do not call tools, "
    "invent missing measurements, or claim that suggested actions were executed. "
    "Return the audit directly, without a thinking block."
)
USER_PROMPT = """Prepare a 180–220-word operational handoff from these fixed records.
Prioritize correctness risks before speed. Cite job identifiers, explain the likely
bottleneck as a hypothesis, and propose two reversible diagnostics. Include what
the records cannot establish. Use connected prose, not a list of record copies.

Environment: one local inference slot, a durable worker queue, and an 8,192-token
context. Model and tool calls share a run budget but have separate counters. A tool
commit must be recorded under an idempotency key before a worker reports success.
Approval waits are excluded from active execution time. No external messages may
be sent during this audit. All times below are observations from one test session;
they are not controlled benchmark averages.

J01 / 09:00:00 — Invoice lookup finished in 180 ms. The tool returned invoice A17,
three line items totaling 420, and call identifier call-17. The following model
request omitted that tool result but retained the assistant's tool-call message.
J02 / 09:00:20 — A file export committed under key export-22. The worker crashed
before acknowledging completion. Recovery queued the same export with a new key.
No second write has yet been observed; duplicate effects remain a risk to check.
J03 / 09:01:00 — A research job made 24 model calls and 18 tool calls. Its reviewer
asked for another model call, although the whole-run model limit is 24. The queue
accepted the request. The records do not show whether inference began.
J04 / 09:01:15 — A proposed publication has awaited approval for 90 seconds.
Its active-time counter increased by 90 seconds despite the documented pause rule.
J05 / 09:02:45 — A parent was cancelled while a child awaited the inference slot.
The child's queue entry remains ready. No cancellation check is logged at dequeue.
J06 / 09:03:00 — A retrieved document added 7,900 tokens to a 900-token history.
The request exceeded context and failed. The worker retried the identical payload.
J07 / 09:03:20 — A nested integer argument arrived as the string \"42\". Validation
rejected it before execution. One bounded repair succeeded with an integer value.
J08 / 09:03:40 — Two child agents became ready together. Their parent retained the
single inference permit while waiting. Both children report waiting for that permit.
J09 / 09:04:00 — The browser disconnected from a running job. Durable execution
continued; reconnect replayed events after the last acknowledged event identifier.
J10 / 09:04:20 — A schema-valid research answer cited source S9, which was absent
from its evidence set. A deterministic reference check rejected the final answer.
J11 / 09:04:40 — One short request generated nine tokens in a warmed session.
Someone extrapolated its rate to long tasks without recording prompt-cache reuse.
J12 / 09:05:00 — One invoice verification task completed correctly after two tool
calls. This isolated result does not measure long-run recovery or general planning.

Write the handoff now, separating confirmed defects, unresolved risks, and the
next two checks. Avoid attributing queue, history, or authorization defects to
model quality without evidence. Do not compress the answer into one sentence.
"""


class DeadlineExceeded(Exception):
    pass


class BenchmarkInterrupted(Exception):
    def __init__(self, signum):
        self.signum = signum
        super().__init__(f"Interrupted by signal {signum}")


class StreamError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise StreamError(f"HTTP redirect rejected ({code}); use the local endpoint directly")


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def token_count(value):
    return value if type(value) is int and value >= 0 else None


def reject_non_json_constant(value):
    raise ValueError(f"Non-JSON numeric constant: {value}")


def local_base_url(value):
    parsed = urllib.parse.urlsplit(value)
    try:
        local = parsed.hostname == "localhost" or ipaddress.ip_address(parsed.hostname).is_loopback
    except (ValueError, TypeError):
        local = False
    if (parsed.scheme != "http" or not local or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path.rstrip("/") not in ("", "/v1")):
        raise argparse.ArgumentTypeError("Use an HTTP loopback URL with no credentials, optionally ending in /v1")
    try:
        parsed.port
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    return value.rstrip("/").removesuffix("/v1")


def bounded_seconds(maximum):
    def parse(value):
        try:
            result = float(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("Expected a number of seconds") from exc
        if not math.isfinite(result) or not 0 < result <= maximum:
            raise argparse.ArgumentTypeError(f"Must be greater than zero and at most {maximum} seconds")
        return result
    return parse


def atomic_write(path, report):
    """Publish a whole valid JSON document; preserve the previous file on failure."""
    path.parent.mkdir(parents=True, exist_ok=True)
    report["updated_at"] = utc_now()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@contextlib.contextmanager
def wall_timeout(seconds):
    """A hard POSIX wall deadline also catches SSE that continually trickles bytes."""
    def on_alarm(_signum, _frame):
        raise DeadlineExceeded(f"Request reached its {seconds:.3f}-second wall deadline")

    previous = signal.signal(signal.SIGALRM, on_alarm)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def request_payload(model):
    return {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content": USER_PROMPT}],
        "stream": True,
        "stream_options": {"include_usage": True},
        "max_tokens": OUTPUT_TOKENS,
        "n": 1,
        "temperature": 0.7,
        "top_p": 0.8,
        "top_k": 20,
        "min_p": 0.0,
        "presence_penalty": 1.5,
        "repeat_penalty": 1.0,
        "seed": 42,
        "cache_prompt": False,
        "reasoning_effort": "none",
        "chat_template_kwargs": {"enable_thinking": False},
    }


def new_sample(index):
    return {
        "id": "warmup" if index == 0 else f"measured-{index}",
        "phase": "warmup" if index == 0 else "measured",
        "status": "pending",
        "classification": "timing_only",
        "task_success_evaluated": False,
        "requested_output_tokens": OUTPUT_TOKENS,
        "content": "",
        "reasoning_content": "",
        "finish_reasons": [],
        "usage": None,
        "timings": None,
        "sse_done": False,
        "events": [],
        "errors": [],
        "time_to_first_event_seconds": None,
        "time_to_first_content_seconds": None,
        "time_to_first_reasoning_seconds": None,
    }


def accept_event(sample, data, elapsed):
    if data == "[DONE]":
        sample["sse_done"] = True
        return
    try:
        event = json.loads(data, parse_constant=reject_non_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise StreamError(f"Malformed JSON SSE event: {exc}") from exc
    if not isinstance(event, dict):
        raise StreamError("SSE data must contain a JSON object")
    if len(sample["events"]) >= MAX_SSE_EVENTS:
        raise StreamError("SSE event count exceeded the bounded limit")
    sample["events"].append({"elapsed_seconds": elapsed, "data": event})
    if sample["time_to_first_event_seconds"] is None:
        sample["time_to_first_event_seconds"] = elapsed
    if event.get("error") is not None:
        raise StreamError(f"Server stream error: {event['error']}")
    if event.get("model") is not None:
        sample["served_model"] = event["model"]
    if event.get("usage") is not None:
        if not isinstance(event["usage"], dict):
            raise StreamError("SSE usage must be an object")
        sample["usage"] = event["usage"]
    if event.get("timings") is not None:
        if not isinstance(event["timings"], dict):
            raise StreamError("SSE timings must be an object")
        sample["timings"] = event["timings"]
    choices = event.get("choices", [])
    if not isinstance(choices, list):
        raise StreamError("SSE choices must be an array")
    for choice in choices:
        if not isinstance(choice, dict) or choice.get("index", 0) != 0:
            raise StreamError("Unexpected SSE choice; exactly one choice was requested")
        finish = choice.get("finish_reason")
        if finish is not None:
            sample["finish_reasons"].append(finish)
        delta = choice.get("delta") or {}
        if not isinstance(delta, dict):
            raise StreamError("SSE delta must be an object")
        if delta.get("tool_calls") or delta.get("function_call"):
            raise StreamError("Unexpected tool call in the text-only performance request")
        for field, first in (("content", "time_to_first_content_seconds"),
                             ("reasoning_content", "time_to_first_reasoning_seconds")):
            value = delta.get(field)
            if field == "reasoning_content" and value is None:
                value = delta.get("reasoning")
            if value is not None and not isinstance(value, str):
                raise StreamError(f"SSE {field} must be a string or null")
            if value:
                sample[field] += value
                if sample[first] is None:
                    sample[first] = elapsed


def finalize_sample(sample):
    usage = sample.get("usage") or {}
    timings = sample.get("timings") or {}
    count = token_count(usage.get("completion_tokens"))
    source = "usage.completion_tokens" if count is not None else None
    if count is None:
        count = token_count(timings.get("predicted_n"))
        source = "timings.predicted_n" if count is not None else None
    details = usage.get("completion_tokens_details") or {}
    reasoning_tokens = token_count(details.get("reasoning_tokens")) if isinstance(details, dict) else None
    sample["actual_completion_tokens"] = count
    sample["token_count_source"] = source
    sample["actual_reasoning_tokens"] = reasoning_tokens
    sample["actual_content_tokens"] = (count - reasoning_tokens
                                       if count is not None and reasoning_tokens is not None
                                       and reasoning_tokens <= count else None)
    sample["visible_content_characters"] = len(sample["content"])
    sample["visible_reasoning_characters"] = len(sample["reasoning_content"])
    sample["thinking_off_observed"] = not (sample["reasoning_content"]
        or "<think>" in sample["content"] or "</think>" in sample["content"]
        or (reasoning_tokens is not None and reasoning_tokens > 0))
    sample["truncated_for_timing"] = "length" in sample["finish_reasons"]
    sample["full_128_token_sample"] = count == OUTPUT_TOKENS
    wall = sample.get("wall_seconds")
    sample["end_to_end_tokens_per_second"] = count / wall if count is not None and wall else None
    # The server's timed decode count can exclude the first generated token.
    # Recomputing predicted_n / predicted_ms would silently change that definition.
    for target, source in (("server_decode_tokens_per_second", "predicted_per_second"),
                           ("server_prefill_tokens_per_second", "prompt_per_second")):
        rate = timings.get(source)
        sample[target] = rate if number(rate) and rate >= 0 else None
        sample[target + "_source"] = "timings." + source if sample[target] is not None else None
    validations = []
    if not sample["sse_done"]:
        validations.append("Missing terminal SSE [DONE]")
    if not sample["finish_reasons"] or any(f not in ("stop", "length") for f in sample["finish_reasons"]):
        validations.append("Missing or unexpected finish reason")
    if count is None or not 0 < count <= OUTPUT_TOKENS:
        validations.append("Missing, empty, or over-budget actual completion-token count")
    if not sample["content"]:
        validations.append("No visible content")
    if not sample["thinking_off_observed"]:
        validations.append("Thinking output observed despite the requested disabled mode")
    if token_count(timings.get("cache_n")) not in (None, 0):
        validations.append("Server reports reused prompt tokens despite cache_prompt=false")
    sample["validation_errors"] = validations
    sample["timing_sample_usable"] = not sample["errors"] and not validations


def read_stream(opener, endpoint, payload, sample, seconds, checkpoint):
    sample.update(status="running", started_at=utc_now())
    checkpoint()
    request = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"}, method="POST")
    # Exclude the initial disk checkpoint from request/TTFT measurements.
    started = time.monotonic()
    try:
        with wall_timeout(seconds):
            with opener.open(request, timeout=seconds) as response:
                sample["http_status"] = response.status
                sample["response_content_type"] = response.headers.get("Content-Type", "")
                if "text/event-stream" not in sample["response_content_type"].lower():
                    raise StreamError("Expected a text/event-stream response")
                data_lines, received, last_checkpoint = [], 0, time.monotonic()
                while not sample["sse_done"]:
                    line = response.readline(MAX_SSE_LINE_BYTES + 1)
                    if not line:
                        if data_lines:
                            accept_event(sample, "\n".join(data_lines), time.monotonic() - started)
                        break
                    received += len(line)
                    sample["response_bytes"] = received
                    if len(line) > MAX_SSE_LINE_BYTES or received > MAX_RESPONSE_BYTES:
                        raise StreamError("SSE response exceeded the bounded byte limit")
                    text = line.decode("utf-8").rstrip("\r\n")
                    if not text:
                        if data_lines:
                            accept_event(sample, "\n".join(data_lines), time.monotonic() - started)
                            data_lines = []
                    elif text.startswith("data:"):
                        data = text[5:]
                        data_lines.append(data[1:] if data.startswith(" ") else data)
                    # Comments, event names, IDs, and retry hints are not response data.
                    if time.monotonic() - last_checkpoint >= CHECKPOINT_INTERVAL_SECONDS:
                        sample["elapsed_seconds_so_far"] = time.monotonic() - started
                        checkpoint()
                        last_checkpoint = time.monotonic()
    except urllib.error.HTTPError as exc:
        sample["http_status"] = exc.code
        # Do not read a potentially slow/unbounded error body after leaving the wall timer.
        sample["errors"].append(f"HTTP {exc.code}: {exc.reason}")
        exc.close()
    except (DeadlineExceeded, StreamError, urllib.error.URLError, OSError, UnicodeError) as exc:
        sample["errors"].append(f"{type(exc).__name__}: {exc}")
    except (BenchmarkInterrupted, KeyboardInterrupt):
        sample["errors"].append("Benchmark interrupted during request")
        raise
    finally:
        sample["wall_seconds"] = time.monotonic() - started
        sample["finished_at"] = utc_now()
        finalize_sample(sample)
        sample["status"] = "succeeded" if sample["timing_sample_usable"] else "error"
        checkpoint()


def summarize(samples):
    measured = [s for s in samples if s["phase"] == "measured"]
    usable = [s for s in measured if s.get("timing_sample_usable")]
    summary = {"expected_measured_runs": MEASURED_RUNS, "usable_measured_runs": len(usable),
               "full_128_token_measured_runs": sum(bool(s.get("full_128_token_sample")) for s in usable),
               "task_success_evaluated": False, "statistics_exclude_warmup": True,
               "failed_or_skipped_runs_remain_in_report": True}
    for field in ("time_to_first_content_seconds", "wall_seconds",
                  "server_decode_tokens_per_second", "server_prefill_tokens_per_second",
                  "end_to_end_tokens_per_second", "actual_completion_tokens"):
        values = [s[field] for s in usable if number(s.get(field))]
        summary[field] = {"n": len(values), "mean": statistics.mean(values),
                          "median": statistics.median(values), "min": min(values), "max": max(values)} if values else None
    return summary


def summarize_saved_report(input_path, output_path):
    """Derive a corrected summary from saved evidence, without any HTTP calls."""
    if input_path.resolve() == output_path.resolve():
        raise ValueError("Summary output must differ from the original report")
    original_bytes = input_path.read_bytes()
    original = json.loads(original_bytes, parse_constant=reject_non_json_constant)
    corrected_samples, comparisons = [], []
    for saved in original["samples"]:
        # Work on a separate object; preserve the input bytes and their old metrics.
        corrected = dict(saved)
        finalize_sample(corrected)
        fields = ("id", "phase", "status", "timing_sample_usable", "actual_completion_tokens",
                  "full_128_token_sample", "truncated_for_timing", "task_success_evaluated",
                  "time_to_first_content_seconds", "wall_seconds", "end_to_end_tokens_per_second",
                  "server_decode_tokens_per_second", "server_decode_tokens_per_second_source",
                  "server_prefill_tokens_per_second", "server_prefill_tokens_per_second_source", "timings")
        corrected_samples.append({key: corrected.get(key) for key in fields})
        previous_rate = saved.get("server_decode_tokens_per_second")
        reported_rate = corrected["server_decode_tokens_per_second"]
        delta_percent = ((previous_rate / reported_rate - 1) * 100
                         if number(previous_rate) and number(reported_rate) and reported_rate > 0 else None)
        comparisons.append({"id": saved["id"], "phase": saved["phase"],
                            "original_derived_decode_tokens_per_second": previous_rate,
                            "server_reported_decode_tokens_per_second": reported_rate,
                            "original_overstatement_relative_to_server_percent": delta_percent})
    measured_deltas = [r["original_overstatement_relative_to_server_percent"] for r in comparisons
                       if r["phase"] == "measured" and number(r["original_overstatement_relative_to_server_percent"])]
    def matches_formula(sample, numerator_offset, rate):
        timings = sample.get("timings") or {}
        n, milliseconds = timings.get("predicted_n"), timings.get("predicted_ms")
        return (token_count(n) is not None and n > numerator_offset and number(milliseconds)
                and milliseconds > 0 and number(rate)
                and math.isclose(rate, (n - numerator_offset) * 1000 / milliseconds, rel_tol=1e-9))

    original_formula_matches = bool(original["samples"]) and all(
        matches_formula(s, 0, s.get("server_decode_tokens_per_second")) for s in original["samples"])
    server_formula_matches = bool(original["samples"]) and all(
        matches_formula(s, 1, (s.get("timings") or {}).get("predicted_per_second")) for s in original["samples"])
    all_128 = bool(corrected_samples) and all(s["actual_completion_tokens"] == 128 for s in corrected_samples)
    explanation = (
        "Each saved sample generated 128 tokens. The server's decode rate uses 127 timed decode tokens, "
        "with the first token accounted for in prefill. The original derived field used 128 instead, "
        "overstating the server-defined decode rate by about 0.8%. "
        if original_formula_matches and server_formula_matches and all_128 else
        "The per-sample comparison preserves the original rate field alongside the explicit server rate. "
        "A formula is identified only when all saved samples numerically match it. ")
    explanation += ("This summary uses the explicit server rates and does not alter the original report. "
                    "End-to-end throughput uses all generated tokens over the full client request duration.")
    result = {
        "schema_version": 1,
        "status": "derived_from_saved_report",
        "generated_at": utc_now(),
        "new_inference_performed": False,
        "input_report": {"filename": input_path.name,
                         "sha256": hashlib.sha256(original_bytes).hexdigest(),
                         "size_bytes": len(original_bytes),
                         "schema_version": original.get("schema_version"),
                         "status": original.get("status"),
                         "started_at": original.get("started_at"),
                         "finished_at": original.get("finished_at"),
                         "preserved_unchanged": True},
        "model_alias": original.get("request_payload", {}).get("model"),
        "prompt_sha256": original.get("prompt_sha256"),
        "classification": "timing_only",
        "task_success_evaluated": False,
        "metric_definitions": {
            "server_decode_tokens_per_second": "Saved samples[*].timings.predicted_per_second; null if absent or invalid; no inferred fallback.",
            "server_prefill_tokens_per_second": "Saved samples[*].timings.prompt_per_second; null if absent or invalid; no inferred fallback.",
            "time_to_first_content_seconds": "Saved client wall time to the first nonempty content delta; excludes role-only events.",
            "wall_seconds": "Saved client request duration, including prefill, generation, and stream reception.",
            "end_to_end_tokens_per_second": "Actual completion-token count divided by client wall_seconds; includes the full request and all generated tokens.",
        },
        "rate_correction": {
            "original_formula": "timings.predicted_n * 1000 / timings.predicted_ms" if original_formula_matches else None,
            "observed_server_formula_in_this_report": "(timings.predicted_n - 1) * 1000 / timings.predicted_ms" if server_formula_matches else None,
            "explanation": explanation,
            "measured_overstatement_percent": ({"n": len(measured_deltas),
                "median": statistics.median(measured_deltas), "min": min(measured_deltas),
                "max": max(measured_deltas)} if measured_deltas else None),
            "per_sample": comparisons,
        },
        "statistics": summarize(corrected_samples),
        "samples": corrected_samples,
        "limitations": ["One warm-up is excluded from aggregate statistics; only three measured runs are available.",
                        "All answers capped by output length are timing samples, not successful task completions.",
                        "No new inference, host-memory measurements, or service changes were performed to create this summary."],
    }
    # Check again before publishing so concurrent input changes cannot be mislabeled.
    if input_path.read_bytes() != original_bytes:
        raise ValueError("Original report changed during offline summarization")
    atomic_write(output_path, result)
    return result


def self_test():
    """Synthetic parser/measurement checks; no HTTP calls, model calls, or writes."""
    sample = new_sample(1)
    accept_event(sample, json.dumps({"choices": [{"index": 0, "delta": {"role": "assistant"}}]}), 0.1)
    accept_event(sample, json.dumps({"choices": [{"index": 0, "delta": {"content": "Audit."}}]}), 0.4)
    accept_event(sample, json.dumps({"choices": [{"index": 0, "delta": {}, "finish_reason": "length"}],
        "usage": {"completion_tokens": 128, "completion_tokens_details": {"reasoning_tokens": 0}},
        "timings": {"predicted_n": 128, "predicted_ms": 8000, "prompt_n": 700,
                    "prompt_ms": 2000, "cache_n": 0,
                    "predicted_per_second": 15.875, "prompt_per_second": 349.75}}), 10)
    accept_event(sample, "[DONE]", 10.01)
    sample["wall_seconds"] = 10.01
    finalize_sample(sample)
    assert sample["time_to_first_content_seconds"] == 0.4
    assert sample["time_to_first_event_seconds"] == 0.1
    assert sample["server_decode_tokens_per_second"] == 15.875  # Not 128 / 8 == 16.
    assert sample["server_decode_tokens_per_second_source"] == "timings.predicted_per_second"
    assert sample["server_prefill_tokens_per_second"] == 349.75  # Prefer explicit synthetic fixture.
    assert sample["server_prefill_tokens_per_second_source"] == "timings.prompt_per_second"
    assert sample["actual_content_tokens"] == 128
    assert sample["timing_sample_usable"] and sample["truncated_for_timing"]
    assert sample["task_success_evaluated"] is False
    sample["sse_done"] = False
    finalize_sample(sample)
    assert not sample["timing_sample_usable"]
    early = new_sample(2)
    accept_event(early, json.dumps({"choices": [{"delta": {"content": "Short."},
        "finish_reason": "stop"}], "usage": {"completion_tokens": 9}}), 1)
    accept_event(early, "[DONE]", 1.01)
    early["wall_seconds"] = 2
    finalize_sample(early)
    assert early["actual_completion_tokens"] == 9 and not early["full_128_token_sample"]
    assert early["end_to_end_tokens_per_second"] == 4.5
    assert early["actual_content_tokens"] is None
    # Counts and durations alone must not be mislabeled as server-reported rates.
    early["timings"] = {"predicted_n": 9, "predicted_ms": 1000, "prompt_n": 20, "prompt_ms": 100}
    finalize_sample(early)
    assert early["server_decode_tokens_per_second"] is None
    assert early["server_prefill_tokens_per_second"] is None
    assert early["server_decode_tokens_per_second_source"] is None
    bad = new_sample(3)
    try:
        accept_event(bad, "{invalid", 0)
    except StreamError:
        pass
    else:
        raise AssertionError("Malformed SSE accepted")
    assert local_base_url("http://127.0.0.1:18081/v1") == "http://127.0.0.1:18081"
    try:
        local_base_url("https://example.com")
    except argparse.ArgumentTypeError:
        pass
    else:
        raise AssertionError("Non-local URL accepted")
    class SyntheticResponse(io.BytesIO):
        status = 200
        headers = {"Content-Type": "text/event-stream; charset=utf-8"}

    class SyntheticOpener:
        def open(self, request, timeout):
            assert request.full_url == "http://127.0.0.1:18081/v1/chat/completions"
            assert json.loads(request.data)["max_tokens"] == 128
            assert timeout == 1
            return SyntheticResponse(
                b': keep-alive\n\nevent: message\n'
                b'data: {"choices": [{"delta": {"content": "Audit."},\n'
                b'data: "finish_reason": "stop"}], "usage": {"completion_tokens": 9}}\n\n'
                b'data: [DONE]\n\n')

    framed = new_sample(1)
    read_stream(SyntheticOpener(), "http://127.0.0.1:18081/v1/chat/completions",
                request_payload("synthetic-only"), framed, 1, lambda: None)
    assert framed["timing_sample_usable"] and framed["actual_completion_tokens"] == 9
    assert framed["content"] == "Audit." and framed["sse_done"]
    try:
        with wall_timeout(0.01):
            time.sleep(0.1)
    except DeadlineExceeded:
        pass
    else:
        raise AssertionError("Wall deadline did not interrupt a blocked operation")
    print("Self-test passed: SSE framing/assembly, TTFT, actual counts, server-rate preference, missing-rate handling, incomplete streams, URL bounds, and wall deadlines.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", "--base", dest="base_url", type=local_base_url,
                        default="http://127.0.0.1:18081")
    parser.add_argument("--model", default="qwen38-local-qualification")
    parser.add_argument("--out", "--output", dest="out", type=Path,
                        default=Path(__file__).resolve().parent / "qwen38-gguf-performance.json")
    parser.add_argument("--request-timeout", type=bounded_seconds(180), default=180.0)
    parser.add_argument("--total-timeout", type=bounded_seconds(900), default=900.0)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--summarize-report", type=Path,
                        help="Derive a corrected summary from saved JSON without HTTP/model calls")
    parser.add_argument("--summary-out", type=Path,
                        default=Path(__file__).resolve().parent / "qwen38-gguf-performance-summary.json")
    args = parser.parse_args(argv)
    if args.self_test:
        self_test()
        return 0
    if args.summarize_report is not None:
        try:
            summary = summarize_saved_report(args.summarize_report, args.summary_out)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            parser.error(f"Cannot summarize saved report: {exc}")
        print(json.dumps({"summary": str(args.summary_out),
                          "input_sha256": summary["input_report"]["sha256"],
                          "server_decode_tokens_per_second": summary["statistics"]["server_decode_tokens_per_second"]}), flush=True)
        return 0
    if not args.model.strip():
        parser.error("--model must not be empty")
    if not hasattr(signal, "setitimer"):
        parser.error("This bounded probe requires POSIX setitimer (available on the target Mac)")
    started = time.monotonic()
    deadline = started + args.total_timeout
    payload = request_payload(args.model)
    report = {
        "schema_version": 2,
        "started_at": utc_now(),
        "status": "running",
        "purpose": "Short local SSE timing qualification, not an agent-quality benchmark",
        "endpoint": args.base_url + "/v1/chat/completions",
        "request_payload": payload,
        "prompt_sha256": hashlib.sha256((SYSTEM_PROMPT + "\n" + USER_PROMPT).encode()).hexdigest(),
        "limits": {"warmup_requests": 1, "measured_requests": MEASURED_RUNS,
                   "max_tokens_per_request": OUTPUT_TOKENS,
                   "request_wall_seconds": args.request_timeout,
                   "total_wall_seconds": args.total_timeout,
                   "response_bytes_per_request": MAX_RESPONSE_BYTES,
                   "checkpoint_interval_seconds": CHECKPOINT_INTERVAL_SECONDS},
        "notes": ["Truncated answers are timing samples only; task success is not assessed.",
                  "Actual tokens come from server usage/timings, never word or character estimates.",
                  "Server decode/prefill rates use explicit timings.predicted_per_second/prompt_per_second; missing fields remain null, without a token/time fallback.",
                  "TTFT measures first nonempty content, excluding role-only SSE chunks.",
                  "No retry, prompt caching, model switching, tool execution, or automatic downloads.",
                  "Host memory monitoring and model/server lifecycle belong to the external controller.",
                  "Three measured trials do not establish reliable tail latency or long-run throughput."],
        "samples": [new_sample(i) for i in range(MEASURED_RUNS + 1)],
    }
    # Explicitly disable environment proxies and redirects, preserving local-only transport.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    def checkpoint():
        report["elapsed_seconds"] = time.monotonic() - started
        report["summary"] = summarize(report["samples"])
        atomic_write(args.out, report)

    def interrupted(signum, _frame):
        raise BenchmarkInterrupted(signum)

    previous_handlers = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
    exit_code = 1
    try:
        checkpoint()
        for sample in report["samples"]:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DeadlineExceeded("Total benchmark wall budget exhausted")
            read_stream(opener, report["endpoint"], payload, sample,
                        min(args.request_timeout, remaining), checkpoint)
            print(json.dumps({"sample": sample["id"], "status": sample["status"],
                              "tokens": sample["actual_completion_tokens"],
                              "ttft_seconds": sample["time_to_first_content_seconds"],
                              "decode_tokens_per_second": sample["server_decode_tokens_per_second"]}), flush=True)
            if not sample["timing_sample_usable"]:
                report["status"] = "failed"
                report["stop_reason"] = "Stopped after an unusable sample; no automatic retry"
                break
        else:
            report["status"] = "completed"
            exit_code = 0
    except (BenchmarkInterrupted, KeyboardInterrupt) as exc:
        report["status"] = "interrupted"
        report["stop_reason"] = str(exc) or "Keyboard interrupt"
        exit_code = 128 + getattr(exc, "signum", signal.SIGINT)
    except (DeadlineExceeded, OSError, ValueError) as exc:
        report["status"] = "failed"
        report["stop_reason"] = f"{type(exc).__name__}: {exc}"
    finally:
        for sample in report["samples"]:
            if sample["status"] == "pending":
                sample["status"] = "skipped"
                sample["skip_reason"] = report.get("stop_reason", "Benchmark stopped")
        report["finished_at"] = utc_now()
        try:
            checkpoint()
        finally:
            for sig, handler in previous_handlers.items():
                signal.signal(sig, handler)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
