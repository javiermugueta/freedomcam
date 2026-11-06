"""The real HTTP client against a local S3 emulator (moto): signatures, errors, lifecycle, indexes.

Run apart from the Home Assistant tests (their plugin blocks real sockets):
    pytest tests_live -p no:homeassistant -p no:socket
"""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

import aiohttp
import pytest

from custom_components.freedomcam.s3 import S3Client
from custom_components.freedomcam.storage import check_bucket
from custom_components.freedomcam.store import PhotoStore

moto_server = pytest.importorskip("moto.server")


@pytest.fixture(scope="module")
def endpoint():
    server = moto_server.ThreadedMotoServer(port=0, verbose=False)
    server.start()
    host, port = server.get_host_and_port()
    yield f"http://{host}:{port}"
    server.stop()


@pytest.fixture
async def session():
    async with aiohttp.ClientSession() as s:
        yield s


def client(session, endpoint, bucket="fotos", secret="secret", virtual=False):
    return S3Client(session, endpoint, bucket, "AKIAEXAMPLE", secret, "us-east-1", virtual)


async def test_check_bucket_creates_it_and_round_trips(session, endpoint):
    c = client(session, endpoint, "nuevo")
    assert await check_bucket(c) is None                          # created on the fly
    assert await c.get_object("freedomcam.json") is not None
    assert "_probe" not in await c.list_keys()
    assert await check_bucket(client(session, endpoint, "otro"), create=False) == "bucket_not_found"


async def test_objects_with_odd_names(session, endpoint):
    c = client(session, endpoint, "raros")
    await c.create_bucket()
    key = "cámara 1/2026/11/06/180310_person.jpg"
    await c.put_object(key, b"jpeg", "image/jpeg")
    assert await c.get_object(key) == b"jpeg"
    assert await c.list_keys("cámara 1/") == [key]
    assert await c.get_object("nada.jpg") is None
    await c.delete_object(key)
    assert await c.get_object(key) is None


async def test_lifecycle_keeps_other_rules(session, endpoint):
    c = client(session, endpoint, "ciclo")
    await c.create_bucket()
    other = (b'<LifecycleConfiguration xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><Rule><ID>mine</ID>'
             b"<Filter><Prefix>logs/</Prefix></Filter><Status>Enabled</Status><Expiration><Days>7</Days>"
             b"</Expiration></Rule></LifecycleConfiguration>")
    await c.request("PUT", query={"lifecycle": ""}, body=other,
                    headers={"content-type": "application/xml",
                             "content-md5": base64.b64encode(hashlib.md5(other).digest()).decode()})
    await c.set_retention(30)
    xml = (await c.request("GET", query={"lifecycle": ""})).decode()
    assert "mine" in xml and "freedomcam-retention" in xml and "<Days>30</Days>" in xml
    await c.set_retention(10)                                      # replaced, not duplicated
    xml = (await c.request("GET", query={"lifecycle": ""})).decode()
    assert xml.count("freedomcam-retention") == 1 and "<Days>10</Days>" in xml
    await c.set_retention(0)
    xml = (await c.request("GET", query={"lifecycle": ""})).decode()
    assert "freedomcam-retention" not in xml and "mine" in xml


async def test_store_end_to_end(session, endpoint):
    c = client(session, endpoint, "fin")
    await c.create_bucket()
    store = PhotoStore(c, 30)
    when = datetime(2026, 11, 6, 18, 3, 10, tzinfo=ZoneInfo("Europe/Madrid"))
    key = await store.save("hall", when, b"jpeg", ["person"], b"thumb")
    await store.flush(date(2026, 11, 6))
    assert json.loads(await c.get_object("_index/2026/11/06.json"))["photos"][0]["key"] == key
    assert await c.get_object("_thumbs/" + key) == b"thumb"
