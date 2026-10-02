"""Run a complete DNS onboarding and send one fulfillment update."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from storefront_mail import DomainOnboarding, InfraiClient, OrderUpdate, onboard_sending_domain, send_order_update


def required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"{name} is required")
    return value


client = InfraiClient.from_environment()
status = onboard_sending_domain(
    client,
    DomainOnboarding(
        domain=required("STOREFRONT_DOMAIN"),
        spf_content=required("SPF_CONTENT"),
        dkim_name=required("DKIM_NAME"),
        dkim_content=required("DKIM_CONTENT"),
        dmarc_content=required("DMARC_CONTENT"),
    ),
)
message_id = send_order_update(
    client,
    OrderUpdate(
        customer_email=required("DEMO_CUSTOMER_EMAIL"),
        order_number="MEDIA-1042",
        status="fulfilled",
        title="Autumn Product Lookbook",
        download_url=required("PURCHASE_URL"),
    ),
)
print(f"domain verification: {status}")
print(f"fulfillment update message_id: {message_id}")
