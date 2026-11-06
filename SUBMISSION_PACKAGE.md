# Devpost Submission Package - SpendSentinel

**Hackathon:** PayPal AI Hackathon  
**Submission deadline:** November 12, 2026, 12:00 PM PT  
**Submission URL:** https://paypalaihackathon.devpost.com

---

## Submission Form Fields

### 1. Project Title
```
SpendSentinel: Guardrails for AI-Agent Commerce
```

### 2. Project Tagline (short description, max 140 chars)
```
AI agents can shop, but merchants need predictable controls before those agents spend money. SpendSentinel enforces deterministic spending policies.
```

### 3. Project Description (full text)

Copy-paste this into the Devpost description field:

---

**SpendSentinel: Guardrails for AI-Agent Commerce**

**The Problem:**
AI agents can understand purchase requests and extract structured data from natural language. But when those agents start spending money on behalf of users, merchants have no way to enforce spending policies, prevent unauthorized transactions, or audit agent behavior. The AI model that understands the purchase intent is not the same system that should authorize payment — and giving it unchecked authority over money creates serious risk.

**The Solution:**
SpendSentinel is a merchant protection platform that sits between a buyer's AI agent and the payment system. It turns natural-language purchase instructions into structured proposals, validates them against deterministic spending policies, and returns auditable approve/deny/escalate decisions. Only after the policy engine approves does the demo prepare a PayPal Sandbox order — and even then, the buyer must explicitly approve and the merchant must explicitly capture. The AI never authorizes or captures a payment.

**How It Works:**

1. **Agent Registration:** A merchant registers an AI agent with configurable spending policies: per-transaction limits, daily budgets, allowed currencies, allowed merchants, and allowed MCC categories.

2. **Natural-Language Purchase Extraction:** A user describes a purchase in plain language (e.g., "Buy printer paper for $24.50 from Office Supply"). A configurable AI model (Google Gemini via OpenAI-compatible API) extracts structured fields: amount, currency, merchant description, and category.

3. **Deterministic Policy Evaluation:** The AI output is treated as untrusted input. SpendSentinel's Agent Guard engine evaluates the proposal through a 10-step sequential policy check: agent status, idempotency, per-transaction limits, currency allowlists, merchant allowlists, MCC allowlists, daily aggregate budgets, velocity checks, and human escalation thresholds. The decision is APPROVE, DENY, or ESCALATE — deterministic and auditable.

4. **PayPal Sandbox Checkout:** For approved proposals, the demo pre-fills a PayPal Orders API sandbox form. The user must explicitly create the order, approve it via PayPal Sandbox (using a test buyer account), and then explicitly capture it. No step is automatic. Denied or escalated proposals do not prepare a checkout.

5. **Evidence Vault & Dispute Prevention:** SpendSentinel includes an immutable evidence vault that stores transaction evidence (device fingerprints, delivery tracking, billing verification) and generates CE3.0-inspired dispute auto-responses. When a dispute is filed, the system correlates the disputed transaction against historical data and generates a structured rebuttal package with a confidence score and recommended action (CONTEST, ESCALATE, or ACCEPT).

6. **International Payment Validation:** Before any cross-border payment, SpendSentinel runs 10 deterministic checks: IBAN format and MOD-97-10 checksum (76 jurisdictions), SWIFT/BIC structure (ISO 9362), ISO 4217 currency codes, currency-country compatibility, amount precision, corridor risk assessment, RTGS timing, duplicate detection (24-hour window), sanctions keyword pre-screening, and SWIFT MT103 reference validation. Composite risk scores determine PASS, WARN, or BLOCK outcomes.

7. **Dashboard Analytics:** An executive dashboard aggregates metrics across all modules: validation counts, agent transaction decisions, evidence/dispute statistics, risk score distributions, corridor risk heatmaps, and recent audit activity.

**PayPal Technologies Used:**
- PayPal REST Orders API v2 (Sandbox): Order creation, buyer approval, capture
- PayPal OAuth2 client credentials flow with token caching
- PayPal Webhooks: Signature verification via verify-signature API, event deduplication
- PayPal Sandbox test accounts: Buyer and seller accounts for demo checkout
- PayPal-Request-Id: Idempotency for order creation and capture

**AI Technologies Used:**
- Google Gemini (gemini-3.8-flash) via OpenAI-compatible chat completions API
- Configurable AI provider: Supports any OpenAI-compatible endpoint (Gemini, LM Studio, etc.)
- AI output is treated as untrusted input and validated before deterministic policy evaluation
- No model call is made unless AI_ENABLED=true

**Key Technical Features:**
- Deterministic policy engine: 10-step sequential evaluation, not decided by the language model
- Idempotency: Same key + same payload = cached result; same key + different payload = DENY
- Concurrent budget enforcement: Database write locking prevents race conditions on daily spending limits
- Fail-closed sanctions screening: If the provider is unavailable, screening returns 503 and no result is treated as clear
- Evidence versioning: Immutable append-only storage with monotonic version numbers
- OIDC/JWKS authentication: RS256 asymmetric token verification with scope-based authorization (production mode)
- Host allowlisting: Remote AI and sanctions endpoints restricted to configured exact hosts, HTTPS-only
- Risk scoring: Agent risk scores (0-100) based on velocity, amount ratio, merchant familiarity, currency deviation, timing — but never based on client-supplied metadata that could be spoofed

**What SpendSentinel Is NOT:**
- Not a production payment authorization service
- Not a compliance or sanctions screening service (uses heuristic keyword checks, not authoritative provider data)
- Not a live payment system (PayPal Sandbox only, live intentionally disabled)
- Not an official PayPal product (independent hackathon prototype)

**Target Audience:**
- Merchants who want to let AI agents shop on their platform without giving the model unchecked authority over money
- Marketplaces and platforms that need to enforce spending policies across multiple AI agents
- Fintech companies building agentic commerce infrastructure

**Hackathon Category:**
Agentic Commerce / AI Agents or Automation

**Project Status:**
Functional prototype with 32 passing tests. All API endpoints operational. Local demo UI serves at http://127.0.0.1:8000/. PayPal Sandbox integration tested with sandbox credentials. AI extraction tested with Google Gemini.

**Repository:**
[your-github-repo-url]

**Demo Video:**
[your-youtube-video-url]

**Live Demo:**
Not publicly hosted. Build and run locally:
```
python -m pip install -r requirements.txt
python run.py
```
Then open http://127.0.0.1:8000/ in a browser.

**Testing Access:**
PayPal Sandbox credentials are provided in the repository's `.env.example` file (template). To obtain your own sandbox credentials for testing:
1. Sign up at https://developer.paypal.com/
2. Go to Dashboard → Apps & Credentials → Sandbox
3. Create a REST app or use the default sandbox app
4. Copy the Client ID and Secret into your local `.env` file
5. Sandbox buyer and seller test accounts are available under Testing Tools → Sandbox Accounts

For AI extraction, you need a Google Gemini API key:
1. Go to https://aistudio.google.com/apikey
2. Create an API key
3. Enter it as AI_API_KEY in your local `.env` file
4. Alternatively, use a local OpenAI-compatible server (e.g., LM Studio) by changing AI_API_URL

**License:**
MIT License (see LICENSE file in repository)

---

### 4. Submission Requirements Checklist

Before submitting, verify:

- [ ] **Public code repository** created on GitHub/GitLab/Bitbucket
- [ ] **LICENSE file** visible at the top of the repository (MIT)
- [ ] **README.md** with clear setup and run instructions
- [ ] **Demo video** uploaded to YouTube and set to Public
- [ ] **Video duration** is under 3:00
- [ ] **Video shows** the project functioning end-to-end
- [ ] **Video uses** synthetic data only (no real credentials or personal info)
- [ ] **All materials** are in English
- [ ] **Testing access** instructions are clear (sandbox credentials, API keys)
- [ ] **Credentials rotated** (PayPal sandbox secret, Gemini API key)
- [ ] **.env file** is NOT committed to the repository (already in .gitignore)
- [ ] **sentinel.db** is NOT committed (already in .gitignore)
- [ ] **Repository URL** is entered in the submission form
- [ ] **YouTube video URL** is entered in the submission form
- [ ] **Project description** is complete and accurate
- [ ] **Eligibility confirmed** (you are not a PayPal/Devpost employee, not in a sanctioned country)
- [ ] **Original work confirmed** (no IP violations, no prior funding from PayPal/Devpost)

---

### 5. Devpost Submission Steps

1. **Register for the hackathon:**
   - Go to https://paypalaihackathon.devpost.com
   - Click "Join Hackathon"
   - Sign up or log in to your Devpost account

2. **Start a new submission:**
   - Click "Enter a Submission" or "Start a Submission"
   - Fill in the project title: "SpendSentinel: Guardrails for AI-Agent Commerce"

3. **Complete the submission form:**
   - **Tagline:** Use the short description above
   - **Description:** Copy-paste the full project description above
   - **Repository URL:** Enter your public GitHub/GitLab/Bitbucket URL
   - **Demo Video URL:** Enter your public YouTube URL
   - **Built with:** Select "PayPal API", "Python", "FastAPI", "Google Gemini" (or similar)
   - **Category:** Select "Agentic Commerce" or "AI Agents or Automation"
   - **License:** Select "MIT"

4. **Upload supporting materials (optional):**
   - Architecture diagram (if you create one)
   - Screenshots of the UI
   - API documentation

5. **Review and submit:**
   - Double-check all fields
   - Ensure the video is public and accessible
   - Ensure the repository is public and the LICENSE is visible
   - Click "Submit" before the deadline: **November 12, 2026, 12:00 PM PT**

6. **Confirm submission:**
   - You should receive a confirmation email from Devpost
   - Your submission should appear in your Devpost portfolio
   - Verify that all URLs work (repository, video, live demo if applicable)

---

### 6. Post-Submission

After submitting:

- **Monitor your email** for any communication from Devpost or PayPal
- **Keep the repository public** and accessible until judging ends (December 15, 2026)
- **Keep the video public** on YouTube until winners are announced (December 21, 2026)
- **Be available** to answer questions from judges if needed
- **Do not make major changes** to the submission after the deadline (minor bug fixes are okay)
- **Prepare for demos** if you are selected as a finalist

---

### 7. Judging Criteria Reminder

Your submission will be evaluated on five equally weighted criteria:

1. **Technological Implementation:** How thoroughly and skillfully does the project use PayPal Developer Platform and AI tool(s)? Is it genuine effort and a working, non-trivial implementation?

2. **Design:** Does the project deliver a complete, coherent product experience — not just a technical proof of concept?

3. **Potential Impact:** Does the project make a credible, specific case for solving a real problem for a real audience? Does the solution actually address that problem?

4. **Innovation/Idea:** How creative and novel is the concept? Does it differ from existing concepts?

5. **Presentation:** Does the video clearly demonstrate the project working end-to-end? Does the pitch communicate the problem, audience, and value? Is it easy to follow?

**Tie-breaking order:** Technological Implementation → Design → Potential Impact → Innovation → Presentation → Judges' vote

---

### 8. Common Mistakes to Avoid

- **Submitting after the deadline:** Submissions close November 12, 2026, 12:00 PM PT. No exceptions.
- **Private repository:** Judges cannot access private repos. Make it public.
- **Missing LICENSE:** Repository must have a detectable open-source license file.
- **Video over 3 minutes:** Judges are not required to watch beyond 3:00. Keep it short.
- **Private YouTube video:** Video must be public, not unlisted or private.
- **No testing access:** Judges need to be able to run your project. Provide clear setup instructions and sandbox credentials.
- **Exposing credentials:** Do not commit .env files, API keys, or passwords to the repository.
- **Claiming live payments:** This is a sandbox-only project. Do not imply that live payments are possible.
- **Using copyrighted material:** Do not include third-party logos, music, or assets in the video.
- **Inaccurate AI model name:** If you use Gemini, say "Gemini" not "GPT" or "ChatGPT". Be accurate.

---

## Final Submission Checklist

**Before you click "Submit" on Devpost:**

- [ ] Repository is public and LICENSE is visible
- [ ] Video is public on YouTube and under 3:00
- [ ] All URLs work and are accessible
- [ ] Description is complete and accurate
- [ ] Credentials are rotated and .env is not committed
- [ ] Testing instructions are clear
- [ ] Category and built-with tags are correct
- [ ] You have confirmed eligibility
- [ ] You have confirmed original work
- [ ] Submission is before the deadline

**Good luck!**
