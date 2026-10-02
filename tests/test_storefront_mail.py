import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from storefront_mail import OrderUpdate, send_order_update


class RecordingClient:
    def __init__(self) -> None:
        self.calls = []

    def request(self, method, path, payload, *, write):
        self.calls.append((method, path, payload, write))
        return {"message_id": "msg_lookbook_1042"}


def test_fulfillment_update_uses_ready_subject_and_default_sender():
    client = RecordingClient()
    message_id = send_order_update(
        client,
        OrderUpdate(
            customer_email="buyer@example.com",
            order_number="MEDIA-1042",
            status="fulfilled",
            title="Autumn Product Lookbook",
            download_url="https://shop.example/purchases/1042",
        ),
    )

    method, path, payload, write = client.calls[0]
    assert message_id == "msg_lookbook_1042"
    assert (method, path, write) == ("POST", "/v1/email/send", True)
    assert payload["subject"] == "Your Autumn Product Lookbook is ready"
    assert "from" not in payload


def test_rejects_an_order_state_without_a_customer_message():
    with pytest.raises(ValueError, match="status must be"):
        send_order_update(
            RecordingClient(),
            OrderUpdate("buyer@example.com", "MEDIA-1042", "refunded", "Lookbook", "https://shop.example/purchases/1042"),
        )
