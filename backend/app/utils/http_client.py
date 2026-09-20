"""Retrying async JSON client; only idempotent reads are retried."""

import asyncio
from typing import Any

import httpx


class UpstreamServiceError(RuntimeError):
    """A sanitized failure from an external provider."""


async def get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    retries: int = 2,
) -> Any:
    for attempt in range(retries + 1):
        try:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            if attempt == retries:
                raise UpstreamServiceError("External service is unavailable.") from exc
            await asyncio.sleep(0.1 * (2**attempt))
    raise UpstreamServiceError("External service is unavailable.")
