"""Connection code for the iOS app: everything it needs to read the bucket, as a freedomcam:// link."""
from __future__ import annotations

import base64
import io
import json
from collections.abc import Mapping
from typing import Any

from .const import (
    CONF_ACCOUNT_ID,
    CONF_APP_ACCESS_KEY,
    CONF_APP_SECRET_KEY,
    CONF_BUCKET,
    CONF_ENDPOINT,
    CONF_JURISDICTION,
    CONF_PROVIDER,
    CONF_REGION,
    CONF_VIRTUAL_HOST,
)

SCHEME = "freedomcam://connect?c="


def connection_link(data: Mapping[str, Any], options: Mapping[str, Any]) -> str | None:
    """Link with the storage settings and the app's read-only keys (None without app keys)."""
    if not (options.get(CONF_APP_ACCESS_KEY) and options.get(CONF_APP_SECRET_KEY)):
        return None
    payload = {"v": 1, "provider": data[CONF_PROVIDER], "bucket": data[CONF_BUCKET],
               "access_key_id": options[CONF_APP_ACCESS_KEY], "secret_access_key": options[CONF_APP_SECRET_KEY]}
    for key in (CONF_ACCOUNT_ID, CONF_JURISDICTION, CONF_REGION, CONF_ENDPOINT, CONF_VIRTUAL_HOST):
        if data.get(key) not in (None, ""):
            payload[key] = data[key]
    code = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    return SCHEME + code


def qr_png(text: str) -> bytes:
    import segno   # noqa: PLC0415 - only needed when the image is shown

    out = io.BytesIO()
    segno.make(text, error="m").save(out, kind="png", scale=8, border=3)
    return out.getvalue()
