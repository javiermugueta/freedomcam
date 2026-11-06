from __future__ import annotations

import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

from custom_components.freedomcam.s3 import S3Error
from custom_components.freedomcam.store import PhotoStore, photo_key

TZ = ZoneInfo("Europe/Madrid")


def t(h, m, s, d=6):
    return datetime(2026, 11, d, h, m, s, tzinfo=TZ)


def test_photo_key():
    assert photo_key("hall", t(18, 3, 10), ["person", "car"]) == "hall/2026/11/06/180310_car-person.jpg"
    assert photo_key("hall", t(8, 0, 1), []) == "hall/2026/11/06/080001.jpg"


async def test_save_and_flush_indexes(fake_s3):
    store = PhotoStore(fake_s3, retention_days=30)
    await store.save("hall", t(18, 3, 10), b"jpeg1", ["person"], thumb=b"th")
    await store.save("garden", t(9, 0, 0), b"jpeg22", [])
    assert "_index/2026/11/06.json" not in fake_s3.objects          # batched until flush
    await store.flush(date(2026, 11, 6))
    day = json.loads(fake_s3.objects["_index/2026/11/06.json"])
    assert [p["key"] for p in day["photos"]] == ["garden/2026/11/06/090000.jpg", "hall/2026/11/06/180310_person.jpg"]
    assert day["photos"][1]["thumb"] == "_thumbs/hall/2026/11/06/180310_person.jpg"
    assert "thumb" not in day["photos"][0]
    month = json.loads(fake_s3.objects["_index/2026/11.json"])
    assert month["days"]["06"] == {"photos": 2, "labels": {"person": 1}}


async def test_restart_continues_existing_index(fake_s3):
    first = PhotoStore(fake_s3)
    await first.save("hall", t(10, 0, 0), b"a", [])
    await first.flush(date(2026, 11, 6))
    second = PhotoStore(fake_s3)                                      # Home Assistant restarted
    await second.save("hall", t(11, 0, 0), b"b", ["person"])
    await second.flush(date(2026, 11, 6))
    assert len(json.loads(fake_s3.objects["_index/2026/11/06.json"])["photos"]) == 2
    assert json.loads(fake_s3.objects["_index/2026/11.json"])["days"]["06"]["photos"] == 2


async def test_unreadable_index_is_not_overwritten(fake_s3):
    first = PhotoStore(fake_s3)
    await first.save("hall", t(10, 0, 0), b"a", [])
    await first.flush(date(2026, 11, 6))
    second = PhotoStore(fake_s3)
    await second.save("hall", t(11, 0, 0), b"b", [])
    fake_s3.fail_get = S3Error(0, "ConnectionError")
    await second.flush(date(2026, 11, 6))
    assert len(json.loads(fake_s3.objects["_index/2026/11/06.json"])["photos"]) == 1   # untouched
    fake_s3.fail_get = None
    await second.flush(date(2026, 11, 6))                             # retried on the next flush
    assert len(json.loads(fake_s3.objects["_index/2026/11/06.json"])["photos"]) == 2


async def test_month_summary_forgets_expired_days(fake_s3):
    store = PhotoStore(fake_s3, retention_days=3)
    await store.save("hall", t(10, 0, 0, d=1), b"a", [])
    await store.save("hall", t(10, 0, 0, d=6), b"b", [])
    await store.flush(date(2026, 11, 6))
    assert list(json.loads(fake_s3.objects["_index/2026/11.json"])["days"]) == ["06"]


async def test_manifest(fake_s3):
    await PhotoStore(fake_s3, 30).write_manifest([{"id": "hall", "name": "Hall", "kind": "indoor"}],
                                                 "Europe/Madrid", t(12, 0, 0))
    m = json.loads(fake_s3.objects["freedomcam.json"])
    assert m["format"] == "freedomcam" and m["version"] == 1 and m["retention_days"] == 30
    assert m["cameras"][0]["id"] == "hall"
