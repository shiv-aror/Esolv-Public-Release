"""Minimal OpenRouter (OpenAI-compatible) chat client with provider privacy preferences and model fallback."""
import json
import logging

import httpx

from ..config import get_settings


log = logging.getLogger(__name__)


class LLMError(Exception):
    pass


class LLMQuotaError(LLMError):
    pass


class OpenRouterClient:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None):
        s = get_settings()
        self.s = s
        self._http = httpx.AsyncClient(
            base_url=s.openrouter_base_url, timeout=httpx.Timeout(90, connect=15), transport=transport,
            headers={"Authorization": f"Bearer {s.openrouter_api_key}", "HTTP-Referer": "https://esolv.app", "X-Title": "Esolv"},
        )

    async def aclose(self):
        await self._http.aclose()

    def _body(self, messages, tools, model, json_mode, max_tokens, temperature, zdr):
        s = self.s
        body: dict = {
            "model": model or s.openrouter_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,

            "provider": {"data_collection": "deny", **({"zdr": True} if zdr else {})},
        }
        if s.openrouter_fallback_model and (model or s.openrouter_model) != s.openrouter_fallback_model:
            body["models"] = [model or s.openrouter_model, s.openrouter_fallback_model]
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        return body

    async def chat(self, messages: list[dict], tools: list[dict] | None = None, model: str | None = None,
                   json_mode: bool = False, max_tokens: int = 1500, temperature: float = 0.2) -> dict:
        if not self.s.openrouter_api_key:
            raise LLMError("OPENROUTER_API_KEY is not set on the server.")
        last = ""
        for zdr in ([True, False] if self.s.openrouter_zdr else [False]):
            try:
                r = await self._http.post("/chat/completions", json=self._body(messages, tools, model, json_mode, max_tokens, temperature, zdr))
            except httpx.RequestError as e:
                raise LLMError("Could not reach the model provider.") from e
            if r.status_code == 404 and zdr:
                last = r.text
                continue
            if r.status_code == 403 and "Key limit exceeded" in r.text:
                raise LLMQuotaError("OpenRouter API key limit exceeded.")
            if r.status_code >= 400:
                raise LLMError(f"Model provider error {r.status_code}: {r.text[:300]}")
            data = r.json()
            if "error" in data:
                raise LLMError(str(data["error"])[:300])
            choice = data["choices"][0]
            msg = choice["message"]
            return {"content": msg.get("content") or "", "tool_calls": msg.get("tool_calls") or [], "raw": msg,
                    "usage": data.get("usage", {}), "model": data.get("model"),
                    "finish_reason": choice.get("finish_reason")}
        raise LLMError(f"No privacy-compliant model endpoint available: {last[:200]}")

    async def chat_json(self, messages: list[dict], model: str | None = None, max_tokens: int = 2500) -> dict:
        last = ""
        for attempt in range(2):
            out = await self.chat(messages, model=model, json_mode=True, max_tokens=max_tokens, temperature=0)
            txt = out["content"].strip()
            last = txt
            start, end = txt.find("{"), txt.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(txt[start:end + 1])
                except json.JSONDecodeError:
                    pass
            log.warning("chat_json parse failure (attempt %d): %r", attempt + 1, txt[:300])
        raise LLMError(f"Model did not return valid JSON: {last[:120]!r}")
