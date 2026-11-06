from __future__ import annotations

import base64
import json
from datetime import datetime
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.freedomcam.connection import SCHEME, connection_link, qr_png
from custom_components.freedomcam.const import DOMAIN
from custom_components.freedomcam.s3 import S3Error
from custom_components.freedomcam.storage import check_app_keys
from custom_components.freedomcam.store import PhotoStore

DATA = {"provider": "cloudflare_r2", "account_id": "abc", "jurisdiction": "default", "bucket": "fotos",
        "access_key_id": "WRITE", "secret_access_key": "WRITESECRET", "retention_days": 30}
BASE_OPTS = {"pause_seconds": 30, "max_per_hour": 60, "sensitivity": "medium", "thumbnails": True,
             "ai_provider": "none", "ai_min_score": 0.7}


def _decode(link: str) -> dict:
    code = link.removeprefix(SCHEME)
    return json.loads(base64.urlsafe_b64decode(code + "=" * (-len(code) % 4)))


def test_link_has_app_keys_not_write_keys():
    assert connection_link(DATA, {}) is None
    link = connection_link(DATA, {"app_access_key_id": "RO", "app_secret_access_key": "ROSECRET"})
    payload = _decode(link)
    assert payload == {"v": 1, "provider": "cloudflare_r2", "bucket": "fotos", "access_key_id": "RO",
                       "secret_access_key": "ROSECRET", "account_id": "abc", "jurisdiction": "default"}
    assert "WRITE" not in link and qr_png(link).startswith(b"\x89PNG")


async def test_app_keys_must_be_read_only(fake_s3):
    assert await check_app_keys(fake_s3) == "app_keys_can_write"
    assert "_probe_app" not in fake_s3.objects
    fake_s3.fail_put = S3Error(403, "AccessDenied")
    assert await check_app_keys(fake_s3) is None
    fake_s3.fail_get = S3Error(403, "InvalidAccessKeyId")
    assert await check_app_keys(fake_s3) == "app_keys_invalid"


async def test_manifest_keeps_indexed_since(fake_s3):
    tz = ZoneInfo("Europe/Madrid")
    store = PhotoStore(fake_s3, 30)
    await store.write_manifest([], "Europe/Madrid", datetime(2026, 11, 6, 18, 0, tzinfo=tz))
    assert json.loads(fake_s3.objects["freedomcam.json"])["indexed_since"] == "2026-11-07"
    await store.write_manifest([], "Europe/Madrid", datetime(2026, 12, 1, 9, 0, tzinfo=tz))
    assert json.loads(fake_s3.objects["freedomcam.json"])["indexed_since"] == "2026-11-07"


async def test_options_app_keys_and_qr_entity(hass: HomeAssistant, fake_s3):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, options=BASE_OPTS, title="fotos")
    entry.add_to_hass(hass)
    with patch("custom_components.freedomcam.client_from_config", return_value=fake_s3), \
         patch("custom_components.freedomcam.config_flow.client_from_config", return_value=fake_s3):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get("image.freedomcam_fotos_app_connection_qr") is None    # no app keys yet

        r = await hass.config_entries.options.async_init(entry.entry_id)
        r = await hass.config_entries.options.async_configure(r["flow_id"], BASE_OPTS | {"app_access_key_id": "RO"})
        assert r["errors"] == {"base": "app_keys_incomplete"}
        keys = {"app_access_key_id": "RO", "app_secret_access_key": "ROSECRET"}
        r = await hass.config_entries.options.async_configure(r["flow_id"], BASE_OPTS | keys)
        assert r["errors"] == {"base": "app_keys_can_write"}          # the fake bucket accepts writes
        with patch("custom_components.freedomcam.config_flow.check_app_keys", AsyncMock(return_value=None)):
            r = await hass.config_entries.options.async_configure(r["flow_id"], BASE_OPTS | keys)
        assert r["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
    assert hass.states.get("image.freedomcam_fotos_app_connection_qr") is not None
