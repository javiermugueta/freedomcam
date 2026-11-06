"""Shared fixtures: an in-memory S3 bucket and custom integrations enabled."""
from __future__ import annotations

import pytest

from custom_components.freedomcam.s3 import S3Error


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


class FakeS3:
    """Stands in for S3Client: objects in a dict, optional failures."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.types: dict[str, str] = {}
        self.fail_get: S3Error | None = None
        self.fail_put: S3Error | None = None
        self.retention: int | None = None
        self.bucket = "test"

    async def put_object(self, key, body, content_type="application/octet-stream", cache_control=None):
        if self.fail_put:
            raise self.fail_put
        self.objects[key], self.types[key] = body, content_type

    async def get_object(self, key):
        if self.fail_get:
            raise self.fail_get
        return self.objects.get(key)

    async def delete_object(self, key):
        self.objects.pop(key, None)

    async def set_retention(self, days):
        self.retention = days


@pytest.fixture
def fake_s3() -> FakeS3:
    return FakeS3()
