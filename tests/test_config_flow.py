from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.freedomcam.const import DOMAIN
from custom_components.freedomcam.s3 import S3Error

R2 = {"account_id": "abc123", "jurisdiction": "default", "bucket": "fotos",
      "access_key_id": "AK", "secret_access_key": "SK"}


def _patches(check="ok", retention_error=None):
    client = MagicMock()
    client.set_retention = AsyncMock(side_effect=retention_error)
    return (patch("custom_components.freedomcam.config_flow.check_bucket",
                  AsyncMock(return_value=None if check == "ok" else check)),
            patch("custom_components.freedomcam.config_flow.client_from_config", return_value=client),
            patch("custom_components.freedomcam.async_setup_entry", AsyncMock(return_value=True)))


async def _to_storage(hass, provider="cloudflare_r2"):
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert r["type"] is FlowResultType.FORM and r["step_id"] == "user"
    return await hass.config_entries.flow.async_configure(r["flow_id"], {"provider": provider})


async def test_r2_happy_path(hass: HomeAssistant):
    p1, p2, p3 = _patches()
    with p1, p2 as cfc, p3:
        r = await _to_storage(hass)
        assert r["step_id"] == "cloudflare_r2"
        r = await hass.config_entries.flow.async_configure(r["flow_id"], R2)
        assert r["step_id"] == "retention"
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"retention_days": 30, "manage_lifecycle": True})
    assert r["type"] is FlowResultType.CREATE_ENTRY and r["title"] == "fotos"
    assert r["data"]["provider"] == "cloudflare_r2" and r["data"]["retention_days"] == 30
    cfc.return_value.set_retention.assert_awaited_once_with(30)
    assert r["options"]["ai_provider"] == "none"


async def test_bad_keys_show_error(hass: HomeAssistant):
    p1, p2, p3 = _patches(check="invalid_auth")
    with p1, p2, p3:
        r = await _to_storage(hass)
        r = await hass.config_entries.flow.async_configure(r["flow_id"], R2)
    assert r["type"] is FlowResultType.FORM and r["errors"] == {"base": "invalid_auth"}


async def test_lifecycle_denied_then_skip(hass: HomeAssistant):
    p1, p2, p3 = _patches(retention_error=S3Error(403, "AccessDenied"))
    with p1, p2, p3:
        r = await _to_storage(hass)
        r = await hass.config_entries.flow.async_configure(r["flow_id"], R2)
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"retention_days": 30, "manage_lifecycle": True})
        assert r["errors"] == {"base": "lifecycle_denied"}
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"retention_days": 30, "manage_lifecycle": False})
    assert r["type"] is FlowResultType.CREATE_ENTRY and r["data"]["manage_lifecycle"] is False


async def test_other_provider_and_duplicate(hass: HomeAssistant):
    data = {"endpoint": "http://minio.local:9000", "region": "us-east-1", "virtual_host": False,
            "bucket": "cams", "access_key_id": "a", "secret_access_key": "b"}
    p1, p2, p3 = _patches()
    with p1, p2, p3:
        r = await _to_storage(hass, "other")
        assert r["step_id"] == "other"
        r = await hass.config_entries.flow.async_configure(r["flow_id"], data)
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"retention_days": 0, "manage_lifecycle": False})
        assert r["type"] is FlowResultType.CREATE_ENTRY
        r = await _to_storage(hass, "other")
        r = await hass.config_entries.flow.async_configure(r["flow_id"], data)
    assert r["type"] is FlowResultType.ABORT and r["reason"] == "already_configured"


async def test_add_and_edit_camera(hass: HomeAssistant):
    entry = MockConfigEntry(domain=DOMAIN, data={"provider": "other", "bucket": "b"}, title="b")
    entry.add_to_hass(hass)
    r = await hass.config_entries.subentries.async_init((entry.entry_id, "camera"), context={"source": SOURCE_USER})
    assert r["step_id"] == "user"
    cam = {"camera_entity": "camera.garden", "name": "Jardín trasero", "kind": "outdoor", "mode": "sensor",
           "interval_seconds": 10, "only_when_away": False}
    r = await hass.config_entries.subentries.async_configure(r["flow_id"], cam)
    assert r["errors"] == {"motion_entity": "motion_entity_required"}
    r = await hass.config_entries.subentries.async_configure(r["flow_id"], cam | {"mode": "image"})
    assert r["type"] is FlowResultType.CREATE_ENTRY
    sub = next(iter(entry.subentries.values()))
    assert sub.data["camera_id"] == "jardin-trasero" and sub.title == "Jardín trasero"

    r = await hass.config_entries.subentries.async_init((entry.entry_id, "camera"), context={"source": SOURCE_USER})
    r = await hass.config_entries.subentries.async_configure(r["flow_id"], cam | {"mode": "image", "camera_id": "jardin-trasero"})
    assert r["errors"] == {"camera_id": "camera_id_taken"}
    r = await hass.config_entries.subentries.async_configure(r["flow_id"], cam | {"mode": "image", "camera_id": "_bad"})
    assert r["errors"] == {"camera_id": "invalid_camera_id"}

    r = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "camera"), context={"source": "reconfigure", "subentry_id": sub.subentry_id})
    r = await hass.config_entries.subentries.async_configure(r["flow_id"], cam | {"mode": "image", "name": "Garden"})
    assert r["type"] is FlowResultType.ABORT and r["reason"] == "reconfigure_successful"
    sub = entry.subentries[sub.subentry_id]
    assert sub.title == "Garden" and sub.data["camera_id"] == "jardin-trasero"   # the folder never changes


async def test_options_ai_validation(hass: HomeAssistant):
    entry = MockConfigEntry(domain=DOMAIN, data={"provider": "other", "bucket": "b"}, options={})
    entry.add_to_hass(hass)
    base = {"pause_seconds": 30, "max_per_hour": 60, "sensitivity": "medium", "thumbnails": True, "ai_min_score": 0.7}
    r = await hass.config_entries.options.async_init(entry.entry_id)
    r = await hass.config_entries.options.async_configure(r["flow_id"], base | {"ai_provider": "cloudflare"})
    assert r["errors"] == {"base": "ai_missing"}
    with patch("custom_components.freedomcam.config_flow.ai.cloudflare_detect", AsyncMock(return_value=[])):
        r = await hass.config_entries.options.async_configure(
            r["flow_id"], base | {"ai_provider": "cloudflare", "ai_account_id": "acc", "ai_token": "tok",
                                  "presence_entity": "zone.home"})
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["presence_entity"] == "zone.home" and entry.options["ai_provider"] == "cloudflare"
