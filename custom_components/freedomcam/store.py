"""Writes photos, thumbnails, indexes and the manifest following docs/bucket-format.md."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, datetime, timedelta
from typing import Any

from .const import FORMAT_VERSION, MANIFEST_KEY
from .s3 import S3Client, S3Error

_LOGGER = logging.getLogger(__name__)
JSON = "application/json"
NO_CACHE = "no-cache"


def photo_key(camera: str, when: datetime, labels: list[str]) -> str:
    suffix = "_" + "-".join(sorted(labels)) if labels else ""
    return f"{camera}/{when:%Y/%m/%d/%H%M%S}{suffix}.jpg"


def day_index_key(day: date) -> str:
    return f"_index/{day:%Y/%m/%d}.json"


def month_index_key(day: date) -> str:
    return f"_index/{day:%Y/%m}.json"


class PhotoStore:
    """Single writer of a freedomCam bucket. Index updates are batched and written by `flush()`."""

    def __init__(self, client: S3Client, retention_days: int = 0) -> None:
        self.client = client
        self.retention_days = retention_days
        self._days: dict[date, dict[str, Any]] = {}
        self._months: dict[tuple[int, int], dict[str, Any]] = {}
        self._dirty_days: set[date] = set()
        self._dirty_months: set[tuple[int, int]] = set()
        self._pending: list[dict[str, Any]] = []   # saved photos not yet added to the indexes
        self._lock = asyncio.Lock()

    async def write_manifest(self, cameras: list[dict[str, str]], timezone: str, now: datetime) -> None:
        """Write freedomcam.json. `indexed_since` (first day with a complete index) is kept from the existing
        manifest; a new one gets tomorrow, because today may have photos from before the indexes."""
        previous = await self._load(MANIFEST_KEY) or {}
        indexed_since = previous.get("indexed_since") or (now.date() + timedelta(days=1)).isoformat()
        manifest = {"format": "freedomcam", "version": FORMAT_VERSION, "timezone": timezone,
                    "retention_days": self.retention_days, "indexed_since": indexed_since, "cameras": cameras,
                    "updated": now.isoformat(timespec="seconds")}
        await self.client.put_object(MANIFEST_KEY, json.dumps(manifest, ensure_ascii=False, indent=1).encode(),
                                     JSON, NO_CACHE)

    async def save(self, camera: str, when: datetime, jpeg: bytes, labels: list[str],
                   thumb: bytes | None = None) -> str:
        """Upload a photo (and its thumbnail) and queue the index update. Returns the photo key."""
        key = photo_key(camera, when, labels)
        await self.client.put_object(key, jpeg, "image/jpeg")
        thumb_key = None
        if thumb:
            try:
                await self.client.put_object("_thumbs/" + key, thumb, "image/jpeg")
                thumb_key = "_thumbs/" + key
            except S3Error as err:                 # the photo is what matters
                _LOGGER.warning("Thumbnail of %s not uploaded: %s", key, err)
        entry: dict[str, Any] = {"camera": camera, "time": when.strftime("%H:%M:%S"), "key": key,
                                 "labels": sorted(labels), "size": len(jpeg)}
        if thumb_key:
            entry["thumb"] = thumb_key
        async with self._lock:
            self._pending.append({"date": when.date(), **entry})
        return key

    async def _add_pending(self) -> None:
        """Add the queued photos to the indexes. If an existing index cannot be read, retry later
        instead of starting it again (that would overwrite it)."""
        pending, self._pending = self._pending, []
        for i, item in enumerate(pending):
            day, entry = item["date"], {k: v for k, v in item.items() if k != "date"}
            try:
                doc, month = await self._day(day), await self._month(day)
            except S3Error as err:
                _LOGGER.warning("Index of %s not readable, will retry: %s", day, err)
                self._pending = pending[i:] + self._pending
                return
            doc["photos"].append(entry)
            doc["photos"].sort(key=lambda p: (p["time"], p["camera"]))
            stats = month["days"].setdefault(f"{day:%d}", {"photos": 0, "labels": {}})
            stats["photos"] += 1
            for label in entry["labels"]:
                stats["labels"][label] = stats["labels"].get(label, 0) + 1
            self._dirty_days.add(day)
            self._dirty_months.add((day.year, day.month))

    async def flush(self, today: date | None = None) -> None:
        """Write the indexes changed since the last flush; forget old days kept in memory."""
        async with self._lock:
            await self._add_pending()
            days, months = sorted(self._dirty_days), sorted(self._dirty_months)
            self._dirty_days, self._dirty_months = set(), set()
            pending_days, pending_months = set(), set()
            for day in days:
                try:
                    await self.client.put_object(day_index_key(day), _dump(self._days[day]), JSON, NO_CACHE)
                except S3Error as err:
                    _LOGGER.warning("Index of %s not written: %s", day, err)
                    pending_days.add(day)
            for ym in months:
                doc = self._months[ym]
                if self.retention_days and today:
                    oldest = today - timedelta(days=self.retention_days)
                    doc["days"] = {d: v for d, v in doc["days"].items()
                                   if date(ym[0], ym[1], int(d)) >= oldest}
                try:
                    await self.client.put_object(month_index_key(date(ym[0], ym[1], 1)), _dump(doc), JSON, NO_CACHE)
                except S3Error as err:
                    _LOGGER.warning("Summary of %04d-%02d not written: %s", *ym, err)
                    pending_months.add(ym)
            self._dirty_days |= pending_days
            self._dirty_months |= pending_months
            if today:                                   # keep only today and yesterday in memory
                keep = {today, today - timedelta(days=1)}
                self._days = {d: v for d, v in self._days.items() if d in keep or d in self._dirty_days}
                self._months = {m: v for m, v in self._months.items()
                                if m in {(d.year, d.month) for d in keep} or m in self._dirty_months}

    async def _day(self, day: date) -> dict[str, Any]:
        if day not in self._days:
            self._days[day] = await self._load(day_index_key(day)) or {
                "version": FORMAT_VERSION, "date": day.isoformat(), "photos": []}
        return self._days[day]

    async def _month(self, day: date) -> dict[str, Any]:
        ym = (day.year, day.month)
        if ym not in self._months:
            self._months[ym] = await self._load(month_index_key(day)) or {
                "version": FORMAT_VERSION, "month": f"{day:%Y-%m}", "days": {}}
        return self._months[ym]

    async def _load(self, key: str) -> dict[str, Any] | None:
        """Existing index (after a restart), or None if there is none. Raises S3Error if unreadable."""
        data = await self.client.get_object(key)
        if not data:
            return None
        try:
            return json.loads(data)
        except ValueError:
            _LOGGER.warning("%s is not valid JSON, starting it again", key)
            return None


def _dump(doc: dict[str, Any]) -> bytes:
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode()
