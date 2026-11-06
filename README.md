# SpendSentinel

SpendSentinel is a hackathon prototype for safer AI-agent commerce. A configured AI model extracts purchase intent from natural language; a deterministic spending-policy engine then approves, denies, or escalates the resulting proposal. Approved evaluations can be followed by a separately initiated PayPal Orders API sandbox checkout. The model never authorizes or captures a payment. SpendSentinel is an independent project and is not an official PayPal product.

## Hackathon project description

AI agents can understand purchase requests, but merchants need predictable controls before those agents spend money. Sentinel turns a buyer's natural-language purchase instruction into a structured proposal, checks that proposal against an agent's merchant, currency, per-transaction, and daily spending policies, and returns an auditable decision. PayPal Orders API sandbox support demonstrates the checkout path without enabling live transactions.

**PayPal technology:** PayPal REST Orders API in sandbox, including order creation, buyer approval before capture, request idempotency, and webhook signature verification.

**AI tool:** A configurable OpenAI-compatible chat-completions model performs natural-language purchase-field extraction. Set `AI_MODEL` and provider endpoint/key for the chosen model. The AI output is untrusted input and is validated before deterministic Agent Guard evaluation. No model call is made unless `AI_ENABLED=true`.

The project is a proof of concept, not a production payment authorization or compliance service. Use synthetic data. Live payments are disabled.

## Run locally

```powershell
python -m pip install -r requirements.txt
python run.py
```

The API documentation is available at `http://127.0.0.1:8000/docs`.
The interactive local demo is served at `http://127.0.0.1:8000/`. It includes payment validation, agent registration and policy evaluation, and a dashboard summary.

### Configure the AI-assisted demo

The Google Gemini configuration uses Google's **Generative Language API** (`generativelanguage.googleapis.com`) through its OpenAI-compatible chat-completions endpoint. This API may not appear in the enabled APIs table you showed; search for **Generative Language API** in the Google Cloud API Library if you are managing API enablement there. Create or view a Gemini API key in [Google AI Studio](https://aistudio.google.com/apikey), then enter it as `AI_API_KEY` in the local `.env`. The configured model is `gemini-3.8-flash`; use a model ID currently available to your AI Studio project if that one is unavailable. Do not commit or share the key. Without a valid key or enabled API, natural-language extraction returns an error while the deterministic agent-evaluation form remains available.

The application still supports a local OpenAI-compatible server such as LM Studio by changing `AI_API_URL` to `http://127.0.0.1:1234/v1/chat/completions`, setting `AI_MODEL` to its served model ID, and leaving `AI_API_KEY` blank if local auth is off.

1. Register a demo agent in the UI with a budget and allowed currencies.
2. Use the natural-language purchase card to submit an instruction and the agent/merchant identifiers.
3. Inspect the extracted fields and deterministic policy decision. A model-generated extraction does not bypass guard rules.
4. When Agent Guard approves an AI-extracted proposal, the demo pre-fills the PayPal sandbox order form for review. The user must explicitly create the order, approve it with a Personal sandbox buyer account, then enter the returned order ID and a new capture request ID to capture it. Denied or escalated proposals do not prefill the checkout. No order is created or captured automatically from an AI decision.

To obtain PayPal sandbox credentials, sign in to the PayPal Developer Dashboard, select the Sandbox environment, then open **Apps & Credentials** and use or create a sandbox REST app. The sandbox buyer and seller test accounts are under **Testing Tools > Sandbox Accounts**. Use the Personal account to approve the order at `www.sandbox.paypal.com`; inspect the Business account to confirm the captured test payment. Keep the REST app secret on the server in `.env` and never put it in browser code or source control. The local demo intentionally will not work against live PayPal credentials.

`PAYPAL_WEBHOOK_ID` is optional for the basic sandbox order, buyer approval, and capture flow. You do not need a website or webhook to demonstrate that checkout. Skip **New Webhook** and leave `PAYPAL_WEBHOOK_ID=` blank unless you specifically want to test server-side notifications. If you later test webhooks locally, PayPal needs a public HTTPS URL; a temporary tunnel can provide one, but it exposes the local app publicly while running. This prototype's demo API is unauthenticated in development mode, so do not open a public tunnel casually; stop it immediately after testing and use synthetic data only.

Alternatively, create the subscription with PayPal's [Webhooks Management v1 API](https://developer.paypal.com/api/webhooks/v1/): `POST https://api-m.sandbox.paypal.com/v1/notifications/webhooks` using a sandbox Client Credentials bearer token with scope `https://uri.paypal.com/services/applications/webhooks`, a public HTTPS `url`, and `event_types`. The response contains the webhook `id`; `GET /v1/notifications/webhooks` lists subscriptions for that app (`anchor_type` defaults to `APPLICATION`).

For a complete token-and-list example using this project's `.env` settings, see the **Register the webhook and find `PAYPAL_WEBHOOK_ID`** section in `docs/PRODUCTION_INTEGRATIONS.md`. The `Bearer` value is the access token returned by PayPal OAuth, not the Client ID or Secret.

Use `GET /v1/notifications/webhooks/{webhook_id}` to inspect a subscription. PayPal's `PATCH` endpoint supports replacing `/url` or `/event_types`; replacing the event list requires sending every event that should remain subscribed. The integration guide includes an example patch payload.

Register the webhook on the same Sandbox REST app whose Client ID/Secret are configured. PayPal documents two verification methods: local signature validation or the PayPal verify-signature API; this app uses the API method and requires a verified event before recording it. The Webhooks simulator sends mock events that PayPal says cannot be verified or inspected like real event notifications, so it tests connectivity only. This endpoint rejects unverified messages with non-2xx; PayPal documents that non-2xx webhook deliveries may be retried up to 25 times over 3 days. Avoid repeated simulator sends to this strict verification endpoint; use a genuine sandbox event to test verification. The endpoint returns 2xx after a verified event is recorded or recognized as a duplicate.

## Relevant endpoints

- `POST /api/validation/validate`: validate one payment instruction.
- `POST /api/validation/validate/batch`: validate up to 100 instructions.
- `GET /api/validation/history`: read paginated validation history.
- `POST /api/agents/register`: register an agent policy.
- `POST /api/agents/evaluate`: evaluate a transaction request.
- `POST /api/agents/interpret-and-evaluate`: extract a natural-language purchase using the configured AI provider, validate the extracted fields, then evaluate the proposal using deterministic agent policy.
- `GET /api/agents/{agent_id}/spending`: read the UTC-day budget summary.
- `PUT /api/agents/{agent_id}/policy` and `DELETE /api/agents/{agent_id}`: owner-identity-gated policy changes; owner identity comes from the verified token subject.
- `POST /api/compliance/screen`: screen through the configured authorized-provider adapter.
- `POST /api/payments/orders` and `POST /api/payments/orders/{order_id}/capture`: PayPal sandbox checkout only.
- `POST /api/payments/webhooks/paypal`: verify PayPal webhook signatures and deduplicate event IDs.
- `GET /api/integrations/status`: inspect readiness without exposing credentials.

The daily limit and per-transaction limit are denominated in `budget_currency`. A request in another allowed currency is denied when no trusted FX source is configured, because its amount cannot be checked against those limits. Approved and escalated requests in the budget currency reserve daily capacity in this prototype.

## Important limitations

- IBAN checksum and BIC structure checks do not prove that an account exists, is open, or belongs to the named recipient.
- Corridor schedules, currency support, and keyword screening are static heuristics. A keyword match is not a sanctions determination; no keyword match does not establish that a party is clear. Use current authorized compliance screening before making a payment decision.
- OIDC/JWKS access-token verification and route scopes are implemented. The local demo intentionally runs without auth on loopback; production mode requires explicit OIDC settings described in `docs/PRODUCTION_INTEGRATIONS.md`.
- The sanctions integration is a provider adapter contract, not a contracted provider. Until an authorized vendor and adapter are configured, screening fails closed with `503`; no result is treated as clear.
- PayPal Orders API requests are restricted to sandbox. Live payment execution is intentionally disabled. Verified webhook event IDs are persisted, but event business processing and reconciliation need a separate production workflow.
- Merchant IDs, descriptions, and MCC values are caller-provided; the prototype has no trusted merchant-category verification and must not be exposed as a production payment authorization service.
- Validation history omits account numbers and IBANs, but stores recipient names, payment references, and decision details. Apply suitable access controls and retention rules before using non-synthetic data.
- Agent evaluation stores transaction descriptions and policy decisions. Do not send credentials, secrets, or unnecessary personal data in request metadata.
- Risk scores and dispute suggestions do not predict or guarantee payment success, regulatory compliance, or dispute outcomes.

## Tests

```powershell
pytest -q
```

## Hackathon submission readiness

- **Working prototype:** local setup and run instructions are provided above; the AI extraction route requires an AI provider key, and PayPal checkout requires sandbox credentials.
- **Tools disclosure:** FastAPI/Python, PayPal Orders REST API sandbox, and the configured OpenAI-compatible AI model are used. Select and identify the actual model/provider used for the demo in the final submission.
- **Still required outside this codebase:** publish this source in a public GitHub, GitLab, or Bitbucket repository, choose and add an open-source `LICENSE`, and record/upload a public YouTube demo video under three minutes. These publication and licensing actions have not been performed.
- **Video and access:** demonstrate the running application on desktop, include the AI extraction and PayPal sandbox order/approval/capture flow, use synthetic data, keep the video under three minutes, and provide English submission materials. Include clear sandbox setup instructions; do not publish account passwords or API secrets.
- **Eligibility and ownership:** the entrant must independently confirm eligibility, authority to submit for any team, ownership/originality, and the right to use any third-party APIs, models, and assets under their applicable terms.
- **Submission timing:** the supplied rules state that submissions close Thursday, November 12, 2026 at 12:00 p.m. Pacific Time.

### Draft submission description

> **SpendSentinel: Guardrails for AI-Agent Commerce**
>
> SpendSentinel helps merchants let AI agents shop without giving the model unchecked authority over money. A user describes a purchase in natural language; a configurable AI model extracts the proposed amount, currency, merchant description, and category. SpendSentinel validates that extraction, then applies deterministic merchant, currency, transaction-limit, and daily-budget policies to approve, deny, or escalate the request. When approved, the demo prepares a PayPal Sandbox order for human review. The buyer must approve it through PayPal Sandbox, and capture is a separate explicit action. This keeps the AI useful for understanding intent while predictable guardrails and user confirmation control payment actions.
>
> The prototype uses PayPal Orders REST API in Sandbox and an OpenAI-compatible model endpoint (the included local configuration targets LM Studio). It is a demonstration, not a production payment, identity, or compliance system. No live PayPal credentials or real funds are used.

### Demo video

The user-friendly plain-text storyboard and English narration in [`SpendSentinel_Video_Script.txt`](SpendSentinel_Video_Script.txt) target 2:50, below the three-minute maximum. Record only after the configured Gemini model and sandbox checkout flow have been tested. If the real PayPal order/approval/capture flow cannot be demonstrated, do not imply that it was completed in the video; show only the parts that work.
