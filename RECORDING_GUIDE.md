# Video Recording Guide - SpendSentinel Demo

**Target duration:** 2:50 (under 3:00 maximum)  
**Format:** Screen recording with English narration  
**Platform:** Desktop browser

---

## Pre-Recording Checklist

### 1. Rotate Credentials (CRITICAL)
Before recording, you MUST rotate these exposed credentials:

**PayPal Sandbox:**
- Go to https://developer.paypal.com/dashboard/applications/sandbox
- Click your app → "Show client secret" → "Reset"
- Copy new Client ID and Secret
- Update `.env` file:
  ```
  PAYPAL_CLIENT_ID=<new_client_id>
  PAYPAL_CLIENT_SECRET=<new_secret>
  ```

**Gemini API:**
- Go to https://aistudio.google.com/apikey
- Delete old key or create new key
- Update `.env` file:
  ```
  AI_API_KEY=<new_api_key>
  ```

### 2. Restart the App
```powershell
# Stop any running instance (Ctrl+C)
# Then start fresh:
python run.py
```

Verify the app is running at http://127.0.0.1:8000/

### 3. Test the Full Flow Manually
Before recording, test these steps to ensure they work:

**Test 1: Agent Registration**
- Open http://127.0.0.1:8000/
- In "Agent Guard" section, register an agent:
  - Agent ID: `demo_merchant_001`
  - Budget Currency: `USD`
  - Max Per Transaction: `50`
  - Max Daily Spend: `100`
  - Allowed Currencies: `USD,EUR,GBP`
  - Allowed Merchants: `OFFICE_SUPPLIES,TECH_STORE,BOOK_COFFEE_SHOP`
  - Allowed MCCs: `5943,5734,5812`
- Submit and verify you see "APPROVE" or "REGISTERED"

**Test 2: AI Purchase Extraction (Approved)**
- In "AI Purchase Extraction" section:
  - Natural Language: `Buy printer paper for 24.50 from Office Supply`
  - Agent ID: `demo_merchant_001`
  - Merchant ID: `OFFICE_SUPPLIES`
  - Idempotency Key: `demo_key_001` (use a unique key each time)
- Submit and verify:
  - AI extracts: amount=24.50, currency=USD, merchant=Office Supply
  - Agent Guard decision: APPROVE
  - PayPal order form is pre-filled

**Test 3: AI Purchase Extraction (Denied)**
- Try an over-limit purchase:
  - Natural Language: `Buy a laptop for 1500 dollars from Tech Store`
  - Agent ID: `demo_merchant_001`
  - Merchant ID: `TECH_STORE`
  - Idempotency Key: `demo_key_002`
- Verify decision: DENY or ESCALATE (exceeds $50 limit)
- Verify PayPal form is NOT pre-filled

**Test 4: PayPal Sandbox Order (Optional but Recommended)**
If you want to show the full PayPal flow:
- Use the pre-filled form from Test 2
- Click "Create Order"
- Copy the approval link from the response
- Open the link in a new browser tab (use sandbox buyer account)
- Approve the payment
- Return to the app, enter the order ID and a new capture key
- Click "Capture"
- Verify success response

**Test 5: Dashboard**
- Scroll to "Dashboard" section
- Click "Refresh Dashboard"
- Verify you see:
  - Validation counts (PASS/WARN/BLOCK)
  - Agent transaction counts (APPROVE/DENY/ESCALATE)
  - Evidence/dispute metrics
  - Risk score distribution
  - Recent activity feed

### 4. Prepare Your Desktop
- Close unnecessary browser tabs and apps
- Set browser zoom to 100% or 110% (ensure UI is readable)
- Use a clean browser profile (no saved passwords visible)
- Disable browser notifications
- Set screen resolution to 1920x1080 or higher
- Ensure system audio is muted (no notification sounds)

### 5. Recording Setup
- Use OBS Studio, ScreenToGif, or built-in screen recorder
- Record only the browser window (not full desktop)
- Set frame rate to 30 fps
- Export as MP4 or MOV
- Test recording with a 10-second clip first

---

## Recording Script (Timed Scenes)

### Scene 1: Introduction (0:00 - 0:16)
**Show:** SpendSentinel home page, scroll down slightly to show the UI  
**Narrate:**
> "AI agents can understand what we ask them to buy, but they should not receive unchecked authority over money. SpendSentinel adds clear spending rules and a human checkpoint to agent commerce."

**Tips:**
- Start with the browser at http://127.0.0.1:8000/
- Show the title "SpendSentinel" and the synthetic-data notice
- Keep mouse movements smooth and slow

---

### Scene 2: Agent Registration (0:16 - 0:34)
**Show:** Agent Guard registration form, fill in the fields, submit  
**Narrate:**
> "First, a merchant defines the agent's limits. This demo caps each purchase at fifty dollars and total daily spending at one hundred dollars. These policy rules are evaluated by the application, not decided by the language model."

**Actions:**
1. Scroll to "Agent Guard" section
2. Fill in the form:
   - Agent ID: `demo_merchant_001`
   - Budget Currency: `USD`
   - Max Per Transaction: `50`
   - Max Daily Spend: `100`
   - Allowed Currencies: `USD,EUR,GBP`
3. Click "Register Agent"
4. Show the success response

**Tips:**
- Use pre-filled values if the form remembers them
- If the agent already exists, use a new ID like `demo_merchant_002`

---

### Scene 3: Approved Purchase (0:34 - 1:05)
**Show:** AI extraction form, submit a purchase that will be approved  
**Narrate:**
> "Next, I describe a purchase in ordinary language. The configured Gemini model extracts a structured proposal. SpendSentinel validates those fields, then the deterministic Agent Guard checks them against the policy. Here, the twenty-four-dollar-and-fifty-cent request is approved under the configured limits."

**Actions:**
1. Scroll to "AI Purchase Extraction" section
2. Fill in:
   - Natural Language: `Buy printer paper for 24.50 from Office Supply`
   - Agent ID: `demo_merchant_001`
   - Merchant ID: `OFFICE_SUPPLIES`
   - Idempotency Key: `demo_key_001`
3. Click "Extract and Evaluate"
4. Show the extracted fields (amount, currency, merchant)
5. Show the decision: APPROVE
6. Point out that the PayPal form below is pre-filled

**Tips:**
- Wait for the AI response (may take 2-5 seconds)
- If the AI fails, show the manual evaluation form instead

---

### Scene 4: Denied Purchase (1:05 - 1:22)
**Show:** Submit a purchase that exceeds the limit  
**Narrate:**
> "Now I try a seventy-five-dollar purchase. It exceeds the per-transaction limit, so the guard rejects or escalates it. The model cannot override that decision, and no checkout is prepared for this request."

**Actions:**
1. In the same AI extraction form:
   - Natural Language: `Buy a laptop for 1500 dollars from Tech Store`
   - Agent ID: `demo_merchant_001`
   - Merchant ID: `TECH_STORE`
   - Idempotency Key: `demo_key_002`
2. Click "Extract and Evaluate"
3. Show the decision: DENY or ESCALATE
4. Point out that the PayPal form is NOT pre-filled

**Tips:**
- Use a fresh idempotency key each time
- If you get an idempotency conflict, just use a new key

---

### Scene 5: PayPal Sandbox Order (1:22 - 1:45)
**Show:** Pre-filled PayPal form, create order  
**Narrate:**
> "For the approved proposal, the demo prepares a Sandbox order form for review. I check the amount and description, then explicitly create the test order. Approval and capture are not automatic."

**Actions:**
1. Scroll back to the pre-filled PayPal form (from Scene 3)
2. Show the amount ($24.50) and description
3. Click "Create Order"
4. Show the response with the approval link
5. (Optional) Open the approval link in a new tab

**Tips:**
- If the PayPal form is not pre-filled, manually enter:
  - Amount: `24.50`
  - Currency: `USD`
  - Description: `Printer paper`
- If you don't want to show the PayPal flow, skip to Scene 6

---

### Scene 6: PayPal Approval and Capture (1:45 - 2:18)
**Show:** Sandbox buyer approval, capture response  
**Narrate:**
> "The buyer must approve the order in the separate Sandbox checkout. After approval, I return here and explicitly request capture. This is test money in the Sandbox, not a live payment."

**Actions:**
1. Open the approval link (from Scene 5) in a new tab
2. Log in with sandbox buyer account (if not already logged in)
3. Approve the payment
4. Copy the order ID from the URL or response
5. Return to the SpendSentinel app
6. Enter the order ID and a new capture key
7. Click "Capture"
8. Show the capture response

**Tips:**
- Use a fresh browser tab for the sandbox buyer
- If you don't have sandbox accounts set up, skip this scene and just show the order creation response
- Blur or crop any email addresses or account details

---

### Scene 7: Dashboard and Conclusion (2:18 - 2:50)
**Show:** Dashboard summary, recent activity  
**Narrate:**
> "SpendSentinel combines AI for understanding purchase intent, deterministic policies for spending control, and a separately confirmed Sandbox checkout. It is a prototype, not a production authorization or compliance service."

**Actions:**
1. Scroll to "Dashboard" section
2. Click "Refresh Dashboard"
3. Show the summary cards:
   - Validation counts
   - Agent transaction counts
   - Evidence metrics
4. Show the recent activity feed
5. End with the SpendSentinel title visible

**Tips:**
- The dashboard should show data from your demo actions
- If the dashboard is empty, that's okay - just mention it's a fresh demo

---

## Post-Recording Checklist

### 1. Edit the Video
- Trim any pauses or mistakes
- Ensure total duration is under 3:00
- Add captions if possible (optional but recommended)
- Do NOT add background music (copyright risk)
- Do NOT add third-party logos or trademarks

### 2. Export the Video
- Format: MP4 (H.264) or MOV
- Resolution: 1920x1080 or higher
- Frame rate: 30 fps
- File size: Keep under 500 MB for YouTube upload

### 3. Upload to YouTube
- Go to https://youtube.com/upload
- Sign in to your Google account
- Upload the video
- Set visibility to **Public** (not Unlisted or Private)
- Title: "SpendSentinel - Guardrails for AI-Agent Commerce | PayPal AI Hackathon"
- Description:
  ```
  SpendSentinel is a hackathon prototype for safer AI-agent commerce. A configured AI model extracts purchase intent from natural language; a deterministic spending-policy engine then approves, denies, or escalates the resulting proposal. Approved evaluations can be followed by a separately initiated PayPal Orders API sandbox checkout.
  
  GitHub Repository: <your-repo-url>
  
  #PayPalAIHackathon #AIAgents #FinTech
  ```
- Tags: PayPal AI Hackathon, AI Agents, FinTech, Payment Security, SpendSentinel
- Copy the YouTube URL

### 4. Verify the Video
- Watch the full video to ensure:
  - No credentials are visible
  - No personal information is shown
  - Audio is clear and narration is audible
  - UI is readable (not too small)
  - Duration is under 3:00
- Check that the video is public and accessible

---

## Troubleshooting

### AI Extraction Fails
**Problem:** The AI extraction returns an error or timeout.  
**Solution:**
- Check that `AI_ENABLED=true` in `.env`
- Verify the Gemini API key is valid
- Check the console for error messages
- If Gemini is unavailable, use the manual evaluation form instead

### PayPal Order Creation Fails
**Problem:** PayPal returns an error when creating the order.  
**Solution:**
- Check that `PAYPAL_SANDBOX_ENABLED=true` in `.env`
- Verify the sandbox Client ID and Secret are correct
- Check the console for error messages
- If PayPal is unavailable, skip the PayPal flow in the video

### Dashboard Shows No Data
**Problem:** The dashboard is empty after demo actions.  
**Solution:**
- Click "Refresh Dashboard" to reload the data
- Check that the database is being written to (sentinel.db)
- If the database is corrupted, delete it and restart the app (it will be recreated)

### Video is Too Long
**Problem:** The recording exceeds 3:00.  
**Solution:**
- Edit the video to trim pauses and mistakes
- Speed up repetitive parts (e.g., form filling)
- Remove optional scenes (e.g., PayPal approval flow)
- Re-record with tighter narration

### Video is Too Short
**Problem:** The recording is under 2:00 and feels rushed.  
**Solution:**
- Add more detail to the narration
- Show additional features (e.g., evidence vault, sanctions screening)
- Add a title card at the beginning and end
- Slow down mouse movements and pauses

---

## Final Notes

- **Do not fabricate responses.** If a step fails, show the failure and explain it.
- **Use synthetic data only.** Do not use real PayPal accounts or real money.
- **Keep it professional.** Speak clearly and at a moderate pace.
- **Practice before recording.** Do a dry run to ensure the flow is smooth.
- **Backup the video.** Save the raw recording and the edited version in separate locations.

Good luck with the recording!
