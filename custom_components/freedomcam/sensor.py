"""One sensor per camera: photos saved today, with the last photo as attributes."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import RestoreSensor, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FreedomCamConfigEntry
from .const import DOMAIN
from .watcher import CameraWatcher


async def async_setup_entry(hass: HomeAssistant, entry: FreedomCamConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    for subentry_id, watcher in entry.runtime_data.watchers.items():
        async_add_entities([PhotosTodaySensor(entry, subentry_id, watcher)], config_subentry_id=subentry_id)


class PhotosTodaySensor(RestoreSensor):
    _attr_has_entity_name = True
    _attr_translation_key = "photos_today"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, entry: FreedomCamConfigEntry, subentry_id: str, watcher: CameraWatcher) -> None:
        self._watcher = watcher
        self._attr_unique_id = f"{entry.entry_id}_{watcher.cam.camera_id}_photos_today"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, f"{entry.entry_id}_{subentry_id}")},
                                            name=watcher.cam.name, manufacturer="freedomCam",
                                            model=f"{entry.title}/{watcher.cam.camera_id}")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_sensor_data()
        extra = await self.async_get_last_state()
        if last and last.native_value is not None and extra:
            self._watcher.restore(int(float(last.native_value)), extra.attributes.get("day"))
        self.async_on_remove(self._watcher.add_listener(self.async_write_ha_state))

    @property
    def native_value(self) -> int:
        return self._watcher.photos_today()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        s = self._watcher.status
        return {
            "day": s.day,
            "last_photo": s.last_photo.isoformat() if s.last_photo else None,
            "last_key": s.last_key,
            "last_labels": s.last_labels,
            "last_check": s.last_check.isoformat() if s.last_check else None,
            "change": round(s.change, 3) if s.change is not None else None,
            "error": s.error,
        }
