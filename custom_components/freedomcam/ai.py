"""Object detection providers."""
from __future__ import annotations

import aiohttp

CLOUDFLARE_URL = "https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/@cf/facebook/detr-resnet-50"


class DetectionError(Exception):
    """The detector could not analyse the image."""


async def cloudflare_detect(session: aiohttp.ClientSession, account: str, token: str, jpeg: bytes,
                            timeout: float = 20) -> list[dict]:
    """Objects found by Cloudflare Workers AI (DETR): [{"label", "score", "box"}] in pixels."""
    try:
        async with session.post(CLOUDFLARE_URL.format(account=account), data=jpeg,
                                headers={"Authorization": f"Bearer {token}",
                                         "Content-Type": "application/octet-stream"},
                                timeout=aiohttp.ClientTimeout(total=timeout)) as r:
            data = await r.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError, ValueError) as err:
        raise DetectionError(str(err) or type(err).__name__) from err
    if r.status != 200 or not data.get("success", True):
        errors = data.get("errors") if isinstance(data, dict) else None
        raise DetectionError(f"HTTP {r.status}: {errors or data}")
    return data.get("result") or []
