"""Bounded, local-only llama-server protocol and fixed-task qualification probe.

No model loading, installation, external tools, shell execution, or network tools.
Start the server separately, then run (this script does not start it):
  python3 research/probe_qwen38_gguf.py --base-url http://127.0.0.1:18081

The default suite makes at most 26 HTTP requests across 15 cases. Seeds are
repetitions, not independent benchmarks. A passing protocol test does not prove
general agent quality. --self-test exercises pure validators without HTTP calls.
"""

import argparse
import contextlib
import copy
import datetime as dt
import json
import math
import signal
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


CALCULATOR_SCHEMA = {
    "type": "object",
    "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
    "required": ["a", "b"],
    "additionalProperties": False,
}
NESTED_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["ready", "blocked"]},
        "result": {
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": ["add"]},
                "operands": {"type": "array", "items": {"type": "integer"},
                             "minItems": 2, "maxItems": 2},
                "value": {"type": "integer"},
                "comment": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            },
            "required": ["operation", "operands", "value", "comment"],
            "additionalProperties": False,
        },
        "checks": {
            "type": "array", "minItems": 1, "maxItems": 1,
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string", "enum": ["sum"]},
                               "passed": {"type": "boolean"}},
                "required": ["name", "passed"], "additionalProperties": False,
            },
        },
    },
    "required": ["status", "result", "checks"],
    "additionalProperties": False,
}
NESTED_EXPECTED = {
    "status": "ready",
    "result": {"operation": "add", "operands": [17, 25], "value": 42, "comment": None},
    "checks": [{"name": "sum", "passed": True}],
}
INVOICE_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "invoice_id": {"type": "string", "enum": ["probe-001"]},
        "computed_total": {"type": "integer"},
        "verified": {"type": "boolean"},
        "plan_steps": {"type": "array", "minItems": 2, "maxItems": 2,
                       "items": {"type": "string", "enum": ["load_invoice", "verify_invoice_total"]}},
    },
    "required": ["invoice_id", "computed_total", "verified", "plan_steps"],
    "additionalProperties": False,
}


def function_tool(name, description, schema):
    return {"type": "function", "function": {
        "name": name, "description": description, "strict": True, "parameters": schema,
    }}


CALCULATOR_TOOLS = [function_tool(
    "add_integers", "The fixed probe calculator; add the supplied integers.", CALCULATOR_SCHEMA)]
INVOICE_TOOLS = [
    function_tool("load_invoice", "Load the fixed invoice before calculating or verifying it.", {
        "type": "object", "properties": {"invoice_id": {"type": "string", "enum": ["probe-001"]}},
        "required": ["invoice_id"], "additionalProperties": False,
    }),
    function_tool("verify_invoice_total", "After loading and calculating, check the computed invoice total.", {
        "type": "object",
        "properties": {"invoice_id": {"type": "string", "enum": ["probe-001"]},
                       "computed_total": {"type": "integer"}},
        "required": ["invoice_id", "computed_total"], "additionalProperties": False,
    }),
]


def schema_errors(value, schema, path="$"):
    """Validate only the documented schema subset used by this probe, fail closed.

    This is not a general JSON Schema implementation. In particular, bool is not
    an integer in JSON Schema even though it subclasses int in Python.
    """
    supported = {"type", "properties", "required", "additionalProperties", "items",
                 "minItems", "maxItems", "enum", "anyOf"}
    unknown = set(schema) - supported
    if unknown:
        raise ValueError(f"Unsupported probe schema keywords: {sorted(unknown)}")
    if "anyOf" in schema:
        if not any(not schema_errors(value, branch, path) for branch in schema["anyOf"]):
            return [f"{path}: did not match anyOf"]
    kind = schema.get("type")
    matches = {
        "object": isinstance(value, dict), "array": isinstance(value, list),
        "string": isinstance(value, str), "integer": type(value) is int,
        "number": type(value) in (int, float) and math.isfinite(value),
        "boolean": type(value) is bool, "null": value is None,
    }
    if kind is not None and kind not in matches:
        raise ValueError(f"Unsupported probe schema type: {kind!r}")
    if kind is not None and not matches[kind]:
        return [f"{path}: expected {kind}, got {type(value).__name__}"]
    errors = []
    if "enum" in schema and not any(type(value) is type(v) and value == v for v in schema["enum"]):
        errors.append(f"{path}: value outside enum")
    if kind == "object":
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}.{key}: missing required property")
        if schema.get("additionalProperties") is False:
            for key in set(value) - set(props):
                errors.append(f"{path}.{key}: additional property forbidden")
        for key, item in value.items():
            if key in props:
                errors.extend(schema_errors(item, props[key], f"{path}.{key}"))
    if kind == "array":
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: too few items")
        if len(value) > schema.get("maxItems", float("inf")):
            errors.append(f"{path}: too many items")
        for i, item in enumerate(value):
            errors.extend(schema_errors(item, schema.get("items", {}), f"{path}[{i}]"))
    return errors


def parse_json(text):
    def reject_constant(value):
        raise ValueError(f"Non-JSON numeric constant: {value}")

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON property: {key}")
            result[key] = value
        return result

    return json.loads(text, parse_constant=reject_constant, object_pairs_hook=unique_object)


def sanitized(value):
    """Retain full evidence while masking credential fields and the local home."""
    sensitive = {"authorization", "api_key", "apikey", "access_token", "refresh_token",
                 "password", "secret", "cookie", "set-cookie"}
    if isinstance(value, dict):
        return {str(k): "[REDACTED]" if str(k).lower() in sensitive else sanitized(v)
                for k, v in value.items()}
    if isinstance(value, list):
        return [sanitized(v) for v in value]
    if isinstance(value, str):
        return value.replace(str(Path.home()), "~")
    return value


class ProbeTimeout(Exception):
    pass


class BudgetExceeded(Exception):
    pass


class CheckFailure(Exception):
    pass


@contextlib.contextmanager
def wall_timeout(seconds):
    """Hard wall deadline, including trickling SSE; supported on the target Mac."""
    def alarm_handler(_signum, _frame):
        raise ProbeTimeout(f"HTTP request exceeded {seconds:.3f}s wall deadline")

    previous = signal.signal(signal.SIGALRM, alarm_handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def assemble_sse(events):
    """Assemble OpenAI deltas by tool index; retain errors instead of guessing."""
    text, reasoning, calls, finishes, usage, errors = "", "", {}, [], None, []
    for event in events:
        if not isinstance(event, dict):
            errors.append("Non-object SSE event")
            continue
        if event.get("usage") is not None:
            usage = event["usage"]
        if "error" in event:
            errors.append(f"Server stream error: {event['error']}")
        for choice in event.get("choices", []):
            if choice.get("index", 0) != 0:
                errors.append("Unexpected choice index")
                continue
            if choice.get("finish_reason") is not None:
                finishes.append(choice["finish_reason"])
            delta = choice.get("delta", {})
            text += delta.get("content") or ""
            reasoning += delta.get("reasoning_content") or delta.get("reasoning") or ""
            for fragment in delta.get("tool_calls") or []:
                index = fragment.get("index")
                if type(index) is not int or index < 0:
                    errors.append("Tool delta lacks a nonnegative integer index")
                    continue
                call = calls.setdefault(index, {"id": "", "type": "function",
                                               "function": {"name": "", "arguments": ""}})
                call["id"] += fragment.get("id") or ""
                if fragment.get("type") not in (None, "function"):
                    errors.append("Unexpected tool delta type")
                for key in ("name", "arguments"):
                    call["function"][key] += (fragment.get("function") or {}).get(key) or ""
    return {"message": {"role": "assistant", "content": text,
                         "tool_calls": [calls[i] for i in sorted(calls)]},
            "reasoning_content": reasoning, "finish_reasons": finishes,
            "usage": usage, "assembly_errors": errors}


class Probe:
    def __init__(self, args):
        self.args = args
        self.model = args.model
        self.started = time.monotonic()
        self.deadline = self.started + args.total_timeout
        self.current = None
        self.report = {
            "started_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "base_url": args.base_url, "requested_model": args.model,
            "scope": "Three-seed protocol qualification and one fixed two-hop task; not general agent benchmarking.",
            "configuration": {"seeds": [42, 43, 44], "per_request_timeout_seconds": args.timeout,
                              "total_timeout_seconds": args.total_timeout, "max_response_bytes": args.max_response_bytes,
                              "thinking": "chat_template_kwargs.enable_thinking=false", "temperature": 1.0,
                              "max_output_tokens": {"tools_and_text": 256, "schema_and_final": 512, "negative": 1}},
            "limitations": ["Server identity is reported; this probe does not independently fingerprint loaded weights.",
                            "Native parsing, constrained decoding, and semantic quality are distinct checks.",
                            "Three seeds are a small repetition set, not confidence intervals.",
                            "Only fixed arithmetic and invoice fixtures execute locally; no model-selected code executes."],
            "requests": [], "tests": [],
        }

    def save(self):
        tests = self.report["tests"]
        requests = self.report["requests"]
        self.report["totals"] = {
            "cases_recorded": len(tests),
            "passed": sum(t["status"] == "pass" for t in tests),
            "failed": sum(t["status"] == "fail" for t in tests),
            "skipped": sum(t["status"] == "skipped" for t in tests),
            "protocol_failures": sum(t.get("protocol_ok") is False for t in tests),
            "semantic_failures": sum(t.get("semantic_ok") is False for t in tests),
            "http_requests": len(requests),
            "elapsed_seconds": round(time.monotonic() - self.started, 3),
            "usage": {key: sum(r.get("usage", {}).get(key, 0) or 0 for r in requests)
                      for key in ("prompt_tokens", "completion_tokens", "total_tokens")},
        }
        self.args.out.parent.mkdir(parents=True, exist_ok=True)
        self.args.out.write_text(json.dumps(sanitized(self.report), indent=2, ensure_ascii=False) + "\n")

    def check(self, dimension, name, ok, detail=None):
        row = {"dimension": dimension, "name": name, "ok": bool(ok)}
        if detail is not None:
            row["detail"] = detail
        self.current["checks"].append(row)
        if not ok:
            raise CheckFailure(f"{dimension}: {name}")

    def case(self, name, fn, seed=None):
        started = time.monotonic()
        self.current = {"name": name, "seed": seed, "checks": [], "request_ids": []}
        try:
            if started >= self.deadline:
                raise BudgetExceeded("Total probe deadline reached; no request sent")
            self.current["detail"] = fn()
            self.current["status"] = "pass"
        except BudgetExceeded as error:
            self.current.update(status="skipped", error=str(error))
        except Exception as error:
            self.current.update(status="fail", error_type=type(error).__name__, error=str(error))
            if not isinstance(error, CheckFailure):
                self.current["checks"].append({"dimension": "protocol", "name": "request_or_parse_error", "ok": False})
        for dimension in ("protocol", "semantic"):
            checks = [c["ok"] for c in self.current["checks"] if c["dimension"] == dimension]
            self.current[f"{dimension}_ok"] = all(checks) if checks else None
        self.current["seconds"] = round(time.monotonic() - started, 3)
        self.current["ok"] = self.current["status"] == "pass"
        self.report["tests"].append(self.current)
        self.save()
        print(json.dumps({k: self.current[k] for k in ("name", "seed", "status", "protocol_ok", "semantic_ok", "seconds")}), flush=True)

    def request(self, path, payload=None, stream=False):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise BudgetExceeded("Total probe deadline reached; no request sent")
        allowance = min(self.args.timeout, remaining)
        item = {"id": len(self.report["requests"]) + 1, "path": path,
                "method": "GET" if payload is None else "POST", "payload": copy.deepcopy(payload),
                "started_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "wall_timeout_seconds": round(allowance, 3)}
        self.report["requests"].append(item)
        self.current["request_ids"].append(item["id"])
        started = time.monotonic()
        req = urllib.request.Request(self.args.base_url + path,
                                     data=None if payload is None else json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with wall_timeout(allowance):
                try:
                    response = urllib.request.urlopen(req, timeout=allowance)
                except urllib.error.HTTPError as error:
                    raw = error.read(self.args.max_response_bytes + 1).decode("utf-8", errors="replace")
                    item.update(http_status=error.code, response_body=raw)
                    raise RuntimeError(f"HTTP {error.code}: {raw[:500]}") from error
                with response:
                    item["http_status"] = response.status
                    item["content_type"] = response.headers.get("Content-Type")
                    if stream:
                        events, data_lines, done, received = [], [], False, 0
                        item["sse_events"] = events
                        item["sse_done"] = False
                        while True:
                            line = response.readline(self.args.max_response_bytes + 1)
                            received += len(line)
                            if received > self.args.max_response_bytes:
                                raise ValueError("SSE response exceeded byte limit")
                            if not line:
                                break
                            decoded = line.decode("utf-8").rstrip("\r\n")
                            if decoded.startswith("data:"):
                                data_lines.append(decoded[5:].lstrip(" "))
                            if decoded == "" and data_lines:
                                data = "\n".join(data_lines)
                                data_lines = []
                                if data == "[DONE]":
                                    done = True
                                    break
                                try:
                                    events.append(parse_json(data))
                                except ValueError:
                                    item["malformed_sse_data"] = data
                                    raise
                        if data_lines:
                            item["unterminated_sse_data"] = "\n".join(data_lines)
                        result = assemble_sse(events)
                        result["done"] = done
                        item.update(sse_done=done, assembled=result, usage=result.get("usage") or {})
                    else:
                        raw = response.read(self.args.max_response_bytes + 1)
                        if len(raw) > self.args.max_response_bytes:
                            raise ValueError("Response exceeded byte limit")
                        item["response_body"] = raw.decode("utf-8")
                        result = parse_json(item["response_body"])
                        item["response"] = result
                        item["usage"] = (result.get("usage") or {}) if isinstance(result, dict) else {}
                        item["finish_reasons"] = [c.get("finish_reason") for c in result.get("choices", [])] if isinstance(result, dict) else []
                    return result
        except Exception as error:
            item.update(error_type=type(error).__name__, error=str(error))
            raise
        finally:
            item["seconds"] = round(time.monotonic() - started, 3)
            self.save()

    def chat(self, messages, seed=42, **extra):
        if not self.model:
            raise RuntimeError("No verified model identity; generation was not attempted")
        return {"model": self.model, "messages": messages, "seed": seed,
                "temperature": 1.0, "top_p": 0.95, "top_k": 20,
                "min_p": 0.0, "presence_penalty": 0.0, "repeat_penalty": 1.0,
                "chat_template_kwargs": {"enable_thinking": False},
                "max_tokens": 256, "stream": False, **extra}

    def message(self, response, expected_finish="stop"):
        choices = response.get("choices", [])
        self.check("protocol", "exactly_one_choice", len(choices) == 1)
        self.check("protocol", "finish_reason", choices[0].get("finish_reason") == expected_finish,
                   choices[0].get("finish_reason"))
        message = choices[0].get("message", {})
        self.check("protocol", "assistant_message", message.get("role") == "assistant")
        return message

    def inspect_tool(self, message, tools):
        calls = message.get("tool_calls") or []
        self.check("protocol", "exactly_one_tool_call", len(calls) == 1)
        call = calls[0]
        self.check("protocol", "tool_call_id", isinstance(call.get("id"), str) and bool(call["id"].strip()))
        self.check("protocol", "function_tool_type", call.get("type") == "function")
        function = call.get("function", {})
        definitions = {t["function"]["name"]: t["function"] for t in tools}
        name = function.get("name")
        self.check("protocol", "registered_function", name in definitions, name)
        self.check("protocol", "arguments_are_json_string", isinstance(function.get("arguments"), str))
        arguments = parse_json(function["arguments"])
        errors = schema_errors(arguments, definitions[name]["parameters"])
        self.check("protocol", "tool_argument_schema", not errors, errors)
        return call, name, arguments

    def identity(self):
        health = self.request("/health")
        self.check("protocol", "health_ready", health.get("status") == "ok" or health.get("ok") is True, health)
        models = self.request("/v1/models")
        ids = [m.get("id") for m in models.get("data", [])]
        if self.model is None:
            self.check("protocol", "unambiguous_model_identity", len(ids) == 1 and isinstance(ids[0], str), ids)
            self.model = ids[0]
        self.check("protocol", "requested_model_listed", self.model in ids, ids)
        self.report["served_model"] = self.model
        return {"health": health, "models": models}

    def calculator(self, choice, seed, streaming=False):
        messages = [{"role": "system", "content": "Use the calculator when asked. After its result, reply with exactly the decimal answer and nothing else."},
                    {"role": "user", "content": "Use add_integers to calculate 17 + 25."}]
        payload = self.chat(messages, seed, tools=CALCULATOR_TOOLS, tool_choice=choice, parallel_tool_calls=False)
        if streaming:
            payload.update(stream=True, stream_options={"include_usage": True})
            result = self.request("/v1/chat/completions", payload, stream=True)
            self.check("protocol", "sse_done", result["done"])
            self.check("protocol", "sse_assembly", not result["assembly_errors"], result["assembly_errors"])
            self.check("protocol", "sse_tool_finish", result["finish_reasons"] == ["tool_calls"], result["finish_reasons"])
            self.check("protocol", "sse_usage", isinstance(result.get("usage"), dict), result.get("usage"))
            message = result["message"]
        else:
            message = self.message(self.request("/v1/chat/completions", payload), "tool_calls")
        call, name, arguments = self.inspect_tool(message, CALCULATOR_TOOLS)
        self.check("semantic", "correct_calculator_and_operands", name == "add_integers" and arguments == {"a": 17, "b": 25}, arguments)
        # Only the validated, fixed arithmetic fixture executes. No arbitrary dispatch.
        messages.extend([{"role": "assistant", "content": message.get("content"), "tool_calls": [call]},
                         {"role": "tool", "tool_call_id": call["id"], "content": "42"}])
        final = self.message(self.request("/v1/chat/completions", self.chat(
            messages, seed, tools=CALCULATOR_TOOLS, tool_choice="none", parallel_tool_calls=False)))
        self.check("protocol", "no_tool_after_none", not final.get("tool_calls"))
        self.check("semantic", "tool_result_answer_42", (final.get("content") or "").strip() == "42", final.get("content"))
        return {"tool_choice": choice, "tool_call_id": call["id"], "arguments": arguments, "answer": final.get("content")}

    def structured(self, seed, truncated=False):
        payload = self.chat(
            [{"role": "user", "content": "Return exactly this JSON value, without Markdown: " + json.dumps(NESTED_EXPECTED)}], seed,
            max_tokens=1 if truncated else 512,
            response_format={"type": "json_schema", "json_schema": {"name": "nested_probe", "strict": True, "schema": NESTED_SCHEMA}})
        result = self.request("/v1/chat/completions", payload)
        message = self.message(result, "length" if truncated else "stop")
        content = message.get("content")
        self.check("protocol", "json_content_string", isinstance(content, str), content)
        try:
            value = parse_json(content)
            errors = schema_errors(value, NESTED_SCHEMA)
        except ValueError as error:
            value, errors = None, [str(error)]
        if truncated:
            self.check("protocol", "truncated_output_rejected", bool(errors), {"content": content, "errors": errors})
            return {"expected_negative": True, "accepted_as_complete": False, "validation_errors": errors}
        self.check("protocol", "strict_nested_schema", not errors, errors)
        self.check("semantic", "requested_nested_values", value == NESTED_EXPECTED, value)
        return {"value": value}

    def text_stream(self):
        result = self.request("/v1/chat/completions", self.chat(
            [{"role": "user", "content": "Reply with exactly these two words: local ready"}],
            stream=True, stream_options={"include_usage": True}), stream=True)
        self.check("protocol", "sse_done", result["done"])
        self.check("protocol", "sse_assembly", not result["assembly_errors"], result["assembly_errors"])
        self.check("protocol", "sse_stop", result["finish_reasons"] == ["stop"], result["finish_reasons"])
        self.check("protocol", "sse_usage", isinstance(result.get("usage"), dict), result.get("usage"))
        self.check("protocol", "text_stream_no_tool", not result["message"].get("tool_calls"))
        self.check("semantic", "exact_streamed_text", result["message"]["content"].strip() == "local ready", result["message"]["content"])
        return result

    def two_hop_task(self):
        messages = [{"role": "system", "content": "You perform a fixed invoice audit. First load the invoice, then calculate quantity times unit_price and sum, then verify the total with the verification tool. Never verify before loading. Use one tool per turn. Only after verification, return the final JSON with invoice_id, computed_total, verified, and plan_steps listing the two tool names in order."},
                    {"role": "user", "content": "Audit invoice probe-001 using the tools. Return the verified total."}]
        hops = []
        expected = [("load_invoice", {"invoice_id": "probe-001"},
                     {"invoice_id": "probe-001", "currency": "USD", "items": [{"qty": 2, "unit_price": 9}, {"qty": 3, "unit_price": 8}]}),
                    ("verify_invoice_total", {"invoice_id": "probe-001", "computed_total": 42},
                     {"invoice_id": "probe-001", "expected_total": 42, "verified": True})]
        for name_expected, args_expected, fixture in expected:
            message = self.message(self.request("/v1/chat/completions", self.chat(
                messages, tools=INVOICE_TOOLS, tool_choice="auto", parallel_tool_calls=False)), "tool_calls")
            call, name, arguments = self.inspect_tool(message, INVOICE_TOOLS)
            self.check("semantic", "correct_next_step", name == name_expected, {"expected": name_expected, "actual": name})
            self.check("semantic", "correct_step_arguments", arguments == args_expected, arguments)
            self.check("protocol", "distinct_tool_call_id", call["id"] not in [h["tool_call_id"] for h in hops], call["id"])
            hops.append({"name": name, "arguments": arguments, "tool_call_id": call["id"], "fixture_result": fixture})
            messages.extend([{"role": "assistant", "content": message.get("content"), "tool_calls": [call]},
                             {"role": "tool", "tool_call_id": call["id"], "content": json.dumps(fixture)}])
        # A hard two-hop bound: no third tool request is allowed.
        message = self.message(self.request("/v1/chat/completions", self.chat(
            messages, max_tokens=512, tools=INVOICE_TOOLS, tool_choice="none", parallel_tool_calls=False,
            response_format={"type": "json_schema", "json_schema": {"name": "audit_result", "strict": True, "schema": INVOICE_RESULT_SCHEMA}})))
        self.check("protocol", "final_no_more_tools", not message.get("tool_calls"))
        value = parse_json(message.get("content", ""))
        errors = schema_errors(value, INVOICE_RESULT_SCHEMA)
        self.check("protocol", "final_audit_schema", not errors, errors)
        expected_result = {"invoice_id": "probe-001", "computed_total": 42, "verified": True,
                           "plan_steps": ["load_invoice", "verify_invoice_total"]}
        self.check("semantic", "correct_verified_audit", value == expected_result, value)
        return {"hops": hops, "result": value, "planning_observation": "Visible tool ordering only; no hidden reasoning quality claim."}

    def run(self):
        named = {"type": "function", "function": {"name": "add_integers"}}
        self.case("health_and_identity", self.identity)
        if not self.report["tests"][-1]["ok"]:
            self.report["aborted_reason"] = "Identity check failed; no generation requests attempted."
            self.save()
            return 1
        # Probe native named-choice compatibility once. Some llama-server builds
        # reject object-form named choice; that remains an explicit failure.
        # Repeated required + one allowed tool is a separate adapter alternative.
        self.case("native_named_strict_tool_roundtrip", lambda: self.calculator(named, 42), 42)
        for seed in (42, 43, 44):
            for name, choice in (("automatic", "auto"), ("required_single_allowed_tool", "required")):
                self.case(f"{name}_strict_tool_roundtrip", lambda c=choice, s=seed: self.calculator(c, s), seed)
            self.case("nested_strict_json_schema", lambda s=seed: self.structured(s), seed)
        self.case("text_sse_stream", self.text_stream, 42)
        self.case("required_single_tool_sse_roundtrip", lambda: self.calculator("required", 42, streaming=True), 42)
        self.case("truncated_json_is_rejected", lambda: self.structured(42, truncated=True), 42)
        self.case("bounded_two_hop_invoice_audit", self.two_hop_task, 42)
        self.report["finished_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
        self.save()
        print(json.dumps({"output": str(self.args.out), "totals": self.report["totals"]}), flush=True)
        return 0 if all(t["ok"] for t in self.report["tests"]) else 1


def self_test():
    assert not schema_errors(NESTED_EXPECTED, NESTED_SCHEMA)
    bad_values = []
    for key, replacement in (("value", True), ("operation", "multiply"), ("operands", [17]), ("comment", 3)):
        bad = copy.deepcopy(NESTED_EXPECTED)
        bad["result"][key] = replacement
        bad_values.append(bad)
    bad = copy.deepcopy(NESTED_EXPECTED)
    bad["result"]["extra"] = "forbidden"
    bad_values.append(bad)
    for bad in bad_values:
        assert schema_errors(bad, NESTED_SCHEMA), bad
    for text in ('{"status":', '{"x":1,"x":2}', '{"x":NaN}'):
        try:
            parse_json(text)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Invalid JSON accepted: {text}")
    assembled = assemble_sse([
        {"choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0, "id": "call_1", "type": "function", "function": {"name": "add_", "arguments": '{"a":'}}]}}]},
        {"choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0, "function": {"name": "integers", "arguments": '17,"b":25}'}}]}}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}], "usage": {"total_tokens": 10}},
    ])
    call = assembled["message"]["tool_calls"][0]
    assert call["id"] == "call_1" and call["function"]["name"] == "add_integers"
    assert parse_json(call["function"]["arguments"]) == {"a": 17, "b": 25}
    assert assembled["finish_reasons"] == ["tool_calls"] and not assembled["assembly_errors"]
    assert assemble_sse([{"choices": [{"delta": {"tool_calls": [{"function": {"name": "x"}}]}}]}])["assembly_errors"]
    print("Pure validation and split-SSE assembly checks passed; no HTTP calls made.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://127.0.0.1:18081", help="Loopback llama-server origin, optionally ending /v1")
    parser.add_argument("--model", help="Expected served model ID; otherwise require exactly one /v1/models result")
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("qwen38-gguf-probe.json"))
    parser.add_argument("--timeout", type=float, default=180, help="Hard wall seconds per request, maximum 180")
    parser.add_argument("--total-timeout", type=float, default=1800, help="Whole-suite wall budget in seconds")
    parser.add_argument("--max-response-bytes", type=int, default=8 * 1024 * 1024)
    parser.add_argument("--self-test", action="store_true", help="Pure helper checks; no HTTP calls or report writes")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    parsed = urllib.parse.urlsplit(args.base_url)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
        parser.error("--base-url must use HTTP(S) on a loopback host")
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path.rstrip("/") not in ("", "/v1"):
        parser.error("--base-url must be a credential-free origin, optionally ending /v1")
    args.base_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    if not 0 < args.timeout <= 180 or not math.isfinite(args.timeout):
        parser.error("--timeout must be greater than 0 and at most 180")
    if not math.isfinite(args.total_timeout) or args.total_timeout <= 0:
        parser.error("--total-timeout must be positive and finite")
    if args.max_response_bytes < 1024:
        parser.error("--max-response-bytes must be at least 1024")
    if not hasattr(signal, "setitimer"):
        parser.error("This probe requires POSIX setitimer for hard wall deadlines")
    return Probe(args).run()


if __name__ == "__main__":
    raise SystemExit(main())
