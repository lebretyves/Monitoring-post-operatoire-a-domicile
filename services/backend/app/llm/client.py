from __future__ import annotations

import json
from typing import Any

import httpx


class OllamaClient:
    def __init__(self, enabled: bool, base_url: str, model: str, timeout_seconds: int) -> None:
        self.enabled = enabled
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def summarize(self, prompt: str, *, system: str | None = None) -> str | None:
        if not self.enabled:
            return None
        try:
            payload: dict[str, Any] = {"model": self.model, "prompt": prompt, "stream": False}
            if system:
                payload["system"] = system
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )
                response.raise_for_status()
                payload: dict[str, Any] = response.json()
                summary = payload.get("response")
                return summary.strip() if isinstance(summary, str) and summary.strip() else None
        except httpx.HTTPError:
            return None

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        *,
        system: str | None = None,
    ) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": schema,
            "options": {"temperature": 0},
        }
        if system:
            payload["system"] = system
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(f"{self.base_url}/api/generate", json=payload)
                response.raise_for_status()
                body: dict[str, Any] = response.json()
                raw_response = body.get("response")
                if not isinstance(raw_response, str) or not raw_response.strip():
                    return None
                decoded = _extract_json_payload(raw_response)
                return decoded if isinstance(decoded, dict) else None
        except (httpx.HTTPError, json.JSONDecodeError):
            return None


def _extract_json_payload(raw_response: str) -> dict[str, Any] | None:
    stripped = raw_response.strip()
    try:
        decoded = json.loads(stripped)
        return decoded if isinstance(decoded, dict) else None
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    candidate = stripped[start : end + 1]
    decoded = json.loads(candidate)
    return decoded if isinstance(decoded, dict) else None
