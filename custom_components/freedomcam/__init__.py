"""freedomCam: camera snapshots on motion, stored in your own S3-compatible bucket."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change, async_track_time_interval
from homeassistant.util import dt as dt_util

from . import motion
from .const import (
    AI_NONE,
    CONF_AI_ACCOUNT_ID,
    CONF_AI_MIN_SCORE,
    CONF_AI_PROVIDER,
    CONF_AI_TOKEN,
    CONF_CAMERA_ENTITY,
    CONF_CAMERA_ID,
    CONF_INTERVAL,
    CONF_KIND,
    CONF_MAX_PER_HOUR,
    CONF_MODE,
    CONF_MOTION_ENTITY,
    CONF_NAME,
    CONF_ONLY_WHEN_AWAY,
    CONF_PAUSE,
    CONF_PRESENCE_ENTITY,
    CONF_RETENTION_DAYS,
    CONF_SENSITIVITY,
    CONF_THUMBNAILS,
    DEFAULT_AI_MIN_SCORE,
    DEFAULT_INTERVAL,
    DEFAULT_MAX_PER_HOUR,
    DEFAULT_PAUSE,
    DEFAULT_SENSITIVITY,
    INDEX_FLUSH_SECONDS,
    KIND_OUTDOOR,
    MODE_IMAGE,
    SENSITIVITIES,
    SUBENTRY_CAMERA,
)
from .s3 import S3Client, S3Error
from .storage import client_from_config
from .store import PhotoStore
from .watcher import CameraConfig, CameraWatcher, Settings

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.IMAGE, Platform.SENSOR]


@dataclass
class FreedomCamData:
    client: S3Client
    store: PhotoStore
    watchers: dict[str, CameraWatcher] = field(default_factory=dict)   # by subentry id


type FreedomCamConfigEntry = ConfigEntry[FreedomCamData]


def _settings(entry: ConfigEntry) -> Settings:
    o = entry.options
    return Settings(
        pause=timedelta(seconds=max(1, int(o.get(CONF_PAUSE, DEFAULT_PAUSE)))),
        max_per_hour=int(o.get(CONF_MAX_PER_HOUR, DEFAULT_MAX_PER_HOUR)),
        presence_entity=o.get(CONF_PRESENCE_ENTITY) or None,
        thumbnails=bool(o.get(CONF_THUMBNAILS, True)),
        detection=motion.Settings(threshold_fraction=SENSITIVITIES[o.get(CONF_SENSITIVITY, DEFAULT_SENSITIVITY)]),
        ai_provider=o.get(CONF_AI_PROVIDER, AI_NONE),
        ai_account=o.get(CONF_AI_ACCOUNT_ID),
        ai_token=o.get(CONF_AI_TOKEN),
        ai_min_score=float(o.get(CONF_AI_MIN_SCORE, DEFAULT_AI_MIN_SCORE)),
    )


async def async_setup_entry(hass: HomeAssistant, entry: FreedomCamConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    client = client_from_config(session, entry.data)
    store = PhotoStore(client, int(entry.data.get(CONF_RETENTION_DAYS, 0)))
    cameras = [s for s in entry.subentries.values() if s.subentry_type == SUBENTRY_CAMERA]
    try:
        await store.write_manifest(
            [{"id": s.data[CONF_CAMERA_ID], "name": s.data[CONF_NAME], "kind": s.data.get(CONF_KIND, KIND_OUTDOOR)}
             for s in cameras],
            str(hass.config.time_zone), dt_util.now())
    except S3Error as err:
        if err.is_auth_error:
            raise ConfigEntryAuthFailed(str(err)) from err
        raise ConfigEntryNotReady(str(err)) from err

    data = FreedomCamData(client, store)
    settings = _settings(entry)
    for sub in cameras:
        d = sub.data
        data.watchers[sub.subentry_id] = CameraWatcher(
            hass,
            CameraConfig(camera_id=d[CONF_CAMERA_ID], name=d[CONF_NAME], entity_id=d[CONF_CAMERA_ENTITY],
                         kind=d.get(CONF_KIND, KIND_OUTDOOR), mode=d.get(CONF_MODE, MODE_IMAGE),
                         motion_entity=d.get(CONF_MOTION_ENTITY) or None,
                         interval=int(d.get(CONF_INTERVAL, DEFAULT_INTERVAL)),
                         only_when_away=bool(d.get(CONF_ONLY_WHEN_AWAY, False))),
            settings, store, session)
    entry.runtime_data = data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    for watcher in data.watchers.values():
        watcher.start()
        entry.async_on_unload(watcher.stop)

    async def _flush(_now=None) -> None:
        await store.flush(dt_util.now().date())

    def _midnight(_now) -> None:            # "photos today" goes back to 0
        for watcher in data.watchers.values():
            watcher.notify()

    entry.async_on_unload(async_track_time_interval(hass, _flush, timedelta(seconds=INDEX_FLUSH_SECONDS)))
    entry.async_on_unload(async_track_time_change(hass, _midnight, hour=0, minute=0, second=1))
    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


async def _reload(hass: HomeAssistant, entry: FreedomCamConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: FreedomCamConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        for watcher in entry.runtime_data.watchers.values():
            watcher.stop()
        await entry.runtime_data.store.flush(dt_util.now().date())   # do not lose the last index updates
    return unloaded
