import os
import re
import json
import logging
from typing import Dict, Any, Optional, Tuple
from config.settings import AppConfig
from core.anti_slop import AntiSlopFilter

logger = logging.getLogger("LinkedBot.Generator")

class ContentGenerator:
    """
    Generates human-sounding, authoritative cybersecurity comments and posts.
    Adheres strictly to the Hook -> Core Insight -> Example -> Takeaway framework
    and bans AI clichés.
    """
    def __init__(self, config: AppConfig):
        self.config = config
        self.anti_slop = AntiSlopFilter(config.anti_slop)

    def _call_llm(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Dispatches prompt to configured LLM provider if API key exists."""
        provider = self.config.llm_provider.upper()

        # Check Gemini API
        gemini_key = self.config.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        if (provider == "GEMINI" or gemini_key) and gemini_key:
            try:
                import requests
                # Use gemini-flash-latest with short timeout
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={gemini_key}"
                payload = {
                    "contents": [{
                        "parts": [{"text": f"System Instructions: {system_prompt}\n\nTask: {user_prompt}"}]
                    }],
                    "generationConfig": {
                        "temperature": 0.5,
                        "maxOutputTokens": 150
                    }
                }
                res = requests.post(url, json=payload, timeout=6)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        if text:
                            logger.info("Successfully generated contextual comment using Gemini API.")
                            return text.strip()
                elif res.status_code == 429:
                    logger.warning("Gemini API rate limit reached (Free tier daily limit exceeded). Seamlessly falling back to rule engine.")
                else:
                    logger.warning(f"Gemini API returned status {res.status_code}: {res.text[:100]}")
            except Exception as e:
                logger.warning(f"Gemini call failed or timed out ({e}). Seamlessly falling back to rule engine.")

        # Check OpenAI API
        openai_key = self.config.openai_api_key or os.getenv("OPENAI_API_KEY", "")
        if (provider == "OPENAI" or openai_key) and openai_key:
            try:
                import requests
                headers = {
                    "Authorization": f"Bearer {openai_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "gpt-4o",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.6
                }
                res = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=20)
                if res.status_code == 200:
                    text = res.json()["choices"][0]["message"]["content"].strip()
                    logger.info("Successfully generated contextual comment using OpenAI API.")
                    return text
            except Exception as e:
                logger.warning(f"OpenAI call failed ({e}). Falling back to local generation.")

        return None

    def generate_comment(self, post_content: str, author_profile: Dict[str, Any], suggested_angle: Optional[str] = None) -> Tuple[str, float, list]:
        """
        Generates a 1-3 sentence value-add comment directly relevant to the post.
        Returns: (comment_text, confidence_score, list_of_violations)
        """
        system_prompt = (
            "You are an experienced Principal Cybersecurity Engineer commenting on a peer's LinkedIn post. "
            "CRITICAL INSTRUCTIONS: "
            "1. You MUST directly and specifically address the EXACT technical topic of the post (e.g. if the post discusses a specific vulnerability, compression flaw, IAM misconfiguration, or SOC metric, focus strictly on that topic). "
            "2. Write 1 to 2 concise, sharp sentences max. "
            "3. Add technical substance: offer an edge case, a counter-perspective, or ask a sharp practitioner question. "
            "4. NEVER use generic praise ('Great post', 'Spot on', 'Thanks for sharing'). "
            "5. NEVER use AI buzzwords ('delve', 'testament', 'game-changer', 'fast-paced', 'in the digital age', 'crucial')."
        )
        user_prompt = (
            f"Author: {author_profile.get('name', 'Peer')} ({author_profile.get('headline', '')})\n"
            f"Post Content:\n\"{post_content}\"\n\n"
            f"Write a sharp, 1-2 sentence response addressing their exact topic:"
        )

        llm_response = self._call_llm(system_prompt, user_prompt)
        if not llm_response:
            # Deterministic cybersecurity domain fallback with STRICT word boundaries
            lower = post_content.lower()

            # 1. Vulnerability / CVE / Exploits / Flaws / Patching
            if re.search(r'\b(cve|flaw|vulnerability|vulnerabilities|exploit|brotli|rce|shell|zeroday|zero-day|0day|0-day|patch|patching|buffer|overflow)\b', lower):
                comment = (
                    "Vulnerabilities like this highlight the gap between theoretical presence and actual runtime reachability. "
                    "If a vulnerable library isn't exposed along an active execution path, emergency patching can be a massive distraction. "
                    "How is your team validating reachability before declaring a code-red drill?"
                )

            # 2. Identity & Access Management / MFA / FIDO2 / Phishing
            elif re.search(r'\b(mfa|fido2|webauthn|passkeys?|phishing|authenticator|aitm|credential|passwords?)\b', lower):
                comment = (
                    "Phishing-resistant keys are the only real defense against modern adversary-in-the-middle kits like Evilginx. "
                    "Standard push and SMS OTP are commoditized targets now. "
                    "How are your engineering teams approaching hardware-bound FIDO2 rollouts for developer accounts?"
                )

            # 3. Cloud Security & IAM / AWS / GCP / Azure
            elif re.search(r'\b(iam|aws|gcp|azure|s3|bucket|least-privilege|permissions|cloud|kubernetes|k8s)\b', lower):
                comment = (
                    "Over-permissioned service roles remain the quietest escalation vector in cloud infrastructure. "
                    "Pruning inactive wildcard permissions older than 60 days usually eliminates half the blast radius overnight. "
                    "Are you running automated IAM role usage audits across your CI/CD pipelines?"
                )

            # 4. SOC / Detection Engineering / SIEM / Alert Fatigue
            elif re.search(r'\b(soc|siem|soar|alert|fatigue|triage|incident response|detection|edr|xdr)\b', lower):
                comment = (
                    "Alert volume without context is a recipe for analyst burnout. "
                    "If a detection rule fires 100 times without producing a single actionable ticket, that rule belongs in the trash, not a dashboard. "
                    "What threshold does your team use to deprecate noisy detection rules?"
                )

            # 5. Application Security / DevSecOps / Code Security
            elif re.search(r'\b(appsec|devsecops|sast|dast|dependencies|supply chain|npm|pip|pipeline)\b', lower):
                comment = (
                    "The fastest way to lose developer trust is blocking pull requests for low-severity dependency alerts that aren't even invoked in production. "
                    "How does your security team filter build-time noise before interrupting release velocity?"
                )

            # 6. AI & LLM Security (Strict word boundary only)
            elif re.search(r'\b(ai|llm|genai|gpt|rag|prompt injection|agent safety)\b', lower):
                comment = (
                    "Treating autonomous AI agent outputs with the same zero-trust skepticism as raw user input is where many architectures fail. "
                    "What isolation boundaries are you enforcing between your agent runtimes and production datastores?"
                )

            # 7. General Cybersecurity / Leadership / Architecture
            else:
                comment = (
                    "Bridging theoretical compliance posture with real practitioner operational friction is where the battle is won. "
                    "How are you measuring mean time to remediate (MTTR) on the ground rather than just audit readiness?"
                )
        else:
            comment = llm_response.strip().strip('"')

        # Clean up any quotes or whitespace
        comment = comment.replace("\n", " ").strip()

        # Run through tone & anti-slop verification
        is_valid, violations, penalty = self.anti_slop.evaluate_comment_tone(comment)
        base_confidence = 92.0
        final_confidence = max(10.0, base_confidence - penalty)

        return comment, round(final_confidence, 1), violations

    def generate_post(self, topic: str, target_angle: Optional[str] = None) -> Tuple[str, float, list]:
        """
        Drafts an original thought leadership post following the framework:
        Hook -> Core Insight -> Example/Data -> Takeaway/Question.
        """
        system_prompt = (
            "You are LinkedBot, an authoritative cybersecurity leader writing a LinkedIn post. "
            "Framework: Hook -> Core Insight -> Example/Data -> Takeaway/Question. "
            "Tone: Punchy, practitioner-level, honest, 0 buzzwords. "
            "Format: Very short paragraphs (1-2 sentences each) with blank lines between them. "
            "Forbidden: 'In today's fast-paced world', 'delve', 'testament', 'game-changer', 'revolutionize'."
        )
        user_prompt = f"Topic: {topic}\nAngle: {target_angle or 'Operational reality vs vendor marketing'}"

        llm_response = self._call_llm(system_prompt, user_prompt)
        if not llm_response:
            lower = topic.lower()
            if "compliance" in lower or "audit" in lower or "soc2" in lower:
                post = (
                    "Compliance is not security.\n\n"
                    "Passing a SOC 2 audit simply proves you have documented policies and screenshots from last Tuesday. It says nothing about whether an attacker can pivot from your staging cluster into production.\n\n"
                    "I have seen organizations pass audits with flying colors while running unpatched domain controllers and hardcoded AWS secrets in public GitHub repos.\n\n"
                    "Auditors check boxes; adversaries look for paths of least resistance.\n\n"
                    "Treat compliance as the regulatory tax it is, but measure your actual security posture by how quickly you can isolate a compromised identity."
                )
            elif "iam" in lower or "cloud" in lower or "identity" in lower:
                post = (
                    "The cloud perimeter isn't a firewall. It's IAM.\n\n"
                    "Most cloud breaches don't happen because an attacker wrote an 0-day exploit against hypervisors. They happen because an engineer needed quick access at 2 AM, attached AdministratorAccess, and never detached it.\n\n"
                    "Over-permissioned service roles are the new open ports of the cloud era.\n\n"
                    "A single orphaned CI/CD token with wildcard permissions can turn a minor repository breach into an existential AWS disaster within minutes.\n\n"
                    "When was the last time your team ran an automated audit of inactive IAM roles older than 90 days?"
                )
            elif "vulnerability" in lower or "cve" in lower or "patch" in lower:
                post = (
                    "Most patch management policies are theater.\n\n"
                    "Mandating that every critical CVE must be patched within 72 hours sounds disciplined on paper. In practice, it leads to emergency deploys of unverified code that break production systems.\n\n"
                    "Without reachability analysis, your team is wasting cycles patching libraries that aren't even imported into execution memory.\n\n"
                    "Prioritizing by CVSS score alone is a vanity metric. Prioritizing by exploitable attack path is how mature engineering teams actually defend infrastructure.\n\n"
                    "What percentage of the CVEs your team patched last quarter were actually exposed to untrusted user input?"
                )
            else:
                post = (
                    "Adding another security tool is often worse than adding nothing.\n\n"
                    "Enterprise security teams now manage an average of 45 distinct security tools. Each one comes with its own agent, its own console, and its own stream of high-severity alerts.\n\n"
                    "The result isn't defense-in-depth. It's context-switching paralysis.\n\n"
                    "The highest-performing security teams aren't adopting new products every quarter. They are actively deprecating underused tools and mastering telemetry from their core endpoints and identity provider.\n\n"
                    "Signal always beats shelfware. What tool in your stack provides the least signal for the noise it makes?"
                )
        else:
            post = llm_response.strip()

        # Tone & slop verification
        is_valid, violations, penalty = self.anti_slop.evaluate_post_tone(post)
        base_confidence = 95.0
        final_confidence = max(10.0, base_confidence - penalty)

        return post, round(final_confidence, 1), violations
