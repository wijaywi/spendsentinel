# Production integration setup

This project now contains an OIDC/JWKS access-token verifier, a normalized sanctions-provider adapter, and PayPal Orders API sandbox calls. It does not include credentials, a paid sanctions-provider contract, or permission to process live payments.

## 1. OIDC authentication and scopes

Set `APP_ENV=production`, `DEBUG=false`, `AUTH_ENABLED=true`, `OIDC_ISSUER`, `OIDC_AUDIENCE`, and `OIDC_JWKS_URL`. The API validates RS256 access-token signatures against the issuer's JWKS and requires `exp`, `iat`, `sub`, `iss`, and `aud`. Keep private signing keys with the identity provider. Supply bearer access tokens, never ID tokens.

Configure `CORS_ORIGINS` with the exact HTTPS web-app origins. `HOST` defaults to loopback; when deploying behind a managed TLS-terminating reverse proxy, set the bind address as required by the hosting platform and restrict network access to that proxy.

The API uses these scopes:

- `sentinel:read` for integration status and read-only views.
- `sentinel:agents:manage` for agent registration and policy changes.
- `sentinel:agents:evaluate` for policy evaluation.
- `sentinel:payments:validate` for payment instruction validation.
- `sentinel:payments:create` for sandbox order creation.
- `sentinel:payments:capture` for sandbox capture.
- `sentinel:compliance:screen` for sending a party to the configured screening adapter.
- `sentinel:evidence:write` for storing evidence.
- `sentinel:disputes:prepare` for preparing a dispute response.

For owner-controlled policy changes, the authenticated token `sub` must match the registered `owner_id`. A self-asserted caller header is not used as identity. Map identity-provider roles to the `sentinel:admin` scope only for administrators.

The local development default disables access-token verification and grants a local demo principal. The server binds to loopback by default. Never expose development mode to a network; production startup rejects missing OIDC configuration and `DEBUG=true`.

## 2. AI-assisted purchase intent

The hackathon demo exposes `POST /api/agents/interpret-and-evaluate`. It sends the supplied natural-language instruction to a configured OpenAI-compatible chat-completions endpoint, asks for a small JSON extraction, validates the extracted amount/currency/MCC with the same transaction schema as direct evaluation, then applies the deterministic Agent Guard. The model does not set policy, approve a purchase, or call PayPal.

For Google Gemini, enable **Generative Language API** (`generativelanguage.googleapis.com`) in the Google Cloud project if API enablement is required, then create/view a Gemini key in [Google AI Studio](https://aistudio.google.com/apikey). Set:

```dotenv
AI_ENABLED=true
AI_API_URL=https://generativelanguage.googleapis.com/v1beta/openai/chat/completions
AI_MODEL=gemini-3.8-flash
AI_API_KEY=your-google-ai-studio-gemini-api-key
```

The Gemini model name must be available to your AI Studio project; if not, replace it with a supported model ID shown in AI Studio. `AI_API_KEY` must remain private and should be loaded from a local untracked `.env` or secret manager. The `.env.example` keeps AI disabled.

The integration can also use LM Studio at `http://127.0.0.1:1234/v1/chat/completions`: start LM Studio, load a chat model, and set `AI_MODEL` to the exact model ID returned by `http://127.0.0.1:1234/v1/models`. A local loopback model does not need `AI_API_KEY` unless local API-key protection has been enabled. Remote providers require HTTPS and an API key held in an environment secret store. An unconfigured or unavailable endpoint fails explicitly and does not result in a payment approval.
Remote AI endpoints must also use an explicitly allowlisted hostname (`AI_ALLOWED_HOSTS`); keep redirects disabled and do not point this setting at an untrusted host. The Gemini example uses `generativelanguage.googleapis.com`.

The natural-language instruction is transmitted to the configured AI provider. Use synthetic data for the hackathon demo and review the provider's data-processing terms before sending any personal or confidential information. The actual provider and model must be disclosed in the project submission.

## 3. Sanctions-screening provider

No licensed provider was selected or configured. Do not send personal data to an arbitrary endpoint. Select a provider under contract, confirm jurisdiction coverage, permitted purpose, data-processing terms, retention, update frequency, match review, and escalation procedures, then configure its adapter over HTTPS.

Set `SANCTIONS_SCREENING_ENABLED=true`, `SANCTIONS_PROVIDER_NAME`, `SANCTIONS_API_URL`, `SANCTIONS_ALLOWED_HOSTS`, and `SANCTIONS_API_TOKEN` using a secret manager. `SANCTIONS_ALLOWED_HOSTS` must contain the exact contracted adapter host; arbitrary hosts and redirects are rejected. The configured adapter accepts a POST JSON body:

```json
{
  "full_name": "Example Person",
  "country": "GB",
  "date_of_birth": "1980-01-02",
  "reference": "case-123"
}
```

It must respond with this normalized contract:

```json
{
  "status": "CLEAR",
  "checked_at": "2026-11-03T00:00:00Z",
  "source_updated_at": "2026-11-02T00:00:00Z",
  "matches": []
}
```

`status` is `CLEAR`, `POTENTIAL_MATCH`, or `REVIEW_REQUIRED`. A `CLEAR` response containing matches is rejected. Missing configuration, network failure, malformed data, and provider errors return service unavailable; they never become a clear result. The API response always marks `authoritative_decision=false` and `requires_human_review=true`. The application does not decide legal permissibility or automatically block/clear a party.

## 4. PayPal payment sandbox

Create sandbox REST app credentials in the PayPal Developer Dashboard. Set `PAYPAL_SANDBOX_ENABLED=true`, `PAYPAL_API_BASE_URL=https://api-m.sandbox.paypal.com`, `PAYPAL_CLIENT_ID`, and `PAYPAL_CLIENT_SECRET`.

- Find sandbox REST credentials under the Developer Dashboard's Sandbox **Apps & Credentials** area. The **Testing Tools > Sandbox Accounts** area provides synthetic Personal (buyer) and Business (seller) accounts.
- The local demo's PayPal Sandbox form calls `POST /api/payments/orders` and sends `PayPal-Request-Id`.
- Open the returned approval link and sign in at `www.sandbox.paypal.com` using a Personal sandbox buyer account. The buyer approval is an explicit step; AI decisions do not create or capture an order.
- After approval, enter the order ID and a distinct capture request ID in the demo. `POST /api/payments/orders/{order_id}/capture` checks that PayPal reports `APPROVED` and then captures with `PayPal-Request-Id`.
- Confirm the test transaction in the sandbox Business seller account.
- `POST /api/payments/webhooks/paypal` verifies signatures with PayPal before recording a minimal event ID/type for deduplication. It does not store raw webhook payloads.

### Register the webhook and find `PAYPAL_WEBHOOK_ID`

`PAYPAL_WEBHOOK_ID` is created by PayPal when you register a webhook for your **Sandbox REST app**. It is not the REST app's Client ID or Secret. Webhook subscriptions belong to a specific REST app, so the webhook must be registered under the same sandbox app whose Client ID and Secret are configured here; events from another app on the same account are not delivered to this subscription.

You can register it in the Developer Dashboard as below, or use PayPal's [Webhooks Management v1 API](https://developer.paypal.com/api/webhooks/v1/). The API's documented authorization is an OAuth **Client Credentials** bearer token from `https://api-m.sandbox.paypal.com/v1/oauth2/token` with the `https://uri.paypal.com/services/applications/webhooks` scope (access/update Webhooks). Use the sandbox REST app credentials and confirm the token includes/permits that scope:

- `POST https://api-m.sandbox.paypal.com/v1/notifications/webhooks` creates a subscription. Send a JSON body with `url` set to the externally reachable listener URL and `event_types` set to the event subscriptions, for example:

  ```json
  {
    "url": "https://<your-tunnel-host>/api/payments/webhooks/paypal",
    "event_types": [
      {"name": "CHECKOUT.ORDER.APPROVED"},
      {"name": "PAYMENT.CAPTURE.COMPLETED"}
    ]
  }
  ```

  The create response includes the webhook `id`; copy that value to `PAYPAL_WEBHOOK_ID`.
- `GET https://api-m.sandbox.paypal.com/v1/notifications/webhooks` lists subscriptions for the authenticated app and can help retrieve an existing ID.
- `GET https://api-m.sandbox.paypal.com/v1/notifications/webhooks/{webhook_id}` shows one webhook's details.
- `GET https://api-m.sandbox.paypal.com/v1/notifications/webhooks-event-types` lists available event types. PayPal permits up to 10 webhook URLs per app.

The list endpoint's optional `anchor_type` query parameter defaults to `APPLICATION`; `ACCOUNT` filters at account scope. For the standard REST-app webhook setup, leave it at the default unless you explicitly need account-anchored subscriptions. A `200` response contains a `webhooks` array; use the `id` from the matching URL/app entry.

To inspect an existing webhook, call `GET /v1/notifications/webhooks/{webhook_id}` with the same sandbox bearer token. A successful response includes the webhook `id`, listener `url`, and subscribed `event_types`.

To change an existing subscription, PayPal's update endpoint is `PATCH /v1/notifications/webhooks/{webhook_id}`. Its endpoint guide says to use `replace` for `/url` or `/event_types`; `event_types` replaces the subscription list, so include every event that must remain enabled:

```json
[
  {
    "op": "replace",
    "path": "/url",
    "value": "https://<your-tunnel-host>/api/payments/webhooks/paypal"
  },
  {
    "op": "replace",
    "path": "/event_types",
    "value": [
      {"name": "CHECKOUT.ORDER.APPROVED"},
      {"name": "PAYMENT.CAPTURE.COMPLETED"}
    ]
  }
]
```

Submit the JSON array with `Content-Type: application/json` and the Webhooks-scope bearer token. Confirm the returned URL and event list with a subsequent `GET` before relying on delivery.

The `Authorization` header must contain the OAuth access token, not the Client ID or Secret directly. Since this project already depends on `httpx` and loads `.env` through its settings, run the following from the project root after entering the sandbox Client ID and Secret in `.env`:

```python
import asyncio
import httpx

from app.config import settings


async def main():
    scope = "https://uri.paypal.com/services/applications/webhooks"
    async with httpx.AsyncClient(timeout=15.0) as client:
        token_response = await client.post(
            "https://api-m.sandbox.paypal.com/v1/oauth2/token",
            auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_CLIENT_SECRET),
            data={"grant_type": "client_credentials", "scope": scope},
        )
        token_response.raise_for_status()
        access_token = token_response.json()["access_token"]

        response = await client.get(
            "https://api-m.sandbox.paypal.com/v1/notifications/webhooks",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        print(response.json())


asyncio.run(main())
```

Find the webhook ID in `response.json()["webhooks"]` by matching the configured listener URL and app. Keep the token and `.env` private; never paste credentials or live tokens into chat, source code, or a public repository. If PayPal returns an authorization/scope error, confirm the token was requested for the Sandbox app and that the app/token is permitted to access Webhooks.

To register through the Developer Dashboard instead:

1. Sign in to the PayPal Developer Dashboard and select **Sandbox**.
2. Open **Apps & Credentials**, select the REST app whose Client ID and Secret are configured above, and open its **Webhooks** section.
3. Choose **Add Webhook** and enter a publicly reachable HTTPS URL ending in `/api/payments/webhooks/paypal`.
4. Subscribe to the event types needed for your demo, then save the webhook. PayPal permits up to 10 webhook URLs per app.
5. Copy the webhook's ID from its details in the dashboard and set `PAYPAL_WEBHOOK_ID` in the local `.env`.

The local address `http://127.0.0.1:8000` is not reachable by PayPal. For local webhook testing, use an HTTPS tunnel you control and point the webhook URL at the tunnel's forwarded `/api/payments/webhooks/paypal` path; otherwise skip webhook delivery testing. Keep the tunnel private to this test, stop it afterwards, and do not expose credentials. Creating a webhook is optional for the basic create, buyer-approval, and capture demo; the ID is required only for webhook signature verification.

### Use the Webhooks simulator carefully

In the PayPal Developer Dashboard's Webhooks simulator, configure the listener URL to the same reachable HTTPS URL registered for the sandbox app, for example `https://<your-tunnel-host>/api/payments/webhooks/paypal`. Start the app on port 8000 and the HTTPS tunnel before selecting **Send Test**. Do not enter `localhost` or `127.0.0.1`; PayPal cannot connect to those addresses.

PayPal documents two verification methods: calculate and verify the message signature locally, or post the message, headers, and stored webhook ID to PayPal's verify-signature API. This application uses the latter method. It must not process an event as trusted unless PayPal reports verification success.

The simulator sends mock event data to check delivery/connectivity. Per PayPal's simulator notice, those mock events cannot be verified, resent, or inspected as normal event notifications. This application's webhook route intentionally calls PayPal's signature-verification API and rejects events that do not verify. Therefore simulator delivery can demonstrate connectivity only; it does not prove that the signature-verification path accepts a real event. Use a genuine sandbox event generated by the configured REST app for end-to-end signature verification. The endpoint returns non-2xx when verification fails. PayPal's delivery documentation says non-2xx responses are retried up to 25 times over 3 days, and failed deliveries may be manually resent from the Webhook Events dashboard. Avoid repeatedly sending simulator mocks to this strict verification endpoint; monitor the response and delivery status, and use genuine app events for signature tests.

For genuine events, PayPal considers receipt successful when the listener returns HTTP 200 or another 2xx response. This prototype returns 2xx after a verified event is recorded or recognized as a duplicate. Business processing and durable retry/queue handling are not implemented yet.

The management endpoints above are distinct from this application's receiver at `POST /api/payments/webhooks/paypal`. PayPal also offers event lookup and resend endpoints under `/v1/notifications/webhooks-events`; those act on genuine event notifications and do not make simulator-generated mock events verifiable.

This release rejects non-sandbox PayPal hosts. No live payment or production capture endpoint is enabled. A production launch requires a separate security, legal, compliance, and PayPal access review, plus durable order and webhook processing, reconciliation, monitoring, and incident-response procedures.

This flow follows PayPal's sandbox pattern of separate developer-dashboard credentials, buyer approval on the sandbox web site, and API calls to `api-m.sandbox.paypal.com`. Sandbox logins and credentials are distinct from live PayPal credentials.

## Before deployment

- Replace SQLite with a managed transactional database and deploy migrations.
- Put OIDC and provider credentials in a secret manager; rotate them and restrict their access.
- Use TLS, rate limits, audit retention, backups, monitoring, and incident response.
- Review data minimization, privacy notices, consent/legal basis, deletion, and data-processing agreements.
- Test identity-provider key rotation, revoked tokens, provider timeouts, duplicate webhooks, idempotency, and concurrent requests in a non-production environment.
- Do not treat syntax checks, a provider `CLEAR` result, or a successful sandbox capture as a guarantee of payment success or legal compliance.
