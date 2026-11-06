"""SigV4 signatures must match botocore (the AWS SDK) byte for byte."""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from unittest.mock import patch
from urllib.parse import quote

import pytest
from botocore.auth import S3SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials

from custom_components.freedomcam.s3 import S3Client, _error_from, sign

NOW = datetime(2026, 11, 6, 18, 3, 10, tzinfo=UTC)


def _boto(method, url, headers, body, region):
    req = AWSRequest(method=method, url=url, data=body, headers=headers)
    req.headers["X-Amz-Content-SHA256"] = hashlib.sha256(body).hexdigest()
    with patch("botocore.auth.get_current_datetime", return_value=NOW.replace(tzinfo=None)):
        S3SigV4Auth(Credentials("AKID", "SECRET"), "s3", region).add_auth(req)
    return req.headers["Authorization"]


@pytest.mark.parametrize(("method", "path", "query", "body", "headers"), [
    ("PUT", "/bucket/hall/2026/11/06/180310_person.jpg", {}, b"jpegdata", {"content-type": "image/jpeg"}),
    ("GET", "/bucket", {"list-type": "2", "prefix": "hall/2026/", "max-keys": "1"}, b"", {}),
    ("PUT", "/bucket/c%C3%A1mara%20x/a.jpg", {}, b"x", {"content-type": "image/jpeg"}),
    ("PUT", "/bucket", {"lifecycle": ""}, b"<x/>", {"content-type": "application/xml", "content-md5": "abc=="}),
])
def test_signature_matches_botocore(method, path, query, body, headers):
    host = "acc.r2.cloudflarestorage.com"
    ours = sign(method, host, path, query, headers, hashlib.sha256(body).hexdigest(), "AKID", "SECRET", "auto", NOW)
    # the URL exactly as S3Client sends it (query values percent-encoded, "/" included)
    url = f"https://{host}{path}" + ("?" + "&".join(f"{k}={quote(v, safe='-_.~')}" for k, v in sorted(query.items()))
                                     if query else "")
    assert ours["authorization"] == _boto(method, url, dict(headers), body, "auto")


def test_virtual_host_target():
    c = S3Client(None, "https://s3.eu-west-1.amazonaws.com", "fotos", "a", "b", "eu-west-1", virtual_host=True)
    assert c._target("hall/a b.jpg") == ("fotos.s3.eu-west-1.amazonaws.com", "/hall/a%20b.jpg")   # noqa: SLF001
    c = S3Client(None, "http://minio.local:9000", "fotos", "a", "b", "us-east-1")
    assert c._target("") == ("minio.local:9000", "/fotos")   # noqa: SLF001


def test_error_parsing():
    err = _error_from(403, b"<Error><Code>SignatureDoesNotMatch</Code><Message>bad</Message></Error>")
    assert err.is_auth_error and not err.is_access_denied
    err = _error_from(403, b"<Error><Code>AccessDenied</Code></Error>")
    assert err.is_access_denied
    assert _error_from(404, b"").code == "NoSuchKey"
    assert _error_from(404, b"<Error><Code>NoSuchBucket</Code></Error>").code == "NoSuchBucket"
