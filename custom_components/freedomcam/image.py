"""QR code to connect the iOS app (only when read-only app keys are set in the options)."""
from __future__ import annotations

from homeassistant.components.image import ImageEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import FreedomCamConfigEntry
from .connection import connection_link, qr_png
from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: FreedomCamConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    link = connection_link(entry.data, entry.options)
    if link:
        async_add_entities([AppConnectionQR(hass, entry, link)])


class AppConnectionQR(ImageEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "app_qr"
    _attr_content_type = "image/png"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, hass: HomeAssistant, entry: FreedomCamConfigEntry, link: str) -> None:
        super().__init__(hass)
        self._link = link
        self._png: bytes | None = None
        self._attr_unique_id = f"{entry.entry_id}_app_qr"
        self._attr_image_last_updated = dt_util.utcnow()
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name=f"freedomCam {entry.title}",
                                            manufacturer="freedomCam", model="Bucket")

    async def async_image(self) -> bytes | None:
        if self._png is None:
            self._png = await self.hass.async_add_executor_job(qr_png, self._link)
        return self._png
