"""Serve one GGUF model with llama-server on 127.0.0.1 and measure it by hand (Decision 0041 A15).

Usage: python3.12 -I research/probe_llama_server.py <bonsai|inkling> <gguf> <out_dir> [--context N] [--only protocol|speed]

The protocol probes check what the gateway needs, after US-3.4's capabilities: plain text, automatic and required
tool calls, a tool result answered, a choice between two tools, JSON-schema output, streaming with usage, and
thinking switched off and on. The speed probes read llama-server's own timings at about 8K, 32K and 62K prompt
tokens, a repeated prefix that the prompt cache should serve, and a decode run. Memory is the server's peak
footprint, sampled every two seconds, with swap read before and after. Nothing leaves 127.0.0.1, and the long
prompts are synthetic sentences from a fixed word list.
"""
from __future__ import annotations

import json
import random
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

PORT = 9931
BASE = f"http://127.0.0.1:{PORT}"

# Each card's sampling, and how a request switches thinking: Bonsai's template takes enable_thinking, and
# Inkling's takes reasoning_effort, whose minimum doesn't fully turn reasoning off (its model card).
MODELS = {
    "bonsai": {
        "server": ["--temp", "0.7", "--top-p", "0.8", "--top-k", "20", "--min-p", "0", "--presence-penalty", "1.5"],
        "think_off": {"chat_template_kwargs": {"enable_thinking": False}},
        "think_on": {"chat_template_kwargs": {"enable_thinking": True}},
    },
    "inkling": {
        "server": ["--temp", "1.0", "--min-p", "0"],
        "think_off": {"chat_template_kwargs": {"reasoning_effort": "none"}},
        "think_on": {"chat_template_kwargs": {"reasoning_effort": "medium"}},
    },
}

CALCULATE = {"type": "function", "function": {
    "name": "calculate", "description": "Evaluate an arithmetic expression and return the number.",
    "parameters": {"type": "object", "properties": {"expression": {"type": "string"}},
                   "required": ["expression"], "additionalProperties": False}}}
MARKET = {"type": "function", "function": {
    "name": "market_history", "description": "Read the latest daily closes for a market symbol such as BZ=F.",
    "parameters": {"type": "object", "properties": {"symbol": {"type": "string"}, "days": {"type": "integer"}},
                   "required": ["symbol"], "additionalProperties": False}}}
WORDS = ("river harbor ledger orchard signal lantern meadow archive compass quarry beacon granite willow "
         "market ferry canyon thicket mill furnace pasture vessel tide summit hollow garden bridge forge").split()


def post(path: str, body: dict, timeout: float = 1800) -> tuple[dict, float]:
    request = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read())
    return payload, time.monotonic() - started


def get(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=30) as response:
        return json.loads(response.read())


def chat(messages: list, extra: dict, **options) -> tuple[dict, float]:
    return post("/v1/chat/completions", {"model": "local", "messages": messages, **options, **extra})


def stream(messages: list, extra: dict) -> dict:
    body = {"model": "local", "messages": messages, "stream": True, "max_tokens": 64,
            "stream_options": {"include_usage": True}, **extra}
    request = urllib.request.Request(BASE + "/v1/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
    started, first, chunks, usage, text = time.monotonic(), None, 0, None, ""
    with urllib.request.urlopen(request, timeout=600) as response:
        for raw in response:
            line = raw.decode().strip()
            if not line.startswith("data: ") or line == "data: [DONE]":
                continue
            chunk = json.loads(line[6:])
            usage = chunk.get("usage") or usage
            for choice in chunk.get("choices") or []:
                piece = (choice.get("delta") or {}).get("content")
                if piece:
                    first = first or time.monotonic()
                    chunks += 1
                    text += piece
    return {"chunks": chunks, "first_content_s": round((first or time.monotonic()) - started, 2),
            "usage_in_last_chunk": usage is not None, "text": text[:200]}


def tool_call(payload: dict) -> dict | None:
    calls = payload["choices"][0]["message"].get("tool_calls") or []
    if not calls:
        return None
    function = calls[0]["function"]
    try:
        arguments = json.loads(function["arguments"])
    except (TypeError, json.JSONDecodeError):
        arguments = None
    return {"id": calls[0].get("id"), "name": function.get("name"), "arguments": arguments}


def summary(payload: dict, seconds: float) -> dict:
    message = payload["choices"][0]["message"]
    timings = payload.get("timings") or {}
    return {"seconds": round(seconds, 2), "finish": payload["choices"][0].get("finish_reason"),
            "content": (message.get("content") or "")[:600],
            "reasoning_chars": len(message.get("reasoning_content") or ""), "usage": payload.get("usage"),
            "prompt_n": timings.get("prompt_n"), "prompt_per_s": round(timings.get("prompt_per_second") or 0, 1),
            "predicted_n": timings.get("predicted_n"),
            "predicted_per_s": round(timings.get("predicted_per_second") or 0, 1)}


def protocol(off: dict, on: dict) -> dict:
    results: dict = {}
    payload, seconds = chat([{"role": "user", "content": "Reply with the single word: ready"}], off, max_tokens=32)
    content = payload["choices"][0]["message"].get("content") or ""
    results["plain"] = {**summary(payload, seconds), "pass": "ready" in content.lower()}

    ask = [{"role": "user", "content": "Use the calculate tool to compute 840 * 0.125. Do not compute it yourself."}]
    payload, seconds = chat(ask, off, tools=[CALCULATE], tool_choice="auto", max_tokens=512)
    call = tool_call(payload)
    results["tool_auto"] = {"seconds": round(seconds, 2), "call": call,
                            "pass": bool(call and call["name"] == "calculate" and isinstance(call["arguments"], dict)
                                         and "expression" in call["arguments"])}

    payload, seconds = chat([{"role": "user", "content": "What is 17 + 25?"}], off, tools=[CALCULATE],
                            tool_choice="required", max_tokens=512)
    required = tool_call(payload)
    results["tool_required"] = {"seconds": round(seconds, 2), "call": required,
                                "pass": bool(required and required["name"] == "calculate")}

    if call:
        call_id = call["id"] or "call_1"
        followed = ask + [
            {"role": "assistant", "content": None, "tool_calls": [{"id": call_id, "type": "function",
             "function": {"name": "calculate", "arguments": json.dumps(call["arguments"])}}]},
            {"role": "tool", "tool_call_id": call_id, "content": "105"}]
        payload, seconds = chat(followed, off, tools=[CALCULATE], max_tokens=256)
        content = payload["choices"][0]["message"].get("content") or ""
        results["tool_result_answered"] = {**summary(payload, seconds), "pass": "105" in content}

    payload, seconds = chat([{"role": "user", "content": "What was Brent crude's last close? Use one tool."}], off,
                            tools=[CALCULATE, MARKET], tool_choice="auto", max_tokens=512)
    chosen = tool_call(payload)
    results["tool_choice_between_two"] = {"seconds": round(seconds, 2), "call": chosen,
                                          "pass": bool(chosen and chosen["name"] == "market_history")}

    schema = {"type": "object", "properties": {"city": {"type": "string"}, "population": {"type": "integer"}},
              "required": ["city", "population"], "additionalProperties": False}
    payload, seconds = chat(
        [{"role": "user", "content": "Name the capital of Costa Rica and its approximate population."}], off,
        max_tokens=256, response_format={"type": "json_schema",
                                         "json_schema": {"name": "capital", "strict": True, "schema": schema}})
    content = payload["choices"][0]["message"].get("content") or ""
    try:
        parsed = json.loads(content)
        valid = (isinstance(parsed, dict) and set(parsed) == {"city", "population"}
                 and isinstance(parsed["city"], str) and isinstance(parsed["population"], int))
    except json.JSONDecodeError:
        parsed, valid = None, False
    results["json_schema"] = {**summary(payload, seconds), "parsed": parsed, "pass": valid}

    streamed = stream([{"role": "user", "content": "Count from one to ten in words."}], off)
    results["stream"] = {**streamed, "pass": streamed["chunks"] > 1 and streamed["usage_in_last_chunk"]}

    question = [{"role": "user", "content": "Is 1,234,567 divisible by 3? Answer yes or no, with one sentence why."}]
    payload, seconds = chat(question, off, max_tokens=4096)
    results["thinking_off"] = summary(payload, seconds)
    payload, seconds = chat(question, on, max_tokens=4096)
    results["thinking_on"] = summary(payload, seconds)

    spanish = [{"role": "user", "content": "Escribí un párrafo corto, en español de Costa Rica, que le explique a "
                "un lector qué significa que el colón se aprecie frente al dólar."}]
    payload, seconds = chat(spanish, off, max_tokens=400)
    results["spanish_for_the_owner"] = summary(payload, seconds)
    return results


def filler(tokens: int) -> str:
    """Synthetic sentences cut to about `tokens`, counted by the server's own tokenizer."""
    rng = random.Random(41)
    sentences: list[str] = []
    while True:
        sentences.extend(" ".join(rng.choice(WORDS) for _ in range(12)).capitalize() + "." for _ in range(400))
        text = " ".join(sentences)
        count = len(post("/tokenize", {"content": text})[0]["tokens"])
        if count >= tokens:
            return text[: int(len(text) * tokens / count)]


def speed(off: dict, context: int) -> dict:
    results: dict = {}
    for label, size in (("8k", 8000), ("32k", 32000), ("62k", 62000)):
        if size > context - 2000:
            continue
        body = filler(size)
        prompt = [{"role": "user", "content": body + "\n\nIn one sentence, which words repeat most in this text?"}]
        payload, seconds = chat(prompt, off, max_tokens=128)
        results[f"prompt_{label}"] = summary(payload, seconds)
        if label == "32k":
            again = [{"role": "user", "content": body + "\n\nIn one sentence, name three words from this text."}]
            payload, seconds = chat(again, off, max_tokens=128)
            results["prompt_32k_cache_hit"] = summary(payload, seconds)
    payload, seconds = chat([{"role": "user", "content": "Write about 400 words on how a river shapes a valley."}],
                            off, max_tokens=600)
    results["decode_short_context"] = summary(payload, seconds)
    return results


def footprint_mb(pid: int) -> float:
    out = subprocess.run(["/usr/bin/footprint", str(pid)], capture_output=True, text=True).stdout
    match = re.search(r"Footprint:\s+([\d.]+)\s+(KB|MB|GB)", out)
    return float(match.group(1)) * {"KB": 1 / 1024, "MB": 1, "GB": 1024}[match.group(2)] if match else 0.0


def swap_used_mb() -> float:
    out = subprocess.run(["sysctl", "-n", "vm.swapusage"], capture_output=True, text=True).stdout
    match = re.search(r"used = ([\d.]+)M", out)
    return float(match.group(1)) if match else -1.0


def wait_ready(server: subprocess.Popen, started: float) -> str | None:
    while True:
        if server.poll() is not None:
            return f"llama-server exited with {server.returncode} while loading"
        try:
            if get("/health").get("status") == "ok":
                return None
        except (urllib.error.URLError, ConnectionError, json.JSONDecodeError):
            pass
        if time.monotonic() - started > 900:
            return "not ready in 900 seconds"
        time.sleep(2)


def finish(report: dict, out_dir: Path, tag: str, code: int) -> int:
    (out_dir / f"{tag}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    passed = {k: v.get("pass") for k, v in (report.get("protocol") or {}).items() if isinstance(v, dict) and "pass" in v}
    print(json.dumps({"model": report["model"], "error": report.get("error"), "load_seconds": report.get("load_seconds"),
                      "served": report.get("served_models"), "pass": passed,
                      "peak_footprint_mb": report.get("peak_footprint_mb"),
                      "swap_mb": [report.get("swap_used_mb_before"), report.get("swap_used_mb_after")]},
                     ensure_ascii=False))
    return code


def main() -> int:
    name, gguf, out_dir = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    context = int(sys.argv[sys.argv.index("--context") + 1]) if "--context" in sys.argv else 65536
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else "all"
    config = MODELS[name]
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"{name}-{only}-{context // 1024}k"
    command = ["llama-server", "-m", gguf, "--host", "127.0.0.1", "--port", str(PORT), "-c", str(context),
               "-np", "1", "-fa", "on", "-ngl", "99", "--jinja", "--reasoning-format", "deepseek",
               "--alias", name, *config["server"]]
    version = subprocess.run(["llama-server", "--version"], capture_output=True, text=True)
    report: dict = {"model": name, "gguf": gguf, "context": context, "command": command,
                    "llama_server": (version.stdout + version.stderr).strip().splitlines()[0],
                    "swap_used_mb_before": swap_used_mb()}
    started = time.monotonic()
    log_path = out_dir / f"{tag}.log"
    with log_path.open("w") as log:
        server = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        peak = {"mb": 0.0}
        stop = threading.Event()

        def sample() -> None:
            while not stop.is_set():
                peak["mb"] = max(peak["mb"], footprint_mb(server.pid))
                stop.wait(2)

        threading.Thread(target=sample, daemon=True).start()
        try:
            problem = wait_ready(server, started)
            if problem:
                report["error"] = problem
            else:
                report["load_seconds"] = round(time.monotonic() - started, 1)
                report["served_models"] = [item.get("id") for item in get("/v1/models").get("data", [])]
                if only in ("all", "protocol"):
                    report["protocol"] = protocol(config["think_off"], config["think_on"])
                if only in ("all", "speed"):
                    report["speed"] = speed(config["think_off"], context)
        except Exception as error:  # noqa: BLE001 - a by-hand probe records any failure, then stops its server.
            report["error"] = f"{type(error).__name__}: {error}"
        finally:
            stop.set()
            server.terminate()
            try:
                server.wait(30)
            except subprocess.TimeoutExpired:
                server.kill()
    report["peak_footprint_mb"] = round(peak["mb"])
    report["swap_used_mb_after"] = swap_used_mb()
    pattern = r"(model buffer size|KV buffer size|kv_cache.*size|compute buffer size|general\.architecture|n_ctx_train)"
    report["log_buffers"] = [line.strip()[:200] for line in log_path.read_text(errors="replace").splitlines()
                             if re.search(pattern, line)][:24]
    return finish(report, out_dir, tag, 1 if "error" in report else 0)


if __name__ == "__main__":
    raise SystemExit(main())
