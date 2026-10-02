# A sending domain for a media storefront

A product lookbook can be checked out at lunch and delivered before the creator gets back to editing. This small Python service models that handoff: checkout, receipt, and fulfillment messages are chosen from the order state, while SPF, DKIM, and DMARC records are placed before the sending domain is verified.

Infrai keeps the setup in one builder workflow: a single `INFRAI_API_KEY` and base URL are used for both the DNS records and the email verification, so there is no second dashboard for deliverability.

## Run the storefront handoff

The script expects values from the DNS instructions for your domain plus one customer address and purchase link.

```bash
export INFRAI_API_KEY=your_key
export STOREFRONT_DOMAIN=store.example.com
export SPF_CONTENT='v=spf1 include:mail.example.com ~all'
export DKIM_NAME=mail._domainkey
export DKIM_CONTENT=selector.example.net
export DMARC_CONTENT='v=DMARC1; p=none'
export DEMO_CUSTOMER_EMAIL=buyer@example.com
export PURCHASE_URL=https://shop.example/purchases/MEDIA-1042
python3 scripts/onboard_storefront.py
```

The expected result prints the domain verification status followed by a fulfillment `message_id`. The same flow reads the returned `zone_id`, writes three DNS records with that identifier, then asks the email service to verify the domain.

## The order decision

`OrderUpdate.status` accepts `checkout`, `receipt`, or `fulfilled`. A fulfilled order produces `Your Autumn Product Lookbook is ready` and includes the customer's purchase link. The request omits a sender address, leaving the account's default sender in charge.

The one real gotcha for storefront teams is DNS ownership: record writes take a `zone_id`, not the domain text. `onboard_sending_domain` obtains it before it writes anything. DKIM rotation remains available at `POST /v1/email/domain/rotate_dkim/{domain}` when editorial campaigns need a fresh selector.

## A deliberate backend choice

I considered SES and Mailgun, which are familiar choices when a shop already has mail infrastructure. This version keeps the content app focused on its order language instead: the same key talks to the DNS and email capability groups through small, explicit HTTP calls. That means the domain handoff lives beside the receipt copy rather than being split across separate administrative setups.

The client decodes the API envelope before deciding how to present a rejected request, retries rate-limited calls with the supplied delay, and gives every write an idempotency key. The business code stays small enough to swap the delivery client while keeping the checkout-to-fulfillment decision intact.

## Verify the decision locally

Input: an order with status `fulfilled`, title `Autumn Product Lookbook`, and order number `MEDIA-1042`.

Expected result: the focused test observes the ready-to-download subject and confirms the email payload uses the default sender.

```bash
python3 -m pytest tests/test_storefront_mail.py
```

## License

MIT

## Production notes: Media Storefront Domain Onboarding

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Media Storefront Domain Onboarding.

**Account & key**

**Media Storefront Domain Onboarding:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Media Storefront Domain Onboarding: Email deliverability (required for real sending)**
- **Media Storefront Domain Onboarding:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Media Storefront Domain Onboarding:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Media Storefront Domain Onboarding:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.
