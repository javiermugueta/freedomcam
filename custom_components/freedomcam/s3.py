"""Minimal async client for S3-compatible storage (AWS Signature Version 4).

Only what freedomCam needs: put/get/delete objects, list, create the bucket and manage one
lifecycle rule. No external SDK, so it works with R2, S3, B2, Wasabi, MinIO… alike.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import UTC, datetime
from urllib.parse import quote, urlparse
from xml.etree import ElementTree as ET

import aiohttp

S3_NS = "http://s3.amazonaws.com/doc/2006-03-01/"
LIFECYCLE_RULE_ID = "freedomcam-retention"


class S3Error(Exception):
    """Error answered by the storage service (or a network failure, with status 0)."""

    def __init__(self, status: int, code: str, message: str = "") -> None:
        super().__init__(f"{status} {code}: {message}".strip(": "))
        self.status, self.code, self.message = status, code, message

    @property
    def is_auth_error(self) -> bool:
        return self.code in ("InvalidAccessKeyId", "SignatureDoesNotMatch", "InvalidToken",
                             "Unauthorized") or self.status == 401

    @property
    def is_access_denied(self) -> bool:
        return self.code == "AccessDenied" or (self.status == 403 and not self.is_auth_error)


def _uri(text: str, safe: str = "-_.~") -> str:
    return quote(text, safe=safe)


def _hmac(key: bytes, text: str) -> bytes:
    return hmac.new(key, text.encode(), hashlib.sha256).digest()


def sign(method: str, host: str, path: str, query: dict[str, str], headers: dict[str, str],
         payload_hash: str, access_key: str, secret_key: str, region: str,
         now: datetime | None = None) -> dict[str, str]:
    """Return `headers` plus x-amz-date, x-amz-content-sha256 and the SigV4 Authorization header.

    `path` must already be URI-encoded (each segment, keeping the slashes).
    """
    now = (now or datetime.now(UTC)).astimezone(UTC)
    date, stamp = now.strftime("%Y%m%d"), now.strftime("%Y%m%dT%H%M%SZ")
    all_headers = {k.lower(): str(v).strip() for k, v in headers.items()}
    all_headers |= {"host": host, "x-amz-content-sha256": payload_hash, "x-amz-date": stamp}
    signed = ";".join(sorted(all_headers))
    canonical_query = "&".join(f"{_uri(k)}={_uri(v)}" for k, v in sorted(query.items()))
    canonical = "\n".join([method, path, canonical_query,
                           *(f"{k}:{all_headers[k]}" for k in sorted(all_headers)), "", signed, payload_hash])
    scope = f"{date}/{region}/s3/aws4_request"
    to_sign = "\n".join(["AWS4-HMAC-SHA256", stamp, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    key = _hmac(_hmac(_hmac(_hmac(("AWS4" + secret_key).encode(), date), region), "s3"), "aws4_request")
    signature = hmac.new(key, to_sign.encode(), hashlib.sha256).hexdigest()
    all_headers["authorization"] = (f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, "
                                    f"SignedHeaders={signed}, Signature={signature}")
    del all_headers["host"]
    return all_headers


def _error_from(status: int, body: bytes) -> S3Error:
    code, message = f"HTTP{status}", ""
    try:
        root = ET.fromstring(body)
        code = root.findtext("Code") or root.findtext(f"{{{S3_NS}}}Code") or code
        message = root.findtext("Message") or root.findtext(f"{{{S3_NS}}}Message") or ""
    except ET.ParseError:
        pass
    if status == 404 and code.startswith("HTTP"):
        code = "NoSuchKey"
    return S3Error(status, code, message)


class S3Client:
    """S3 client bound to one bucket."""

    def __init__(self, session: aiohttp.ClientSession, endpoint: str, bucket: str, access_key: str,
                 secret_key: str, region: str = "auto", virtual_host: bool = False,
                 timeout: float = 30) -> None:
        url = urlparse(endpoint if "://" in endpoint else "https://" + endpoint)
        self._session = session
        self._scheme, self._host = url.scheme, url.netloc
        self.bucket = bucket
        self._access_key, self._secret_key = access_key, secret_key
        self.region = region or "auto"
        self._virtual_host = virtual_host
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    def _target(self, key: str) -> tuple[str, str]:
        """(host, encoded path) for an object key ("" = the bucket itself)."""
        key_path = "/".join(_uri(p) for p in key.split("/")) if key else ""
        if self._virtual_host:
            return f"{self.bucket}.{self._host}", "/" + key_path
        return self._host, f"/{_uri(self.bucket)}" + (f"/{key_path}" if key else "")

    async def request(self, method: str, key: str = "", query: dict[str, str] | None = None,
                      body: bytes = b"", headers: dict[str, str] | None = None,
                      ok: tuple[int, ...] = (200, 204)) -> bytes:
        query = query or {}
        host, path = self._target(key)
        signed = sign(method, host, path, query, headers or {}, hashlib.sha256(body).hexdigest(),
                      self._access_key, self._secret_key, self.region)
        url = f"{self._scheme}://{host}{path}"
        if query:
            url += "?" + "&".join(f"{_uri(k)}={_uri(v)}" for k, v in sorted(query.items()))
        try:
            async with self._session.request(method, url, data=body or None, headers=signed,
                                             timeout=self._timeout, skip_auto_headers=("Content-Type",)) as r:
                data = await r.read()
                if r.status not in ok:
                    raise _error_from(r.status, data)
                return data
        except (aiohttp.ClientError, TimeoutError) as err:
            raise S3Error(0, "ConnectionError", str(err) or type(err).__name__) from err

    # ---------------------------------------------------------------- objects
    async def put_object(self, key: str, body: bytes, content_type: str = "application/octet-stream",
                         cache_control: str | None = None) -> None:
        headers = {"content-type": content_type}
        if cache_control:
            headers["cache-control"] = cache_control
        await self.request("PUT", key, body=body, headers=headers)

    async def get_object(self, key: str) -> bytes | None:
        """Object content, or None if it does not exist."""
        try:
            return await self.request("GET", key)
        except S3Error as err:
            if err.status == 404 and err.code != "NoSuchBucket":
                return None
            raise

    async def delete_object(self, key: str) -> None:
        await self.request("DELETE", key)

    async def list_keys(self, prefix: str = "", max_keys: int = 1000) -> list[str]:
        """Keys under `prefix` (first page only: enough for checks)."""
        data = await self.request("GET", query={"list-type": "2", "prefix": prefix, "max-keys": str(max_keys)})
        root = ET.fromstring(data)
        return [e.text or "" for e in root.iter() if e.tag.endswith("}Key") or e.tag == "Key"]

    # ---------------------------------------------------------------- bucket
    async def create_bucket(self) -> None:
        body = b""
        if self._virtual_host and self.region not in ("us-east-1", "auto"):
            body = (f'<CreateBucketConfiguration xmlns="{S3_NS}"><LocationConstraint>{self.region}'
                    f"</LocationConstraint></CreateBucketConfiguration>").encode()
        await self.request("PUT", body=body)

    async def set_retention(self, days: int) -> None:
        """Create/replace (days > 0) or remove (days == 0) freedomCam's expiration rule, keeping other rules."""
        try:
            current = await self.request("GET", query={"lifecycle": ""})
            rules = [r for r in ET.fromstring(current) if r.tag.endswith("Rule")]
        except S3Error as err:
            if err.code != "NoSuchLifecycleConfiguration" and err.status != 404:
                raise
            rules = []
        rules = [r for r in rules if (r.findtext(f"{{{S3_NS}}}ID") or r.findtext("ID")) != LIFECYCLE_RULE_ID]
        if days > 0:
            rule = ET.fromstring(
                f"<Rule><ID>{LIFECYCLE_RULE_ID}</ID><Filter><Prefix></Prefix></Filter><Status>Enabled</Status>"
                f"<Expiration><Days>{int(days)}</Days></Expiration></Rule>")
            rules.append(rule)
        if not rules:
            await self.request("DELETE", query={"lifecycle": ""}, ok=(200, 204, 404))
            return
        root = ET.Element("LifecycleConfiguration", xmlns=S3_NS)
        for r in rules:
            for e in r.iter():                       # drop namespaces from rules read back
                e.tag = e.tag.split("}", 1)[-1]
            root.append(r)
        body = ET.tostring(root, encoding="utf-8", xml_declaration=False)
        md5 = base64.b64encode(hashlib.md5(body).digest()).decode()   # noqa: S324 - required by S3
        await self.request("PUT", query={"lifecycle": ""}, body=body,
                           headers={"content-type": "application/xml", "content-md5": md5})
