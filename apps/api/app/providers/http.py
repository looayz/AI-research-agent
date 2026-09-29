import asyncio
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504, 529}


def error_detail(response: httpx.Response, limit: int = 300) -> str:
    """Best-effort human readable error message from an API error response."""
    try:
        data = response.json()
    except ValueError:
        return response.text[:limit]
    if isinstance(data, dict):
        err = data.get("error", data.get("detail", data))
        if isinstance(err, dict):
            err = err.get("message") or err.get("type") or err
        return str(err)[:limit]
    if isinstance(data, list) and data and isinstance(data[0], dict):
        # Gemini wraps errors in a list
        err = data[0].get("error", {})
        return str(err.get("message", err))[:limit]
    return str(data)[:limit]


async def request_with_retries(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    attempts: int = 3,
    base_delay: float = 1.0,
    **kwargs: Any,
) -> httpx.Response:
    """Send a request, retrying on timeouts, connection errors and 429/5xx."""
    last_exc: Optional[Exception] = None
    for attempt in range(attempts):
        try:
            response = await client.request(method, url, **kwargs)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            last_exc = exc
        else:
            if response.status_code not in RETRYABLE_STATUS or attempt == attempts - 1:
                return response
            last_exc = None
            retry_after = response.headers.get("retry-after", "")
            if retry_after.isdigit():
                await asyncio.sleep(min(float(retry_after), 20.0))
                continue
        if attempt < attempts - 1:
            delay = base_delay * (3**attempt)
            logger.debug("Retrying %s %s in %.1fs (attempt %d)", method, url, delay, attempt + 1)
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc
