# Agent-LinkedIn (LinkedBot) 🚀

[![CI](https://github.com/Akhil-Binu/agent-linkedin/actions/workflows/ci.yml/badge.svg)](https://github.com/Akhil-Binu/agent-linkedin/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/Playwright-Automated-green.svg)](https://playwright.dev/)
[![LLM](https://img.shields.io/badge/LLM-Groq%20%7C%20Gemini%20%7C%20OpenAI-orange.svg)](https://groq.com/)
[![Semantic Versioning](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/Akhil-Binu/agent-linkedin/releases)

**Agent-LinkedIn (LinkedBot)** is an autonomous AI-powered LinkedIn growth and engagement agent. It simulates organic human browsing, performs intelligent post classification, executes targeted reactions, and drafts high-authority, value-additive comments free from corporate jargon or interrogation questions.

---

## 🌟 Key Features

- 🎭 **Real Playwright Browser Automation:** Persistent authenticated profile session with support for 2FA, checkpoints, human-like keystroke delays, smooth mouse wheel scrolling, and singleton lock management.
- 🔎 **Targeted Hashtag & "Latest" Search:** Ingest specific hashtags (e.g., `#cybersecurity`, `#devsecops`) filtered by `sortBy="date_posted"` ("Past 24 Hours") to engage with brand-new posts before comment fatigue sets in.
- 🤝 **Warm Connection Requests:** Automatically send personalized connection notes (< 280 chars) referencing the post topic to authors after commenting, adhering to safe daily quotas.
- 🔄 **2-Way Reply Tracking & Conversation:** Monitor previously engaged posts for author/peer replies and publish contextual follow-up statements to build genuine professional authority.
- 📑 **AI Carousel (PDF Slide) Generator:** Create modern 5-slide PDF document carousels (800x1000pt 4:5 portrait) with dark-mode cyber styling, ready for LinkedIn document posts.
- 🛡️ **Anti-Slop Tone Guard:** Automatically blocks corporate clichés (`delve`, `testament`, `game-changer`, `in today's fast-paced world`) and generic empty praise (`great post`, `totally agree`).
- 💬 **Zero-Question Appreciative Comments:** Eliminates interrogation questions. Crafts supportive, validating peer affirmations tailored directly to the specific topic of each post (AI, cloud, software engineering, leadership, cybersecurity).
- 🎯 **Dual-Condition Engagement Loop:** Guarantees satisfaction of user targets (e.g., minimum 15 comments and 20 reactions) across continuous feed streaming without early exits.
- 🏷️ **Post Nature Classification:** Automatically classifies posts into 7 distinct categories (`CAREER_MILESTONE`, `CERTIFICATION_ACHIEVEMENT`, `PROJECT_OR_TOOL_LAUNCH`, `EVENT_OR_WEBINAR`, `LEADERSHIP_AND_CULTURE`, `TECHNICAL_OR_INDUSTRY_INSIGHT`, and `GENERAL_PROFESSIONAL`) and applies contextual reactions (`CELEBRATE` vs. `LIKE`).
- 🤖 **Multi-Provider LLM Engine:** Seamless auto-failover across Groq (Llama-3.3 70B / GPT-OSS 120B), Google Gemini 1.5 Flash, OpenAI GPT-4o, and an offline deterministic mock fallback.
- 🛑 **Rate-Limit Circuit Breaker:** Strict hourly/daily caps on comments and likes with automatic backoff cooldown upon detecting LinkedIn rate limits (429).
- 👤 **Human-In-The-Loop (HITL) Staging:** Low-confidence comments and original thought leadership drafts are routed to an interactive review queue with optional Slack/Telegram alerts.
- 📊 **SQLite Analytics Engine:** Automatically tracks every post evaluated, confidence score, sentiment, and reaction history in `data/analytics.db`.
- 🌐 **Web Command Center:** Built-in FastAPI dashboard at `http://127.0.0.1:8000` with live metrics, approval cards, and content bank browser.

---

## 🏗️ Architecture

```
Agent-Linkedin/
├── config/              # YAML and Pydantic configuration schemas
│   ├── config.yaml      # Keywords, personas, and anti-slop rules
│   └── settings.py      # AppConfig and rate limiter limits
├── connectors/          # Feed & browser interaction drivers
│   ├── base.py          # Abstract base connector
│   ├── playwright_linkedin.py # Live browser automation via Playwright
│   └── mock_linkedin.py # Zero-credential offline sandbox simulator
├── core/                # Core agent intelligence
│   ├── anti_slop.py     # Cliché detection & tone evaluation
│   ├── evaluator.py     # Post classification & relevance scoring
│   ├── generator.py     # LLM multi-provider comment & post generator
│   ├── carousel_generator.py # 5-slide PDF carousel document builder
│   ├── hitl.py          # Human-in-the-loop review queue
│   ├── rate_limiter.py  # Sliding-window quota & backoff manager
│   ├── analytics.py     # SQLite metrics and audit tracker
│   └── content_bank.py  # Pre-vetted thought leadership drafts
├── tests/               # Full unittest test suite
├── web/                 # FastAPI Web Command Center
├── main.py              # Unified CLI entrypoint
└── pyproject.toml       # Package manifest & metadata
```

---

## ⚡ Quickstart

### 1. Prerequisites
- Python 3.10 or higher
- Git

### 2. Installation
```powershell
# Clone the repository
git clone https://github.com/Akhil-Binu/agent-linkedin.git
cd agent-linkedin

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies and Playwright Chromium
pip install -r requirements.txt
playwright install chromium
```

### 3. Environment Configuration
Copy the sample environment file:
```powershell
cp .env.example .env
```
Configure your credentials in `.env`:
```ini
LLM_PROVIDER=GROQ
GROQ_API_KEY=your_groq_api_key_here
LINKEDIN_MODE=REAL
```

---

## 🕹️ Interactive Feature Menu (Quickest Way to Run)

You can launch the interactive control menu listing features **[1] to [6]** without memorizing CLI arguments:

```powershell
# Option A: Run interactive menu script
python menu.py

# Option B: Run main.py (defaults to menu when no flags passed)
python main.py

# Option C: Double-click or run Windows launcher
.\run.bat
```

```text
Select a feature to execute:
  [1] 🔎 Targeted Search & Engagement (Latest #Cybersecurity Posts, 15 Comments & 20 Likes)
  [2] 🚀 General Feed Engagement Loop (Must-Rule: 15 Comments & 20 Likes)
  [3] 🤝 Warm Connection Requests (Personalized Outreach to Commented Authors)
  [4] 🔄 2-Way Reply Tracker (Continue Dialogues on Active Threads)
  [5] 📑 AI Carousel Generator (Design 5-Slide PDF Document for LinkedIn)
  --------------------------------------------------------------
  [6] 📊 View Analytics & Activity History
  [7] 🛡️ View Rate Limit & Queue Status
  [8] 🔐 Real LinkedIn 1-Time Interactive Login
  [0] ❌ Exit
```

---

## 💻 Direct CLI Usage & Commands

### 1. Authenticate LinkedIn Account (One-Time Setup)
Opens a dedicated Chromium window for logging in with your real LinkedIn account (handles 2FA/SMS checkpoints). Saves the session securely to `data/linkedin_browser_session`:
```powershell
python main.py login
```

### 2. Run Autonomous Engagement Cycle
Scrolls the feed, classifies posts, reacts to updates, and submits tailored supportive comments:
```powershell
# Run with default targets (15 comments, 20 likes)
python main.py run --real

# Run targeted hashtag search on latest posts ('Past 24 Hours')
python main.py run --real --search "#cybersecurity" --sort-by date_posted

# Automatically send warm connection requests after commenting
python main.py run --real --search "cloud security" --connect

# Run with custom engagement goals
python main.py run --real --target-comments 15 --target-likes 20

# Reset rate limit quotas before running
python main.py run --real --reset-limits
```

### 3. Generate 5-Slide PDF Document Carousels
Converts thought leadership topics into high-conversion PDF carousels formatted for LinkedIn document posts:
```powershell
# Generate carousel from custom topic
python main.py carousel --topic "IAM Wildcard Roles & Cloud Perimeters"

# Generate carousel from Content Bank ID
python main.py carousel --from-bank cb_iam_01

# Directly publish carousel as a document post to LinkedIn
python main.py carousel --from-bank cb_iam_01 --publish --real
```

### 4. 2-Way Reply Tracking & Conversation Follow-Up
Scans previously engaged posts for replies from authors/peers and posts supportive follow-ups:
```powershell
python main.py replies --limit 10
```

### 5. Launch Web Command Center
Starts the FastAPI dashboard for monitoring real-time metrics and approving drafts:
```powershell
python main.py web --port 8000
```
Visit `http://127.0.0.1:8000` in your web browser.

### 6. View Status & Quotas
```powershell
python main.py status
```

### 7. View SQLite Analytics Summary
```powershell
python main.py analytics
```

### 8. Draft Thought Leadership Content
```powershell
# Generate a new post draft from topic
python main.py post --topic "Zero Trust Microsegmentation in Cloud Kubernetes"

# Publish a pre-vetted draft from the content bank
python main.py post --from-bank cb_iam_01 --publish --real
```

### 9. Review HITL Queue
```powershell
python main.py queue
```

### 10. Run Continuous Scheduler
```powershell
# Run every 4 hours with quiet hours pause
python main.py schedule --interval-hours 4.0
```

---

## 🧪 Testing

LinkedBot includes a comprehensive automated test suite covering anti-slop filters, post evaluators, rate limiting, and dual-target engagement cycles:

```powershell
python -m unittest discover tests
```

---

## 🛡️ Governance & Security

- **[LICENSE](LICENSE):** Licensed under the permissive [MIT License](LICENSE).
- **[CONTRIBUTING.md](CONTRIBUTING.md):** Guidelines for code contributions, development workflow, and PR submission.
- **[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md):** Adheres to the Contributor Covenant v2.1.
- **[SECURITY.md](SECURITY.md):** Procedures for responsible vulnerability disclosure.

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/Akhil-Binu/agent-linkedin/issues).

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
