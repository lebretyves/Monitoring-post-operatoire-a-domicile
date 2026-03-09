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
            payload: dict[str, Any] = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0, "num_predict": 160},
            }
            if system:
                payload["system"] = system
            body = await self._post_generate(payload, timeout_seconds=self.timeout_seconds)
            if not body:
                return None
            raw_response = body.get("response")
            if not isinstance(raw_response, str) or not raw_response.strip():
                return None
            structured = _extract_json_payload(raw_response)
            if not structured:
                return None
            summary = structured.get("summary")
            return summary.strip() if isinstance(summary, str) and summary.strip() else None
        except httpx.HTTPError:
            return None

    async def is_available(self, timeout_seconds: int = 1) -> bool:
        if not self.enabled:
            return False
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    async def probe_generation(self, timeout_seconds: int = 12) -> bool:
        if not self.enabled:
            return False
        payload = {
            "model": self.model,
            "prompt": 'Retourne uniquement un JSON compact: {"status":"ok"}',
            "stream": False,
            "format": "json",
            "options": {"temperature": 0, "num_predict": 24},
        }
        body = await self._post_generate(payload, timeout_seconds=timeout_seconds)
        if not body:
            return False
        raw_response = body.get("response")
        if not isinstance(raw_response, str) or not raw_response.strip():
            return False
        structured = _extract_json_payload(raw_response)
        return isinstance(structured, dict) and str(structured.get("status", "")).lower() == "ok"

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
            "format": "json",
            "options": {"temperature": 0, "num_predict": 240},
        }
        if system:
            payload["system"] = system
        try:
            body = await self._post_generate(payload, timeout_seconds=self.timeout_seconds)
            if not body:
                return None
            raw_response = body.get("response")
            if not isinstance(raw_response, str) or not raw_response.strip():
                return None
            decoded = _extract_json_payload(raw_response)
            if not isinstance(decoded, dict):
                return None
            if not _matches_required_shape(decoded, schema):
                return None
            return decoded
        except (httpx.HTTPError, json.JSONDecodeError):
            return None

    async def _post_generate(
        self,
        payload: dict[str, Any],
        *,
        timeout_seconds: int,
    ) -> dict[str, Any] | None:
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(f"{self.base_url}/api/generate", json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError:
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


def _matches_required_shape(payload: dict[str, Any], schema: dict[str, Any]) -> bool:
    required = schema.get("required")
    if isinstance(required, list):
        for key in required:
            if key not in payload:
                return False
    return True
