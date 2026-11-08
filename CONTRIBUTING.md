# Contributing to Agent-LinkedIn (LinkedBot)

Thank you for your interest in contributing to **Agent-LinkedIn**! We welcome bug fixes, documentation improvements, new connector features, and heuristics optimizations.

Please take a few moments to review these guidelines before submitting a pull request.

---

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this standard.

---

## Getting Started & Local Development

### 1. Prerequisites
- **Python 3.10+**
- **Git**
- **Chromium browser engine** (installed via Playwright)

### 2. Fork and Clone
```bash
git clone https://github.com/Akhil-Binu/agent-linkedin.git
cd agent-linkedin
```

### 3. Set Up Virtual Environment
```bash
# On Linux/macOS
python3 -m venv .venv
source .venv/bin/activate

# On Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 4. Install Dependencies & Playwright
```bash
pip install -r requirements.txt
playwright install chromium
```

### 5. Configure Environment
Copy the example environment configuration:
```bash
cp .env.example .env
```
For local sandbox development and testing without credentials, keep `LINKEDIN_MODE=MOCK` and `LLM_PROVIDER=LOCAL_MOCK`.

---

## Testing Guidelines

All contributions must pass existing tests and include unit tests for new functionality.

Run the full test suite:
```bash
python -m unittest discover tests
```

Tests should be fast, isolated, and deterministic. Avoid hardcoding live API keys or making external network calls in unit tests—use mock connectors and sandbox fixtures.

---

## Commit Message Conventions

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

- `feat:` A new feature or capability (e.g., `feat: add Anthropic Claude LLM provider`)
- `fix:` A bug fix (e.g., `fix: handle sticky header occlusion during comment submission`)
- `docs:` Documentation-only changes (e.g., `docs: update quickstart guide`)
- `refactor:` Code restructuring without changing external behavior
- `test:` Adding or updating tests
- `chore:` Maintenance tasks, dependency upgrades, or tooling changes

---

## Pull Request Workflow

1. **Create a branch** for your work:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. **Commit your changes** following the commit message format.
3. **Run tests** and verify everything passes cleanly:
   ```bash
   python -m unittest discover tests
   ```
4. **Push your branch** to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
5. **Open a Pull Request** against the `main` branch of `Akhil-Binu/agent-linkedin`.
6. Fill out the provided [Pull Request Template](.github/pull_request_template.md) completely.
7. Address any code review feedback promptly.

---

## Coding Standards

- Follow **PEP 8** style guidelines.
- Use explicit type hints for function signatures.
- Keep system prompts clean and maintain zero-slop anti-cliché filters.
- Never commit credentials, cookies, tokens, or personal session data.
