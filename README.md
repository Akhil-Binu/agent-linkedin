# LinkedBot: Autonomous Cybersecurity LinkedIn Growth Agent

**LinkedBot** is an autonomous AI social growth agent designed to build authentic B2B authority in cybersecurity through strategic liking, thoughtful commenting, and human-sounding thought leadership posts.

---

## 🛡️ Core Rules & Guardrails
- **Anti-Slop Tone Guard:** Automatically blocks corporate clichés (`delve`, `testament`, `game-changer`, `in today's fast-paced world`, etc.) and generic praise (`great post`, `totally agree`).
- **Target Domain:** **Cybersecurity** (Cloud Security & IAM, DevSecOps/AppSec, Detection Engineering/SOC alert fatigue, FIDO2/Auth, AI Red Teaming).
- **Post Structure:** Strictly enforces `Hook -> Core Insight -> Example/Data -> Takeaway/Question` with short punchy paragraphs and <= 2 emojis.
- **Engagement Heuristics:** Comments are 1–3 sentences offering a counter-perspective, sharp open-ended question, or technical micro-insight. Zero empty flattery.
- **Rate-Limiter Circuit Breaker:** Daily & hourly quotas enforced; auto-triggers a 60-minute hard backoff if a 429 / rate limit is hit.
- **Human-In-The-Loop (HITL):** If comment confidence < 85% or on original posts, items are staged in `hitl_queue.json` for review with optional Slack/Telegram webhook alerts.
- **SQLite Analytics Engine:** Automatically tracks every scanned post, evaluation score, and engagement action to `data/analytics.db`.
- **Autonomous Scheduler:** Features quiet hours (night pause) and human jitter to mimic organic user behavior.

---

## 🚀 Quickstart & Commands

Activate the virtual environment:
```powershell
.\.venv\Scripts\Activate.ps1
```

### 1. Run Autonomous Scan & Engagement Cycle
Ingests the feed, checks author credibility & relevance, likes matching posts, and generates value-add comments:
```powershell
python main.py run
```

### 2. View Real-Time Status & Quotas
```powershell
python main.py status
```

### 3. Launch the Web Command Center UI
Open the full visual control dashboard with real-time approval cards, content studio, and analytics:
```powershell
python main.py web --port 8000
```
Then navigate to `http://127.0.0.1:8000` in your browser.

### 4. Browse Cybersecurity Content Bank
View pre-vetted, high-authority thought-leadership posts across 6 sub-domains:
```powershell
python main.py bank
```

### 4. Draft & Schedule a Thought Leadership Post
- Draft from custom topic:
  ```powershell
  python main.py post --topic "IAM Wildcard Roles & Cloud Perimeters"
  ```
- Draft from Content Bank ID:
  ```powershell
  python main.py post --from-bank cb_iam_01
  ```
- Publish directly (bypassing HITL queue):
  ```powershell
  python main.py post --from-bank cb_secops_01 --publish
  ```

### 5. Review HITL Approval Queue
Interactively approve `[a]`, reject `[r]`, or skip `[s]` pending drafts:
```powershell
python main.py queue
```

### 6. View Historical Analytics & Activity Log
```powershell
python main.py analytics
```

### 7. Run Continuous Scheduler Loop
Runs recurring cycles with automatic quiet-hours pause and human jitter:
```powershell
python main.py schedule --interval-hours 4.0
```

### 8. Run Unit Tests
```powershell
python -m unittest discover tests
```

---

## ⚙️ Configuration & Connection Modes

Set your preferred mode in `.env`:
- `LINKEDIN_MODE=MOCK`: Zero-credential offline sandbox simulator with realistic cybersecurity posts.
- `LINKEDIN_MODE=BROWSER`: Live session mode using your `li_at` session cookie from browser developer tools (`LINKEDIN_LI_AT=...`). Includes natural human jitter delays between actions.
- `LINKEDIN_MODE=API`: Official LinkedIn REST API using OAuth token (`LINKEDIN_ACCESS_TOKEN=...`).

### LLM Providers
Set in `.env`:
- `LLM_PROVIDER=LOCAL_MOCK`: Deterministic, high-caliber domain engine (zero API keys needed).
- `LLM_PROVIDER=GEMINI` + `GEMINI_API_KEY`: Google Gemini 1.5 Flash.
- `LLM_PROVIDER=OPENAI` + `OPENAI_API_KEY`: OpenAI GPT-4o.
