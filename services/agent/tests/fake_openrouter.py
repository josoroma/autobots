"""An in-process fake of OpenRouter Chat Completions, through the real adapter and SDK."""

import json
from typing import Any

import httpx
import openrouter
from langchain_openrouter import ChatOpenRouter
from pydantic import SecretStr

DEEPSEEK_WIRE_ID = "deepseek/deepseek-v4.1-flash-1017"
TERRA_WIRE_ID = "openai/gpt-6.1-terra"
APPROVED_WIRE_IDS = frozenset({DEEPSEEK_WIRE_ID, TERRA_WIRE_ID})
ARRANGED_KEY = "arranged-not-a-real-key"


class FakeOpenRouter:
    """Records requests and refuses what the two-profile policy forbids, all in process."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def models(self) -> list[str]:
        return [request["model"] for request in self.requests]

    def _handle(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.requests.append(body)
        if not request.headers.get("authorization", "").startswith("Bearer "):
            return httpx.Response(401, json={"error": {"code": 401, "message": "missing key"}})
        if body.get("model") not in APPROVED_WIRE_IDS or body.get("models"):
            error = {"code": 400, "message": "not an approved profile"}
            return httpx.Response(400, json={"error": error})
        return httpx.Response(
            200,
            json={
                "id": "fake",
                "object": "chat.completion",
                "created": 1,
                "model": body["model"],
                "system_fingerprint": "fake",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "fake reply"},
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    def chat_model(self, wire_id: str) -> ChatOpenRouter:
        http = httpx.Client(transport=httpx.MockTransport(self._handle))
        client = openrouter.OpenRouter(api_key=ARRANGED_KEY, client=http)
        return ChatOpenRouter(
            model=wire_id, api_key=SecretStr(ARRANGED_KEY), max_retries=0, client=client
        )
