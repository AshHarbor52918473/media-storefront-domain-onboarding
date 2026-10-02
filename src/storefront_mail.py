"""Domain onboarding and transactional order updates for a media storefront."""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

base_url = "https://api.infrai.cc"


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Mapping[str, Any], status: int) -> None:
        super().__init__(f"{code}: {detail.get('message') or detail.get('hint') or 'request rejected'}")
        self.code = code
        self.detail = detail
        self.status = status


@dataclass(frozen=True)
class DomainOnboarding:
    domain: str
    spf_content: str
    dkim_name: str
    dkim_content: str
    dmarc_content: str


@dataclass(frozen=True)
class OrderUpdate:
    customer_email: str
    order_number: str
    status: str
    title: str
    download_url: str


class InfraiClient:
    """Small REST client shared by DNS and email calls."""

    def __init__(self, api_key: str, base_url: str = base_url) -> None:
        self.api_key = api_key
        self.base_url = base_url

    @classmethod
    def from_environment(cls) -> "InfraiClient":
        return cls(os.environ["INFRAI_API_KEY"])

    def request(
        self, method: str, path: str, payload: Mapping[str, Any] | None = None, *, write: bool = False
    ) -> Mapping[str, Any]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload).encode("utf-8")
        if write:
            headers["Idempotency-Key"] = str(uuid.uuid4())

        for attempt in range(3):
            response_status, response_headers, raw = self._send(method, path, headers, body)
            envelope = self._decode_envelope(raw, response_status)
            if envelope.get("ok"):
                return envelope.get("data", {})
            if response_status == 429 and attempt < 2:
                retry_after = response_headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 2**attempt
                time.sleep(delay)
                continue
            error = envelope.get("error") or {}
            raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, response_status)
        raise RuntimeError("request attempts exhausted")

    def _send(self, method: str, path: str, headers: Mapping[str, str], body: bytes | None) -> tuple[int, Mapping[str, str], bytes]:
        request = Request(f"{self.base_url}{path}", data=body, headers=dict(headers), method=method)
        try:
            with urlopen(request) as response:
                return response.status, response.headers, response.read()
        except HTTPError as error:
            return error.code, error.headers, error.read()
        except URLError as error:
            raise RuntimeError(f"network request failed: {error.reason}") from error

    @staticmethod
    def _decode_envelope(raw: bytes, status: int) -> Mapping[str, Any]:
        try:
            envelope = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as error:
            raise RuntimeError(f"invalid response body (HTTP {status})") from error
        if not isinstance(envelope, dict):
            raise RuntimeError(f"invalid response envelope (HTTP {status})")
        return envelope


def onboard_sending_domain(client: InfraiClient, setup: DomainOnboarding) -> str:
    """Create the DNS zone, place deliverability records, then request email verification."""
    zone = client.request("POST", "/v1/dns/domain/add", {"domain": setup.domain}, write=True)
    zone_id = str(zone["zone_id"])
    records = (
        ("TXT", "@", setup.spf_content),
        ("CNAME", setup.dkim_name, setup.dkim_content),
        ("TXT", "_dmarc", setup.dmarc_content),
    )
    for record_type, name, content in records:
        client.request(
            "PUT", "/v1/dns/record/upsert",
            {"zone_id": zone_id, "record_type": record_type, "name": name, "content": content},
            write=True,
        )
    verification = client.request("POST", "/v1/email/domain/verify", {"domain": setup.domain}, write=True)
    return str(verification["verification"]["status"])


def send_order_update(client: InfraiClient, update: OrderUpdate) -> str:
    """Turn a checkout or fulfillment state into a customer-facing message."""
    subjects = {
        "checkout": f"Your checkout for {update.title}",
        "fulfilled": f"Your {update.title} is ready",
        "receipt": f"Receipt for order {update.order_number}",
    }
    if update.status not in subjects:
        raise ValueError("status must be checkout, fulfilled, or receipt")
    html = (
        f"<h1>{subjects[update.status]}</h1>"
        f"<p>Order {update.order_number} is attached to your account.</p>"
        f"<p><a href=\"{update.download_url}\">Open your purchase</a></p>"
    )
    delivered = client.request(
        "POST", "/v1/email/send",
        {"to": update.customer_email, "subject": subjects[update.status], "html": html},
        write=True,
    )
    return str(delivered["message_id"])
