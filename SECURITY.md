# Security Policy

## Supported Versions

We provide security updates and patches for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

---

## Reporting a Vulnerability

The maintainers take security and user safety very seriously. If you discover a security vulnerability within this project, **please do NOT report it through a public GitHub issue**.

Instead, follow one of these private channels:

1. **GitHub Security Advisory (Preferred):**
   Navigate to the [Security Advisories tab](https://github.com/Akhil-Binu/agent-linkedin/security/advisories) on GitHub and click **"Report a vulnerability"**. This initiates a private disclosure between you and the project maintainers.

2. **Email Disclosure:**
   If GitHub Advisories are unavailable, email your report to [akhilbinu@users.noreply.github.com](mailto:akhilbinu@users.noreply.github.com) with:
   - Type of issue (e.g. credential leakage, injection, unhandled subprocess)
   - Step-by-step instructions or proof-of-concept to reproduce the issue
   - Affected files and components
   - Any proposed remediation

### What to Expect:
- **Initial Response:** Within 48 hours acknowledging receipt of your report.
- **Triage & Assessment:** Regular updates as the vulnerability is verified and patched.
- **Public Disclosure:** Coordinated release once the fix is deployed and verified.

---

## Critical Safety Notice for Users

- **Never commit `.env` or files inside `data/`**: These folders may store active cookies, browser state, and API tokens.
- **Session Protection**: Persistent browser sessions stored in `data/linkedin_browser_session` contain encrypted profile credentials. Keep this folder strictly excluded from version control and local backups.
