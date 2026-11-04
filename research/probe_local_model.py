"""Bounded protocol smoke probe; no external tools or mutations are executed.

Run against an explicitly started local MTPLX server:
  python3 research/probe_local_model.py http://127.0.0.1:18080
This is research evidence, not an agent-quality benchmark.
"""

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:18080"
MODEL = "mtplx-bonsai-2-27b-optimized-speed"
OUT = Path(__file__).parent / "local-model-probe.json"
report = {"research_date": "2026-11-04", "base_url": BASE, "model": MODEL,
          "scope": "Single-seed HTTP protocol smoke checks; not SDK integration or agent quality evaluation.",
          "tests": []}


def request(path, payload=None):
    req = urllib.request.Request(
        BASE + path,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as response:
        return json.load(response)


def save():
    OUT.write_text(json.dumps(report, indent=2) + "\n")


def record(name, fn):
    started = time.monotonic()
    try:
        detail = fn()
        item = {"name": name, "ok": True, "seconds": round(time.monotonic()-started, 3), "detail": detail}
    except Exception as error:
        detail = error.read().decode() if isinstance(error, urllib.error.HTTPError) else str(error)
        item = {"name": name, "ok": False, "seconds": round(time.monotonic()-started, 3), "error": detail}
    report["tests"].append(item)
    save()
    print(json.dumps(item), flush=True)


def chat(messages, **extras):
    return {"model": MODEL, "messages": messages, "temperature": 1.0,
            "top_p": 0.95, "top_k": 20, "seed": 42, "enable_thinking": False,
            "max_tokens": 160, "stream": False, **extras}


def identity():
    health = request("/health")
    models = request("/v1/models")
    assert health.get("ok") is True
    assert MODEL in [m["id"] for m in models["data"]]
    return {"health_ok": health["ok"], "generation_mode": health.get("generation_mode"),
            "model_path": health.get("model_path"), "models": models["data"]}


TOOLS = [{"type": "function", "function": {
    "name": "add_integers", "description": "Add two integers using the test calculator.",
    "parameters": {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                   "required": ["a", "b"], "additionalProperties": False}}}]


def tool_roundtrip(choice):
    messages = [{"role": "system", "content": "Use the calculator tool when asked to add. After receiving its result, give the result briefly."},
                {"role": "user", "content": "Use add_integers to calculate 17 + 25."}]
    first = request("/v1/chat/completions", chat(messages, tools=TOOLS, tool_choice=choice, parallel_tool_calls=False))
    msg = first["choices"][0]["message"]
    calls = msg.get("tool_calls", [])
    assert len(calls) == 1, f"Expected one tool call, received {msg!r}"
    call = calls[0]
    assert call["function"]["name"] == "add_integers"
    args = json.loads(call["function"]["arguments"])
    assert args == {"a": 17, "b": 25}, args
    assert call.get("id"), "Missing tool call ID"
    # Only this fixed, harmless calculator is implemented. No model-selected code runs.
    messages += [{"role": "assistant", "content": msg.get("content"), "tool_calls": calls},
                 {"role": "tool", "tool_call_id": call["id"], "content": "42"}]
    second = request("/v1/chat/completions", chat(messages, tools=TOOLS, tool_choice="none"))
    answer = second["choices"][0]["message"].get("content", "")
    assert "42" in answer, answer
    return {"tool_choice": choice, "arguments": args, "tool_call_id": call["id"],
            "first_finish_reason": first["choices"][0].get("finish_reason"),
            "answer": answer, "usage_first": first.get("usage"), "usage_second": second.get("usage")}


def structured():
    schema = {"type": "object", "properties": {"status": {"type": "string", "enum": ["ready"]},
              "count": {"type": "integer"}}, "required": ["status", "count"], "additionalProperties": False}
    result = request("/v1/chat/completions", chat(
        [{"role": "user", "content": "Return JSON with status ready and count 3."}],
        response_format={"type": "json_schema", "json_schema": {"name": "probe", "strict": True, "schema": schema}},
    ))
    value = json.loads(result["choices"][0]["message"]["content"])
    assert value == {"status": "ready", "count": 3}, value
    return {"value": value, "finish_reason": result["choices"][0].get("finish_reason"), "usage": result.get("usage")}


def streaming():
    payload = chat([{"role": "user", "content": "Reply with the two words: local ready"}],
                   stream=True, stream_options={"include_usage": True})
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    chunks, answer, done, usage = 0, "", False, None
    with urllib.request.urlopen(req, timeout=90) as response:
        for line in response:
            text = line.decode().strip()
            if not text.startswith("data:"):
                continue
            data = text[5:].strip()
            if data == "[DONE]":
                done = True
                break
            event = json.loads(data)
            chunks += 1
            usage = event.get("usage") or usage
            for choice in event.get("choices", []):
                answer += choice.get("delta", {}).get("content") or ""
    assert done and "local ready" in answer.lower(), {"answer": answer, "done": done}
    return {"chunks": chunks, "answer": answer, "done": done, "usage": usage}


record("health_and_identity", identity)
record("automatic_tool_roundtrip", lambda: tool_roundtrip("auto"))
record("forced_tool_roundtrip", lambda: tool_roundtrip({"type": "function", "function": {"name": "add_integers"}}))
record("simple_strict_json_schema", structured)
record("text_sse_stream", streaming)
