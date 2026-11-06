"""Builds the S3 client from the stored configuration and checks a bucket."""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import aiohttp

from .const import (
    CONF_ACCESS_KEY,
    CONF_ACCOUNT_ID,
    CONF_BUCKET,
    CONF_ENDPOINT,
    CONF_JURISDICTION,
    CONF_PROVIDER,
    CONF_REGION,
    CONF_SECRET_KEY,
    CONF_VIRTUAL_HOST,
    MANIFEST_KEY,
    PROVIDERS,
    R2_JURISDICTIONS,
)
from .s3 import S3Client, S3Error


def endpoint_for(data: Mapping[str, Any]) -> tuple[str, str, bool]:
    """(endpoint, region, virtual-host addressing) for the stored provider settings."""
    provider = PROVIDERS[data[CONF_PROVIDER]]
    if provider.key == "other":
        return (data[CONF_ENDPOINT].rstrip("/"), data.get(CONF_REGION) or provider.default_region,
                bool(data.get(CONF_VIRTUAL_HOST, False)))
    region = provider.region or data.get(CONF_REGION) or provider.default_region
    endpoint = provider.endpoint.format(
        account=(data.get(CONF_ACCOUNT_ID) or "").strip(), region=region,
        jurisdiction=R2_JURISDICTIONS.get(data.get(CONF_JURISDICTION, "default"), ""))
    return endpoint, region, provider.virtual_host


def client_from_config(session: aiohttp.ClientSession, data: Mapping[str, Any]) -> S3Client:
    endpoint, region, virtual_host = endpoint_for(data)
    return S3Client(session, endpoint, data[CONF_BUCKET].strip(), data[CONF_ACCESS_KEY].strip(),
                    data[CONF_SECRET_KEY].strip(), region, virtual_host)


async def check_bucket(client: S3Client, create: bool = True) -> str | None:
    """Check that the keys can write and read the bucket (creating it if missing and allowed).

    Returns None if everything works, or an error key for the config flow.
    """
    probe = json.dumps({"format": "freedomcam", "probe": True}).encode()
    for attempt in (1, 2):
        try:
            if await client.get_object(MANIFEST_KEY) is None:     # new bucket: leave a placeholder manifest
                await client.put_object(MANIFEST_KEY, probe, "application/json")
            await client.put_object("_probe", probe, "application/json")
            if await client.get_object("_probe") != probe:
                return "cannot_read"
            await client.delete_object("_probe")
            return None
        except S3Error as err:
            if err.code == "NoSuchBucket" and create and attempt == 1:
                try:
                    await client.create_bucket()
                except S3Error:
                    return "bucket_not_found"
                continue
            if err.code == "NoSuchBucket":
                return "bucket_not_found"
            if err.status == 0:
                return "cannot_connect"
            if err.is_auth_error:
                return "invalid_auth"
            if err.is_access_denied:
                return "access_denied"
            return "unknown"
    return "unknown"


async def check_app_keys(client: S3Client) -> str | None:
    """The app's keys must read the bucket and must NOT be able to write it. Returns an error key or None."""
    try:
        await client.get_object(MANIFEST_KEY)
    except S3Error as err:
        if err.status == 0:
            return "cannot_connect"
        return "app_keys_invalid"
    try:
        await client.put_object("_probe_app", b"{}", "application/json")
    except S3Error as err:
        if err.status in (401, 403):
            return None                  # read-only, as it should be
        return "cannot_connect" if err.status == 0 else "app_keys_invalid"
    await client.delete_object("_probe_app")
    return "app_keys_can_write"
