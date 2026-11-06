"""Watches one camera and saves a photo when there is motion."""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import aiohttp

from homeassistant.components.camera import async_get_image
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later, async_track_state_change_event, async_track_time_interval
from homeassistant.util import dt as dt_util

from . import ai, motion
from .const import (
    AI_CLOUDFLARE,
    AWAY_STATES,
    INDOOR_LABELS,
    KIND_INDOOR,
    MODE_SENSOR,
)
from .s3 import S3Error
from .store import PhotoStore

_LOGGER = logging.getLogger(__name__)
FAILURES_BEFORE_WARNING = 3


@dataclass
class CameraConfig:
    camera_id: str
    name: str
    entity_id: str
    kind: str
    mode: str
    motion_entity: str | None
    interval: int
    only_when_away: bool


@dataclass
class Settings:
    pause: timedelta
    max_per_hour: int
    presence_entity: str | None
    thumbnails: bool
    detection: motion.Settings
    ai_provider: str
    ai_account: str | None = None
    ai_token: str | None = None
    ai_min_score: float = 0.7


@dataclass
class CameraStatus:
    photos_today: int = 0
    day: str | None = None
    last_photo: datetime | None = None
    last_key: str | None = None
    last_labels: list[str] = field(default_factory=list)
    last_check: datetime | None = None
    change: float | None = None
    error: str | None = None


class CameraWatcher:
    def __init__(self, hass: HomeAssistant, cam: CameraConfig, settings: Settings, store: PhotoStore,
                 session: aiohttp.ClientSession) -> None:
        self.hass, self.cam, self.settings, self.store, self.session = hass, cam, settings, store, session
        self.status = CameraStatus()
        self.detector = motion.Detector(settings.detection) if cam.mode != MODE_SENSOR else None
        self._listeners: list[Callable[[], None]] = []
        self._unsubs: list[Callable[[], None]] = []
        self._hour: datetime | None = None
        self._in_hour = 0
        self._failures = 0
        self._following = False      # sensor mode: a series of photos is running
        self._series_timer: Callable[[], None] | None = None
        self._busy = False

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        if self.cam.mode == MODE_SENSOR and self.cam.motion_entity:
            self._unsubs.append(async_track_state_change_event(self.hass, [self.cam.motion_entity],
                                                               self._motion_changed))
        else:
            self._unsubs.append(async_track_time_interval(self.hass, self._poll,
                                                          timedelta(seconds=self.cam.interval)))

    def stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._series_timer:
            self._series_timer()
            self._series_timer = None

    def add_listener(self, update: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(update)
        return lambda: self._listeners.remove(update)

    def notify(self) -> None:
        for update in list(self._listeners):
            update()

    # ------------------------------------------------------------------ conditions
    def _active(self) -> bool:
        """Photos are taken unless the camera only works when away and someone is at home."""
        if not (self.cam.only_when_away and self.settings.presence_entity):
            return True
        state = self.hass.states.get(self.settings.presence_entity)
        return state is not None and state.state.lower() in AWAY_STATES

    # ------------------------------------------------------------------ image mode
    async def _poll(self, _now: datetime | None = None) -> None:
        if self._busy or not self._active():
            return
        self._busy = True
        try:
            jpeg = await self._image()
            if jpeg is None:
                return
            state, self.status.change = await self.hass.async_add_executor_job(self.detector.analyse, jpeg)
            if state == motion.MOTION:
                await self._save(jpeg)
            else:
                self.notify()
        finally:
            self._busy = False

    # ------------------------------------------------------------------ sensor mode
    @callback
    def _motion_changed(self, event: Event[EventStateChangedData]) -> None:
        new = event.data["new_state"]
        if new is not None and new.state == "on" and not self._following:
            self.hass.async_create_task(self._series())

    async def _series(self, _now: datetime | None = None) -> None:
        """A photo now and another every `pause` while the sensor still sees motion."""
        motion_state = self.hass.states.get(self.cam.motion_entity or "")
        if motion_state is None or motion_state.state != "on" or not self._active():
            self._following = False
            return
        self._following = True
        jpeg = await self._image()
        if jpeg is not None:
            await self._save(jpeg)
        self._series_timer = async_call_later(self.hass, self.settings.pause.total_seconds(), self._series_later)

    @callback
    def _series_later(self, _now: datetime) -> None:
        self._series_timer = None
        self.hass.async_create_task(self._series())

    # ------------------------------------------------------------------ common
    async def _image(self) -> bytes | None:
        try:
            image = await async_get_image(self.hass, self.cam.entity_id, timeout=15)
        except HomeAssistantError as err:
            self._failures += 1
            self.status.error = str(err)[:200]
            if self._failures == FAILURES_BEFORE_WARNING:   # some cameras fail an odd request
                _LOGGER.warning("%s: no image from %s (%s)", self.cam.name, self.cam.entity_id, err)
            self.notify()
            return None
        if self._failures >= FAILURES_BEFORE_WARNING:
            _LOGGER.info("%s: images are back", self.cam.name)
        self._failures, self.status.error = 0, None
        self.status.last_check = dt_util.now()
        return image.content

    async def _save(self, jpeg: bytes) -> None:
        now = dt_util.now()
        s = self.settings
        if self.status.last_photo and now - self.status.last_photo < s.pause:
            return
        hour = now.replace(minute=0, second=0, microsecond=0)
        if self._hour != hour:
            self._hour, self._in_hour = hour, 0
        if self._in_hour >= s.max_per_hour:
            return
        labels = await self._labels(jpeg)
        thumb = await self.hass.async_add_executor_job(motion.thumbnail, jpeg) if s.thumbnails else None
        try:
            key = await self.store.save(self.cam.camera_id, now, jpeg, labels, thumb)
        except S3Error as err:
            self.status.error = f"upload: {err}"[:200]
            _LOGGER.warning("%s: photo not uploaded (%s)", self.cam.name, err)
            self.notify()
            return
        today = now.date().isoformat()
        if self.status.day != today:
            self.status.day, self.status.photos_today = today, 0
        self.status.photos_today += 1
        self.status.last_photo, self.status.last_key, self.status.last_labels = now, key, labels
        self._in_hour += 1
        self.notify()

    async def _labels(self, jpeg: bytes) -> list[str]:
        s = self.settings
        if s.ai_provider != AI_CLOUDFLARE or not (s.ai_account and s.ai_token):
            return []
        try:
            objects = await ai.cloudflare_detect(self.session, s.ai_account, s.ai_token, jpeg)
            size = await self.hass.async_add_executor_job(motion.image_size, jpeg)
        except (ai.DetectionError, OSError) as err:
            _LOGGER.warning("%s: object detection failed, photo saved without labels (%s)", self.cam.name, err)
            return []
        if self.cam.kind == KIND_INDOOR:     # cars seen through a window are not interesting indoors
            return motion.labels(objects, size, allowed=INDOOR_LABELS, min_score=s.ai_min_score)
        changed = self.detector.changed if self.detector else None
        return motion.labels(objects, size, changed, min_score=s.ai_min_score)

    def photos_today(self) -> int:
        return self.status.photos_today if self.status.day == dt_util.now().date().isoformat() else 0

    def restore(self, photos_today: int, day: str | None) -> None:
        """Today's counter survives restarts (restored by the sensor)."""
        if day == dt_util.now().date().isoformat():
            self.status.photos_today, self.status.day = photos_today, day
