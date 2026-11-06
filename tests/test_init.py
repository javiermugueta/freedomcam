"""The integration running inside Home Assistant with simulated cameras and bucket."""
from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.camera import Image
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.freedomcam.const import DOMAIN
from custom_components.freedomcam.s3 import S3Error

from .images import frame

DATA = {"provider": "other", "endpoint": "http://minio:9000", "region": "us-east-1", "bucket": "fotos",
        "access_key_id": "a", "secret_access_key": "b", "retention_days": 30}
OPTIONS = {"pause_seconds": 30, "max_per_hour": 60, "sensitivity": "medium", "thumbnails": True,
           "ai_provider": "none", "presence_entity": "input_boolean.home"}
GARDEN = {"camera_entity": "camera.garden", "name": "Garden", "camera_id": "garden", "kind": "outdoor",
          "mode": "image", "interval_seconds": 10, "only_when_away": False}
HALL = {"camera_entity": "camera.hall", "name": "Hall", "camera_id": "hall", "kind": "indoor", "mode": "sensor",
        "motion_entity": "binary_sensor.hall_motion", "interval_seconds": 10, "only_when_away": True}


class Cameras:
    """Frames returned by async_get_image, per camera."""

    def __init__(self) -> None:
        self.frames = {"camera.garden": frame(), "camera.hall": frame(background=60)}
        self.fail = False

    async def get(self, hass, entity_id, timeout=10):
        if self.fail:
            raise HomeAssistantError("camera offline")
        return Image("image/jpeg", self.frames[entity_id])


@pytest.fixture
async def setup(hass: HomeAssistant, fake_s3):
    cams = Cameras()
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, options=OPTIONS, title="fotos", subentries_data=[
        {"data": GARDEN, "subentry_type": "camera", "title": "Garden", "unique_id": None},
        {"data": HALL, "subentry_type": "camera", "title": "Hall", "unique_id": None}])
    entry.add_to_hass(hass)
    hass.states.async_set("input_boolean.home", "on")
    hass.states.async_set("binary_sensor.hall_motion", "off")
    with patch("custom_components.freedomcam.client_from_config", return_value=fake_s3), \
         patch("custom_components.freedomcam.watcher.async_get_image", cams.get):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield entry, cams


def _watcher(entry, camera_id):
    return next(w for w in entry.runtime_data.watchers.values() if w.cam.camera_id == camera_id)


def _photos(fake_s3, camera):
    return [k for k in fake_s3.objects if k.startswith(camera + "/")]


async def test_manifest_and_sensors(hass, setup, fake_s3):
    entry, _ = setup
    assert entry.state is ConfigEntryState.LOADED
    manifest = json.loads(fake_s3.objects["freedomcam.json"])
    assert {c["id"] for c in manifest["cameras"]} == {"garden", "hall"}
    assert manifest["timezone"] == hass.config.time_zone and manifest["retention_days"] == 30
    assert hass.states.get("sensor.garden_photos_today").state == "0"


async def test_image_mode_saves_on_motion(hass, setup, fake_s3):
    entry, cams = setup
    w = _watcher(entry, "garden")
    await w._poll()                                   # background
    await w._poll()
    assert _photos(fake_s3, "garden") == []
    cams.frames["camera.garden"] = frame(box=(100, 100, 250, 300))
    await w._poll()
    keys = _photos(fake_s3, "garden")
    assert len(keys) == 1 and "_thumbs/" + keys[0] in fake_s3.objects
    assert hass.states.get("sensor.garden_photos_today").state == "1"
    await w._poll()                                   # still moving, but within the pause
    assert len(_photos(fake_s3, "garden")) == 1
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))   # index flush
    await hass.async_block_till_done()
    day = json.loads(fake_s3.objects[f"_index/{dt_util.now():%Y/%m/%d}.json"])
    assert day["photos"][0]["key"] == keys[0]


async def test_sensor_mode_respects_presence(hass, setup, fake_s3, freezer):
    hass.states.async_set("binary_sensor.hall_motion", "on")      # someone at home: no photos
    await hass.async_block_till_done()
    assert _photos(fake_s3, "hall") == []
    hass.states.async_set("binary_sensor.hall_motion", "off")
    hass.states.async_set("input_boolean.home", "off")            # house empty
    hass.states.async_set("binary_sensor.hall_motion", "on")
    await hass.async_block_till_done()
    assert len(_photos(fake_s3, "hall")) == 1
    freezer.tick(timedelta(seconds=31))                            # series: one more while it keeps moving
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(_photos(fake_s3, "hall")) == 2
    hass.states.async_set("binary_sensor.hall_motion", "off")       # motion over: the series stops
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(_photos(fake_s3, "hall")) == 2


async def test_camera_and_upload_errors_are_reported(hass, setup, fake_s3):
    entry, cams = setup
    w = _watcher(entry, "garden")
    cams.fail = True
    await w._poll()
    assert hass.states.get("sensor.garden_photos_today").attributes["error"] == "camera offline"
    cams.fail = False
    await w._poll()
    cams.frames["camera.garden"] = frame(box=(100, 100, 250, 300))
    fake_s3.fail_put = S3Error(503, "SlowDown")
    await w._poll()
    assert "upload" in hass.states.get("sensor.garden_photos_today").attributes["error"]


async def test_unload_flushes_indexes(hass, setup, fake_s3):
    entry, cams = setup
    w = _watcher(entry, "garden")
    await w._poll()
    cams.frames["camera.garden"] = frame(box=(100, 100, 250, 300))
    await w._poll()
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert f"_index/{dt_util.now():%Y/%m/%d}.json" in fake_s3.objects


async def test_auth_error_starts_reauth(hass: HomeAssistant, fake_s3):
    fake_s3.fail_put = S3Error(403, "InvalidAccessKeyId")
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, options=OPTIONS)
    entry.add_to_hass(hass)
    with patch("custom_components.freedomcam.client_from_config", return_value=fake_s3):
        await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert any(f["context"]["source"] == "reauth" for f in hass.config_entries.flow.async_progress())


async def test_cloudflare_labels_in_name(hass: HomeAssistant, fake_s3):
    cams = Cameras()
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, title="fotos",
                            options=OPTIONS | {"ai_provider": "cloudflare", "ai_account_id": "acc", "ai_token": "t"},
                            subentries_data=[{"data": GARDEN, "subentry_type": "camera", "title": "Garden",
                                              "unique_id": None}])
    entry.add_to_hass(hass)
    person = [{"label": "person", "score": 0.9, "box": {"xmin": 10, "ymin": 10, "xmax": 50, "ymax": 100}}]
    with patch("custom_components.freedomcam.client_from_config", return_value=fake_s3), \
         patch("custom_components.freedomcam.watcher.async_get_image", cams.get), \
         patch("custom_components.freedomcam.watcher.ai.cloudflare_detect", AsyncMock(return_value=person)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        w = _watcher(entry, "garden")
        await w._poll()
        cams.frames["camera.garden"] = frame(box=(100, 100, 250, 300))
        await w._poll()
    assert _photos(fake_s3, "garden")[0].endswith("_person.jpg")
    assert hass.states.get("sensor.garden_photos_today").attributes["last_labels"] == ["person"]
