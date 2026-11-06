# SpendSentinel Progress Log

## 6 November 2026 - Hackathon submission gap remediation

### Gap 1: Git repository initialization - COMPLETED

- Initialized local git repository at project root.
- Verified `.gitignore` correctly excludes: `.env`, `*.db`, `__pycache__/`, `.pytest_cache/`, `*.py[cod]`, `.venv/`.
- Confirmed no hardcoded credentials in source code or test files via grep scan.
- Created initial commit: 61 files, 10,672 insertions across all 8 modules.
- Sensitive files verified NOT tracked: `.env` (0 matches), `sentinel.db` (0 matches), `__pycache__/` (0 matches), `.pytest_cache/` (0 matches).
- **Remaining action (user):** Create public GitHub/GitLab/Bitbucket repository and push. Rotate exposed PayPal Sandbox Client Secret and Gemini API key before pushing.

### Gap 2: Open-source license file - COMPLETED

- Added MIT License file at project root (`LICENSE`).
- Copyright holder: "SpendSentinel Contributors", year 2026.
- MIT License chosen for maximum permissiveness and GitHub auto-detection in repository About section.
- Committed to git: `66e7e38 Add MIT open-source license`.

### Gap 3: Credential rotation - PENDING (USER ACTION REQUIRED)

- Identified exposed credentials in `.env`: PayPal Sandbox Client ID, Client Secret, and Gemini API Key.
- `.env` is correctly excluded from git via `.gitignore` (0 tracked matches).
- **User must manually rotate credentials:**
  - PayPal Sandbox: Reset client secret at https://developer.payrecurring.com/dashboard/applications/sandbox
  - Gemini API: Delete old key and create new key at https://aistudio.google.com/apikey
  - Update `.env` with new values before recording demo video
- No code changes required; this is an operational security step.

### Gap 4: Demo video preparation - COMPLETED

- Verified all 32 tests pass (47.72s runtime, deprecation warnings only).
- Verified `python -m compileall -q app tests run.py` passes with no errors.
- Created `RECORDING_GUIDE.md` with:
  - Pre-recording checklist (credential rotation, app restart, manual flow testing)
  - 7 timed scenes with exact narration scripts (total target: 2:50)
  - Step-by-step actions for each scene (agent registration, approved purchase, denied purchase, PayPal order, approval/capture, dashboard)
  - Desktop and browser preparation tips
  - Post-recording editing and YouTube upload instructions
  - Troubleshooting section for common failures (AI extraction, PayPal order, dashboard data)
- Committed to git: `25379a6 Add video recording guide and Devpost submission package`.
- **User must:** Record video following the guide, edit to under 3:00, upload to YouTube as public.

### Gap 5: Devpost submission preparation - COMPLETED

- Created `SUBMISSION_PACKAGE.md` with:
  - Complete project description text (ready to copy-paste into Devpost form)
  - Submission requirements checklist
  - Step-by-step Devpost submission instructions
  - Testing access guide for judges (sandbox credentials, API keys, setup steps)
  - Judging criteria reference with tie-breaking order
  - Common mistakes to avoid
  - Final submission checklist
- Committed to git: `25379a6 Add video recording guide and Devpost submission package`.
- **User must:** Create public GitHub/GitLab/Bitbucket repo, push code, register at paypalaihackathon.devpost.com, fill submission form using the package, submit before November 12, 2026 12:00 PM PT.

---

## 3 November 2026 - Service audit remediation

### Completed

- Changed local sanctions-keyword hits from a low-weight pass into a failed screening check with a minimum `WARN` outcome. The result explicitly requires authorized manual/provider review and does not claim that a keyword alone is an authoritative sanctions match.
- Changed duplicate-payment validation to use database-side exact matching and return at most one candidate instead of loading every recent record. A missing database session now fails closed to `WARN` rather than reporting the duplicate check as passed.
- Serialized agent budget evaluation with a database write lock on the agent row, in addition to the local lock, so the critical budget check is not dependent on one worker's memory.
- Changed transactions outside the configured budget currency to `DENY` when no trusted exchange-rate source is available. The Agent Guard can no longer treat them as pending escalation while omitting them from enforceable budget totals.
- Added evidence version uniqueness, SQLite write serialization, and PostgreSQL transaction advisory locking. Evidence bulk inserts now commit or roll back as one unit.
- Reworked Evidence Vault statistics and device/IP profiles to compute latest-version metrics and counts in SQL. Associated customer IDs are capped at 100 and disclose when truncated.
- Removed client-provided transaction hour and velocity from agent risk scoring. Malformed risk metadata no longer causes integer-conversion failures. Removed the unreferenced payment/dispute risk helper functions so they are not mistaken for active enforcement controls.
- Fixed the PayPal demo mock's dispute due date to use a real ten-day `timedelta` and marked its in-memory state as demo-only. It is not the active payment integration.
- Added a process-wide PayPal OAuth token cache keyed by a one-way credential fingerprint, with expiry handling and concurrent refresh serialization. Webhook header lookup is case-insensitive. PayPal calls remain restricted to Sandbox.
- Restricted remote AI and sanctions endpoints to configured exact-host allowlists, disallowed redirects, and limited remote endpoints to HTTPS port 443. Local loopback inference remains supported. AI extraction now tolerates standard JSON Markdown fences and still passes the extracted result to deterministic policy validation.
- Changed the sanctions-unavailable helper to return the same Pydantic response contract as successful screening responses. Added explicit package exports for the active service entry points.
- Added regression coverage for these policy, concurrency, URL validation, parsing, evidence atomicity/versioning, OAuth caching, webhook header, and due-date behaviors.

### Verification

- Final `pytest -q`: 32 passed, including concurrent evidence-version writes, atomic bulk rollback, database-filtered duplicate detection, and OAuth token reuse.
- `python -m compileall -q app tests run.py`: passed.
- Documentation now reflects the fail-closed behavior for non-budget currencies and endpoint host allowlists.
- Existing Pydantic, Starlette/httpx, and `datetime.utcnow()` deprecation warnings remain outside the scope of this audit remediation.

### Remaining limitations

- AI prompt injection cannot be eliminated by prompt text alone. Model output remains untrusted, and purchase authorization continues to depend on the deterministic Agent Guard; external model calls were not live-tested in this remediation.
- Non-budget-currency purchases are denied until a trusted exchange-rate service and corresponding policy are introduced.
- PayPal production/live API access remains intentionally disabled. OAuth and webhook behavior were tested with mocked responses, not live PayPal credentials.
- No licensed sanctions provider was selected or tested. Configure only the contracted adapter hostname in `SANCTIONS_ALLOWED_HOSTS`; screening is not authoritative until provider and legal requirements are established.
- Evidence locking is implemented for the configured SQLite use and PostgreSQL. Other database engines require their own migration and transaction-lock verification before multi-worker deployment.
- SQLAlchemy `create_all` does not retrofit the evidence-version unique constraint onto an existing table; apply a database migration before relying on that constraint for existing deployments.
- The mock PayPal service remains an unused, in-process demo stub; it is not suitable for multi-worker state or production payments.

## 3 November 2026

### Completed

- Connected the international payment validator and AI Agent Guard to the FastAPI application.
- Served the interactive local demo from `/` and moved the platform status payload to `/api/status`.
- Replaced the static-only landing page with working forms for payment validation, AI-agent registration, and agent transaction evaluation, plus a dashboard refresh action. Results are rendered as text rather than interpreted HTML.
- Connected dashboard counts to the newly persisted validation and agent-policy records, in addition to the legacy demo tables.
- Added payment validation endpoints:
  - `POST /api/validation/validate` for one payment instruction.
  - `POST /api/validation/validate/batch` for batches of up to 100 instructions.
  - `GET /api/validation/history` for paginated validation history.
- Added persistent validation records while avoiding storage of account numbers and IBANs. Removed IBAN values from persisted validation-check details as well.
- Improved the sanctions keyword pre-screen to report review warnings rather than presenting local keyword matches as authoritative sanctions determinations. Updated corridor warnings to clarify that static data does not determine legal permissibility.
- Corrected currency compatibility messaging so it does not claim that a recipient bank will accept or convert a currency unless that has actually been verified.
- Hardened AI-agent transaction evaluation:
  - Validated and normalized currency codes, identifiers, MCC values, transaction amounts, and currency minor-unit precision.
  - Bound idempotency keys to the complete transaction request, including description, merchant name, and metadata, so reusing a key with altered details is rejected.
  - Used database transaction locking for SQLite evaluation and added row-locking where supported, helping serialize spending-limit checks.
  - Counted both approved and escalated transactions against daily spending limits.
  - Added an explicit budget currency. Requests in another allowed currency require human review because no trusted FX source is configured.
  - Switched spending amounts and aggregation to decimal arithmetic to avoid binary floating-point budget errors.
  - Scoped transaction idempotency to each agent.
- Required a caller identity for policy updates and deactivation, and enforced that only the registered owner may perform those operations. This is an ownership check, not a substitute for authenticated identity.
- Registered the new routes in OpenAPI and added startup initialization for their database tables. Separated their table names from legacy tables to avoid schema collisions.
- Restricted the development server to loopback and narrowed the CORS origins.
- Added a README covering setup, endpoints, and operational limitations.
- Added tests for IBAN checksum validation, sanctions-review semantics, idempotency conflicts and replay, foreign-currency escalation, concurrent daily-budget enforcement, decimal budget boundaries, currency precision, and sensitive account-data persistence.

### Verification

- `pytest -q`: 8 passed.
- `python -m compileall -q app tests run.py`: passed.
- OpenAPI route-registration check: passed.
- End-to-end smoke test of health, payment validation, agent registration, and agent evaluation: passed.
- End-to-end smoke test of the served UI, payment validation history, approved and escalated agent decisions, dashboard aggregates, and spending summary: passed.
- Inline browser JavaScript syntax check: passed.

### Known limitations

- This remains a prototype. PayPal API calls are sandbox-only; order creation and capture require explicit API requests and buyer approval. Live payments are disabled.
- There is no production authentication or trusted verification of merchant identity, MCC, or caller identity.
- Static corridor data and local sanctions keyword checks are not authoritative compliance screening.
- Account syntax checks do not prove account existence, ownership, or status.
- No trusted exchange-rate source is integrated; different-currency requests are escalated instead of automatically converted.
- Validation history and agent audit records may include recipient names, references, descriptions, or metadata. Do not send secrets or unnecessary personal data; configure access controls and retention before using real data.
- The test run reports existing Pydantic deprecation warnings in legacy evidence and dashboard schemas.

## 3 November 2026 - Integration foundations

### Completed

- Added optional OIDC access-token verification using asymmetric JWT signatures and the configured issuer's JWKS, with audience, issuer, expiry, and required-claim checks.
- Added scope/role authorization dependencies to API routes. In authenticated mode, agent-policy ownership is derived from the verified token subject rather than a caller-supplied identity.
- Added production startup checks that reject incomplete or unsafe authentication, issuer/JWKS, CORS, or debug configuration.
- Added a fail-closed sanctions-provider adapter contract. It requires an HTTPS provider endpoint and maps only valid normalized provider outcomes; missing configuration, provider failures, and malformed responses do not produce a clear result.
- Added PayPal Orders API support restricted to the sandbox host, including OAuth client credentials, request idempotency, and an approved-order check before capture.
- Added PayPal sandbox webhook signature verification and event-ID deduplication, persisting only the event ID and type.
- Added environment-variable examples and `docs/PRODUCTION_INTEGRATIONS.md` with configuration and deployment guidance.
- Added integration tests, including an API-level webhook replay test that verifies duplicate events are stored only once.

### Verification

- `pytest -q`: 19 passed.
- `python -m compileall -q app tests run.py`: passed.
- Settings-module import check: passed.
- Existing warnings: five Pydantic deprecation warnings in legacy schemas and one Starlette/httpx TestClient deprecation warning.

### Remaining production prerequisites

- The API authentication verifier is implemented, but deployment still requires a configured OIDC identity provider and the frontend does not yet implement interactive OIDC login/Authorization Code with PKCE.
- Sanctions screening is an adapter contract, not a connection to a selected licensed screening vendor or authoritative sanctions dataset. Vendor selection, legal/privacy review, and jurisdictional coverage validation remain necessary.
- PayPal operations are sandbox-only and were tested with mocked responses; real sandbox credentials and end-to-end buyer approval/webhook testing have not been performed. No live-payment endpoint is enabled.
- Production operations still require durable webhook processing and reconciliation, production-grade database/storage and retention decisions, monitoring, and security/compliance review.

## 3 November 2026 - Hackathon alignment and AI intent flow

### Challenge alignment

- Positioned PayPal Sentinel as an AI-agent commerce safety prototype for the "Build What's Next with PayPal and AI" challenge.
- Clarified the two substantive integrations: AI-assisted purchase-intent extraction and PayPal Orders API sandbox checkout.
- Distinguished model-based language extraction from the deterministic Agent Guard, which remains the authority for approve/deny/escalate decisions.

### Completed

- Added configurable OpenAI-compatible chat-completions settings (`AI_ENABLED`, `AI_API_URL`, `AI_API_KEY`, and `AI_MODEL`) without introducing a new runtime package.
- Added `POST /api/agents/interpret-and-evaluate`: sends user text to the configured model for structured purchase-field extraction, validates the extracted values with existing transaction rules, then evaluates the transaction against the agent's deterministic policy.
- Preserved trusted `agent_id`, `merchant_id`, and idempotency key from the API caller rather than asking the model to invent identity or replay controls.
- Made the AI path fail explicitly when disabled, unconfigured, unavailable, or returning invalid/ambiguous data. The AI path does not create or capture a PayPal order.
- Added a natural-language purchase form to the interactive local demo and disclosed that AI configuration is required for this feature.
- Updated the README and integration guide with the challenge project description, model and PayPal tools disclosure, safe setup, demo flow, and items still required for submission.
- Updated `/api/status` to list the AI extraction and PayPal Orders sandbox modules accurately.
- Added tests for AI provider extraction, unconfigured behavior, and the complete route handoff from model extraction to policy evaluation.
- Reviewed the supplied hackathon rules and PayPal sandbox quickstart resources. Documented the explicit buyer-approval/seller-confirmation test sequence, English submission materials, public-repository/open-source-license requirement, under-three-minute public YouTube video, eligibility/ownership checks, third-party terms, and the stated submission deadline.
- Added a browser-based PayPal sandbox checkout flow: create order, open only a verified PayPal sandbox approval URL, then explicitly submit capture after buyer approval using a distinct idempotency key.
- Connected the approved AI purchase proposal to the PayPal sandbox form by pre-filling the extracted amount, currency, and description only when deterministic Agent Guard returns `APPROVE`. The user must review and explicitly create the order; buyer approval and capture remain separate explicit steps. Denied/escalated proposals do not prefill checkout.
- Expanded README and integration setup instructions with how to obtain sandbox app credentials and test buyer/seller accounts, and cautions not to disclose secrets or use live credentials.
- Changed the AI integration default from OpenAI's hosted endpoint to LM Studio's local OpenAI-compatible endpoint (`http://127.0.0.1:1234/v1/chat/completions`) after the user reported they do not have the OpenAI endpoint. Local loopback inference now permits an empty API key; remote HTTPS providers still require a key. Added model-ID setup guidance and a test for local no-key requests.
- Created a local `.env` template for development, optional AI configuration, and PayPal sandbox credentials. Secret values are blank; live PayPal credentials are explicitly not intended for this file.
- Documented where to create and retrieve `PAYPAL_WEBHOOK_ID` in the PayPal Sandbox REST app dashboard, clarified that it differs from Client ID/Secret, and noted that webhook delivery requires a publicly reachable HTTPS endpoint while basic checkout does not require webhook setup.
- Added guidance for the PayPal Webhooks simulator: use a public HTTPS tunnel to `/api/payments/webhooks/paypal`, keep the app and tunnel running, and distinguish simulator connectivity checks from real signature verification because simulator-generated mock events are not verifiable as normal notifications.
- Incorporated PayPal's webhook integration details supplied by the user: subscriptions are scoped to a REST app (up to 10 URLs per app); verified receipt should return 2xx; non-2xx delivery may be retried up to 25 times over 3 days; verification may use local signature validation or PayPal's verify-signature API, and this project uses the API method. Updated the webhook docs to warn that repeated simulator mocks may cause retries and are not an end-to-end signature test.
- Added the PayPal Webhooks Management v1 API as an alternative to dashboard setup, including sandbox create/list/details/event-type endpoints and a sample create payload. Clarified that management/event-resend APIs are separate from this app's webhook receiver.
- Added a complete `httpx` example to obtain a sandbox OAuth Client Credentials token with the Webhooks scope, then call `GET /v1/notifications/webhooks`; clarified the Bearer value is the access token, not Client ID/Secret.
- Documented PayPal webhook details lookup by ID and update via `PATCH /v1/notifications/webhooks/{webhook_id}`, including `replace` examples for `/url` and `/event_types` and the need to send the full replacement event list.

## 3 November 2026 - Submission readiness review

### Remaining hackathon submission work

- Add the user's PayPal Sandbox REST app Client ID and Secret locally to `.env`; keep the values private and do not commit the file.
- Start LM Studio, load a chat model, and replace the placeholder `AI_MODEL=local-model` with the exact model ID provided by the local server.
- Run a real end-to-end demo with AI extraction, deterministic Agent Guard evaluation, PayPal sandbox order creation, Personal buyer approval, capture, and Business seller confirmation. Prior automated tests use mocked provider responses and do not substitute for this live sandbox check.
- If webhook verification is part of the demo, register a webhook for the same sandbox REST app, configure its HTTPS listener and ID, and test with a genuine sandbox event. Simulator mock delivery only checks connectivity and does not provide a verifiable event.
- Publish the source repository publicly, add a selected open-source license, prepare the English submission description and test instructions, and upload a public YouTube demo video under three minutes.
- Confirm entrant eligibility, team representative authority where applicable, project ownership, and applicable third-party API/model/asset terms.

Production OIDC authentication and a licensed sanctions vendor are not required by the supplied core hackathon criteria; they remain production-readiness work.

## 3 November 2026 - Product name changed to SpendSentinel

- Replaced the product-facing name "PayPal Sentinel" with "SpendSentinel" in the README, UI title/header/footer, API title and status payload, configuration default, and code module descriptions.
- Added a clear statement that SpendSentinel is an independent prototype and not an official PayPal product. PayPal is named only to identify the sandbox/API integration.
- Kept historical work entries below/above this update intact where they describe the earlier project state; they are progress history, not current product branding.
- Restarted the local demo so the active process loads the new title. Verified the served homepage returns HTTP 200 and displays SpendSentinel without the old product name; `/api/status` reports `SpendSentinel`; OpenAPI title is `SpendSentinel API`.
- Verification: `pytest -q`: 23 passed; `python -m compileall -q app tests run.py`: passed.
- Remaining: public repository and submission artifacts remain pending; confirm eligibility and third-party asset/provider terms before submission.

## 3 November 2026 - Hackathon demo video script

- Created `SpendSentinel_Video_Script.txt` as a user-friendly plain-text script with an English spoken script, timed scene-by-scene desktop screen recording plan, and a total target runtime of 2:50, under the hackathon's three-minute maximum.
- Script covers the project problem, agent policy setup, Gemini natural-language extraction, a denied over-limit request, PayPal Sandbox order review, buyer approval, explicit capture, and seller confirmation.
- Added pre-recording and editing checks for actual integration testing, synthetic data, credential/account privacy, English materials, public YouTube upload, no unlicensed third-party logos/music/assets, and no fabricated results or implied PayPal endorsement.
- Linked the `.TXT` script from the README; the user-facing video script is kept in plain text only.
- Confirmed the `.TXT` contains eight timed scenes and README points to the plain-text script; removed stale Markdown script references.
- Remaining: record only after the Gemini and real Sandbox flow have been verified; the video itself has not been recorded or uploaded.

## 3 November 2026 - Recording readiness check

- Confirmed the local SpendSentinel homepage is available at `http://127.0.0.1:8000/` with HTTP 200; `/health` is `ok` and `/api/status` reports `SpendSentinel`.
- Checked integration configuration without printing secrets: Gemini and PayPal Sandbox are enabled/configured in `.env`; `PAYPAL_WEBHOOK_ID` is blank and remains optional for basic checkout.
- The app is ready for recording UI and locally functioning portions. This check did not send a request to Gemini or PayPal, so it does not establish that the Gemini model call or sandbox order/approval/capture flow succeeds end-to-end.
- For a final submission video, first verify the live Gemini response and the real Sandbox buyer approval/capture and seller confirmation; keep `.env`, API keys, passwords, and private account details off-screen.
- The video has not been recorded or uploaded.

## 3 November 2026 - Local readiness work

### Completed

- Checked local AI/PayPal configuration without printing secret values: sandbox Client ID and Secret are not configured; LM Studio is not reachable at `127.0.0.1:1234`; `AI_MODEL` is still the placeholder `local-model`.
- Added `.gitignore` rules for `.env` and other local secrets/artifacts, while keeping `.env.example` eligible for source control.
- Added an English draft hackathon submission description and an initial timed video outline to the README, with an explicit instruction not to claim untested PayPal steps as complete. The detailed 2:50 narration/storyboard is in `SpendSentinel_Video_Script.txt`.

### Blocked or requiring the user's account/actions

- Real PayPal sandbox checkout cannot be exercised until the user adds sandbox REST credentials to the local `.env`; creating and capturing an order also requires explicit approval for that sandbox transaction.
- AI extraction cannot be exercised against a real local model until LM Studio is started, a chat model is loaded, and `AI_MODEL` is changed from its placeholder to the model's actual ID.
- Public repository publication, license selection, and video upload were not attempted. The workspace is not a Git repository, and license/ownership and publication credentials are user-controlled.

### Verification

- `pytest -q`: 23 passed (six existing dependency/schema deprecation warnings).
- `python -m compileall -q app tests run.py`: passed.
- `.gitignore` check confirmed `.env` is ignored and `.env.example` remains allowed.

## 3 November 2026 - Webhook ID not yet available

- Clarified in `.env` and README that `PAYPAL_WEBHOOK_ID` may remain blank for the basic sandbox order, buyer approval, and capture flow. It is needed only for incoming webhook signature verification.
- Did not create or capture a PayPal order; that remains a separate sandbox transaction requiring explicit user approval.
- Local `.env` contains sandbox credential values and is excluded by `.gitignore`; do not share or commit it.

## 3 November 2026 - User provided sandbox configuration

- Checked `.env` without printing credential values: sandbox mode is enabled, Client ID and Secret are configured, and `PAYPAL_WEBHOOK_ID` is blank. The local integration-status endpoint returns HTTP 200 and reports PayPal sandbox as configured; webhook verification is not configured.
- The local LM Studio endpoint is not currently reachable, and `AI_MODEL` remains the placeholder `local-model`; AI-backed intent extraction cannot yet be tested against a real model.
- No PayPal credentials were sent to PayPal and no order/capture was initiated in this check.
- Security notice: an earlier file-view output in this conversation displayed the `.env` credential values. Treat that sandbox Client Secret as exposed: rotate/regenerate it in the PayPal Developer Dashboard, update the local `.env`, and do not reuse the disclosed secret. The `.env` file remains excluded by `.gitignore`.
- An initial local check command had a Python syntax error; it was corrected. The corrected ASGI readiness check succeeded with HTTP 200 and printed only non-secret status flags.

## 3 November 2026 - Local demo launched for user testing

- Started the FastAPI demo on `http://127.0.0.1:8000/` for the user to test.
- Verified the homepage returns HTTP 200 and serves the PayPal Sentinel UI; `/health` returns `ok`.
- Verified `/api/integrations/status` reports PayPal configured in sandbox mode and webhook not configured. Webhook ID is optional for basic checkout.
- Did not call Gemini or PayPal APIs; no external request or payment action was made.
- Remaining: Gemini live-call testing, PayPal sandbox order/approval/capture flow, public repo/license/video submission. Before PayPal testing, rotate the sandbox Client Secret because it was displayed in prior tool output.

## 3 November 2026 - Google Gemini API configuration

- Identified the relevant Google service as **Generative Language API** (`generativelanguage.googleapis.com`); it is not one of the APIs in the user's displayed list.
- Configured local `.env` and `.env.example` for Google's OpenAI-compatible Gemini endpoint and a Gemini Flash model identifier.
- Updated README and integration documentation with Google AI Studio key setup, API enablement, endpoint/model settings, and the LM Studio alternative.
- The user has now entered the Gemini API key in `.env`; a local presence check confirmed it is configured without displaying the value.
- No request was sent to Google during the presence check. A live API smoke test remains unperformed.
- Isolated the fail-closed integration test from machine-local `.env` settings after the first test run correctly observed the user's configured sandbox PayPal credentials; this keeps tests deterministic without altering the user's credentials.
- Verification: `pytest -q`: 23 passed; `python -m compileall -q app tests run.py`: passed; confirmed `.env` points to Google's endpoint, has AI enabled, and contains a non-empty key without printing it.

### Verification

- `pytest -q`: 22 passed.
- `python -m compileall -q app tests run.py`: passed.
- OpenAPI check confirms `/api/agents/interpret-and-evaluate` is registered.
- Inline browser JavaScript syntax check: passed after adding the PayPal demo flow.
- OpenAPI checks confirm the AI intent route and PayPal order creation/capture routes are registered.
- After linking approved AI proposals to sandbox order review, the full test suite, Python compilation, JavaScript syntax, and route-registration checks were rerun and passed.
- After switching the AI default to local LM Studio, `pytest -q`: 23 passed; `python -m compileall -q app tests run.py`: passed; settings import confirmed local URL, enabled flag, placeholder model ID, and no configured API key.

### Hackathon submission tasks not completed in this workspace

- Select and configure the actual AI provider/model and PayPal sandbox credentials, then record an end-to-end demo with those services.
- Publish the source repository publicly, select and add an open-source license, and upload a public YouTube demo video under three minutes. These require account-level/user decisions or external publication actions and have not been performed.
- Confirm personal/team eligibility and rights to submit, use the configured third-party AI provider, and include all assets under their applicable licenses.
