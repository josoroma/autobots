"""How fast a local route reads and writes on this Mac, and how much memory its server holds
(Decision 0041 A15, US-23.2).

Each measurement is one streamed chat completion sent straight to the owner's llama-server on
127.0.0.1, so it measures the route, not the gateway. The prompts are synthetic sentences from a
fixed word list, of about 8K, 32K and 62K tokens by the server's own tokenizer. Each extends the
last, as the by-hand probe's did, so the prompt cache serves the earlier part and the reading speed
is for the new tokens. The server's peak footprint is sampled every two seconds while they run.
"""

import asyncio
import json
import random
import re
import shutil
import time
from collections.abc import Mapping
from typing import Any

import httpx

from autobots.adapters.models.local_server import base_url

SIZES: tuple[tuple[str, int], ...] = (("8k", 8_000), ("32k", 32_000), ("64k", 62_000))
OUTPUT_TOKENS = 64
SAMPLE_SECONDS = 2.0
# A cold 62K read took about 11 minutes by hand, so each request gets well past that.
REQUEST_SECONDS = 1_800.0
WORDS = (
    "river harbor ledger orchard signal lantern meadow archive compass quarry beacon granite "
    "willow market ferry canyon thicket mill furnace pasture vessel tide summit hollow garden "
    "bridge forge"
).split()
QUESTION = "\n\nIn one sentence, which words repeat most in this text?"


async def _tokens(http: httpx.AsyncClient, port: int, text: str) -> int:
    reply = await http.post(f"http://127.0.0.1:{port}/tokenize", json={"content": text})
    reply.raise_for_status()
    return len(reply.json()["tokens"])


async def filler(http: httpx.AsyncClient, port: int, tokens: int) -> str:
    """The same sentences every time, cut to about `tokens` by the server's tokenizer."""
    rng = random.Random(41)
    sentences: list[str] = []
    while True:
        sentences.extend(
            " ".join(rng.choice(WORDS) for _ in range(12)).capitalize() + "." for _ in range(400)
        )
        text = " ".join(sentences)
        count = await _tokens(http, port, text)
        if count >= tokens:
            return text[: int(len(text) * tokens / count)]


async def timed_stream(
    http: httpx.AsyncClient, port: int, model: str, content: str, extra: Mapping[str, Any]
) -> dict[str, Any]:
    """One streamed completion: when its first content arrived, and its usage."""
    body = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": OUTPUT_TOKENS,
        "stream": True,
        "stream_options": {"include_usage": True},
        **extra,
    }
    started = time.monotonic()
    first: float | None = None
    usage: dict[str, Any] = {}
    async with http.stream("POST", base_url(port) + "/chat/completions", json=body) as reply:
        reply.raise_for_status()
        async for line in reply.aiter_lines():
            if not line.startswith("data:") or line.strip() == "data: [DONE]":
                continue
            chunk = json.loads(line[5:])
            usage = chunk.get("usage") or usage
            for choice in chunk.get("choices") or []:
                if (choice.get("delta") or {}).get("content") and first is None:
                    first = time.monotonic()
    ended = time.monotonic()
    first = first or ended
    return {
        "first_content_seconds": round(first - started, 2),
        "seconds": round(ended - started, 2),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
    }


def _speeds(result: dict[str, Any], new_tokens: int) -> dict[str, Any]:
    reading = result["first_content_seconds"]
    writing = result["seconds"] - reading
    written = result.get("completion_tokens") or 0
    return {
        **result,
        "new_prompt_tokens": new_tokens,
        "reading_tokens_per_second": round(new_tokens / reading, 1) if reading > 0 else None,
        "writing_tokens_per_second": round(written / writing, 1)
        if writing > 0 and written
        else None,
    }


async def _listening_pid(port: int) -> int | None:
    if shutil.which("lsof") is None:
        return None
    process = await asyncio.create_subprocess_exec(
        "lsof",
        "-nP",
        f"-iTCP:{port}",
        "-sTCP:LISTEN",
        "-t",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await process.communicate()
    pids = [int(value) for value in out.decode().split() if value.isdigit()]
    return pids[0] if pids else None


async def footprint_mb(pid: int) -> float | None:
    """macOS's footprint of one process, which includes the GPU memory it holds."""
    process = await asyncio.create_subprocess_exec(
        "/usr/bin/footprint",
        str(pid),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await process.communicate()
    match = re.search(r"Footprint:\s+([\d.]+)\s+(KB|MB|GB)", out.decode(errors="replace"))
    if not match:
        return None
    return float(match.group(1)) * {"KB": 1 / 1024, "MB": 1.0, "GB": 1024.0}[match.group(2)]


async def server_facts(http: httpx.AsyncClient, port: int) -> dict[str, Any]:
    """What the server says it is: its build and context, never a path on this Mac."""
    reply = await http.get(f"http://127.0.0.1:{port}/props")
    if reply.status_code != 200:
        return {}
    props = reply.json()
    settings = props.get("default_generation_settings") or {}
    return {"build_info": props.get("build_info"), "n_ctx": settings.get("n_ctx")}


async def measure(
    port: int,
    model: str,
    extra: Mapping[str, Any],
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    sizes: tuple[tuple[str, int], ...] = SIZES,
) -> dict[str, Any]:
    """Each size's timings, the server's facts and its peak footprint. `extra` carries the
    profile's thinking switch, as the route sends it."""
    peak: dict[str, Any] = {"mb": None, "reason": None}
    stop = asyncio.Event()
    pid = await _listening_pid(port) if transport is None else None

    async def sample() -> None:
        if pid is None or not shutil.which("/usr/bin/footprint"):
            peak["reason"] = "no listening process or footprint tool to sample"
            return
        while not stop.is_set():
            value = await footprint_mb(pid)
            if value is not None:
                peak["mb"] = max(peak["mb"] or 0.0, value)
            try:
                await asyncio.wait_for(stop.wait(), SAMPLE_SECONDS)
            except TimeoutError:
                pass

    sampler = asyncio.create_task(sample())
    results: dict[str, Any] = {}
    async with httpx.AsyncClient(transport=transport, timeout=REQUEST_SECONDS) as http:
        facts = await server_facts(http, port)
        read_before = 0
        for label, size in sizes:
            text = await filler(http, port, size)
            result = await timed_stream(http, port, model, text + QUESTION, extra)
            prompt = result.get("prompt_tokens") or size
            results[label] = _speeds(result, max(prompt - read_before, 0))
            read_before = prompt
    stop.set()
    await sampler
    return {
        "server": facts,
        "sizes": results,
        "peak_footprint_mb": round(peak["mb"]) if peak["mb"] is not None else None,
        "peak_footprint_note": peak["reason"]
        or "macOS footprint of the listening process, without the weights' file pages",
        "how": "each prompt extends the last, so the cache serves the earlier part; reading speed "
        "is for the new tokens",
    }
