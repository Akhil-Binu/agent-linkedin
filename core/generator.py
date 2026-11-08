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

        if provider == "OPENAI" and self.config.openai_api_key:
            try:
                import requests
                headers = {
                    "Authorization": f"Bearer {self.config.openai_api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "gpt-4o",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.7
                }
                res = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=30)
                if res.status_code == 200:
                    return res.json()["choices"][0]["message"]["content"].strip()
            except Exception as e:
                logger.warning(f"OpenAI call failed ({e}). Falling back to local generation.")

        elif provider == "GEMINI" and self.config.gemini_api_key:
            try:
                import requests
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.config.gemini_api_key}"
                payload = {
                    "contents": [{
                        "parts": [{"text": f"{system_prompt}\n\nUser: {user_prompt}"}]
                    }]
                }
                res = requests.post(url, json=payload, timeout=30)
                if res.status_code == 200:
                    data = res.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"].strip()
            except Exception as e:
                logger.warning(f"Gemini call failed ({e}). Falling back to local generation.")

        return None

    def generate_comment(self, post_content: str, author_profile: Dict[str, Any], suggested_angle: Optional[str] = None) -> Tuple[str, float, list]:
        """
        Generates a 1-3 sentence value-add comment.
        Returns: (comment_text, confidence_score, list_of_violations)
        """
        system_prompt = (
            "You are a Senior Cybersecurity Practitioner commenting on a peer's LinkedIn post. "
            "Write 1 to 2 sentences max. "
            "Do NOT write 'Great post', 'Thanks for sharing', or generic praise. "
            "Share a counter-perspective, an edge case, or ask a sharp technical question. "
            "NEVER use corporate buzzwords like 'delve', 'testament', 'game-changer', or 'fast-paced'."
        )
        user_prompt = f"Post: {post_content}\nAuthor: {author_profile.get('headline', '')}\nFocus angle: {suggested_angle or 'Practitioner reality'}"

        llm_response = self._call_llm(system_prompt, user_prompt)
        if not llm_response:
            # Deterministic cybersecurity domain fallback
            lower = post_content.lower()
            if "mfa" in lower or "iam" in lower or "auth" in lower:
                comment = (
                    "MFA stops credential stuffing, but without WebAuthn/FIDO2 keys, "
                    "AiTM reverse proxies like Evilginx bypass standard push and SMS in seconds. "
                    "Are you seeing resistance from leadership when pushing for hardware keys?"
                )
            elif "cloud" in lower or "s3" in lower or "aws" in lower or "gcp" in lower:
                comment = (
                    "The challenge isn't discovering cloud misconfigurations; it's that teams get buried under 5,000 low-risk findings. "
                    "Until security tooling prioritizes by reachability and actual IAM privilege path, developers will keep tuning alerts out."
                )
            elif "ai" in lower or "llm" in lower:
                comment = (
                    "Most AI security discussions focus on hypothetical rogue models, but the immediate headache is ungoverned API keys embedded in client-side scripts. "
                    "How are your teams auditing shadow MCP/agent connections across dev workstations?"
                )
            elif "soc" in lower or "siem" in lower or "alert" in lower:
                comment = (
                    "Alert fatigue isn't a staffing issue—it's an engineering debt issue. "
                    "If a detection rule fires 100 times without yielding a single incident response ticket, that rule belongs in the trash, not a dashboard."
                )
            else:
                comment = (
                    "A lot of security tooling promises automated remediation, but in production, breaking business workflows is what gets security teams sidelined. "
                    "How are you balancing blast radius containment with developer velocity?"
                )
        else:
            comment = llm_response.strip().strip('"')

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
            # Deterministic, high-caliber cybersecurity posts based on topic
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
            elif "tool" in lower or "sprawl" in lower or "vendor" in lower:
                post = (
                    "Adding another security tool is often worse than adding nothing.\n\n"
                    "Enterprise security teams now manage an average of 45 distinct security tools. Each one comes with its own agent, its own console, and its own stream of high-severity alerts.\n\n"
                    "The result isn't defense-in-depth. It's context-switching paralysis.\n\n"
                    "The highest-performing security teams I talk with aren't adopting new products every quarter. They are actively deprecating underused tools and mastering telemetry from their core endpoints and identity provider.\n\n"
                    "Signal always beats shelfware. What tool in your stack provides the least signal for the noise it makes?"
                )
            else:
                post = (
                    "Most incident response plans look great in a binder.\n\n"
                    "Then a real incident hits, and the team realizes the primary on-call engineer's laptop credentials expired, the Slack webhook was broken, and nobody knows who owns the compromised database.\n\n"
                    "Tabletop exercises aren't just for executives. They exist to uncover the mundane operational friction that destroys your mean time to respond (MTTR).\n\n"
                    "If your response plan hasn't been tested under simulated chaos in the last six months, you don't have a plan—you have a wish list.\n\n"
                    "What was the most unexpected operational bottleneck your team discovered during your last drill?"
                )
        else:
            post = llm_response.strip()

        # Tone & slop verification
        is_valid, violations, penalty = self.anti_slop.evaluate_post_tone(post)
        base_confidence = 95.0
        final_confidence = max(10.0, base_confidence - penalty)

        return post, round(final_confidence, 1), violations
