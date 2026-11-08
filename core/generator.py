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
        """Dispatches prompt to configured LLM provider (Groq, Grok, Gemini, OpenAI) with auto-failover."""
        provider = self.config.llm_provider.upper()
        groq_key = self.config.groq_api_key or os.getenv("GROQ_API_KEY", "")
        grok_key = self.config.grok_api_key or os.getenv("GROK_API_KEY", os.getenv("XAI_API_KEY", ""))
        gemini_key = self.config.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        openai_key = self.config.openai_api_key or os.getenv("OPENAI_API_KEY", "")

        # If user passed a gsk_ key in grok_key, alias it to groq_key
        if grok_key and grok_key.startswith("gsk_"):
            groq_key = grok_key

        def _try_groq():
            if not groq_key:
                return None
            try:
                import requests
                headers = {
                    "Authorization": f"Bearer {groq_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "openai/gpt-oss-120b",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.6
                }
                res = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=10)
                if res.status_code == 200:
                    text = res.json()["choices"][0]["message"]["content"].strip()
                    logger.info("Successfully generated contextual comment using Groq API.")
                    return text
                else:
                    # Fallback to qwen on groq
                    payload["model"] = "qwen/qwen3.8-27b"
                    res2 = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=10)
                    if res2.status_code == 200:
                        text = res2.json()["choices"][0]["message"]["content"].strip()
                        logger.info("Successfully generated contextual comment using Groq API (Qwen).")
                        return text
                    logger.warning(f"Groq API returned status {res.status_code}: {res.text[:100]}")
            except Exception as e:
                logger.warning(f"Groq call failed ({e}).")
            return None

        def _try_grok():
            if not grok_key or grok_key.startswith("gsk_"):
                return None
            try:
                import requests
                headers = {
                    "Authorization": f"Bearer {grok_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "grok-beta",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.6
                }
                res = requests.post("https://api.x.ai/v1/chat/completions", headers=headers, json=payload, timeout=15)
                if res.status_code == 200:
                    text = res.json()["choices"][0]["message"]["content"].strip()
                    logger.info("Successfully generated contextual comment using Grok (xAI) API.")
                    return text
                else:
                    logger.warning(f"Grok API returned status {res.status_code}: {res.text[:100]}")
            except Exception as e:
                logger.warning(f"Grok call failed ({e}).")
            return None

        def _try_gemini():
            if not gemini_key:
                return None
            try:
                import requests
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
                    logger.warning("Gemini API rate limit reached (Free tier daily limit). Failing over...")
                else:
                    logger.warning(f"Gemini API returned status {res.status_code}: {res.text[:100]}")
            except Exception as e:
                logger.warning(f"Gemini call failed or timed out ({e}).")
            return None

        def _try_openai():
            if not openai_key:
                return None
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
                logger.warning(f"OpenAI call failed ({e}).")
            return None

        # Call in priority order based on provider setting
        if provider in ["GROQ", "GROK"]:
            return _try_groq() or _try_grok() or _try_gemini() or _try_openai()
        elif provider == "OPENAI":
            return _try_openai() or _try_groq() or _try_gemini()
        else: # GEMINI or default
            return _try_gemini() or _try_groq() or _try_openai()

    def generate_comment(
        self,
        post_content: str,
        author_profile: Dict[str, Any],
        suggested_angle: Optional[str] = None,
        post_type: str = "TECHNICAL_DISCUSSION"
    ) -> Tuple[str, float, list]:
        """
        Generates a 1-2 sentence tailored comment based on classified post type:
        - CAREER_MILESTONE: Warm, professional appreciation & congratulations for the new security role.
        - CERTIFICATION_ACHIEVEMENT: Encouraging commendation for discipline and milestone achievement.
        - PROJECT_OR_TOOL_LAUNCH: Constructive appreciation for open-source / engineering tooling.
        - EVENT_OR_WEBINAR: Supportive wish for high session engagement.
        - TECHNICAL_DISCUSSION: Technical peer insight or sharp operational question.
        Returns: (comment_text, confidence_score, list_of_violations)
        """
        author_name = author_profile.get("name", "Colleague")
        author_title = author_profile.get("headline", "Cybersecurity Professional")
        first_name = author_name.split()[0] if author_name else ""
        name_ref = f", {first_name}" if first_name and first_name.lower() != "colleague" else ""

        if post_type == "CAREER_MILESTONE":
            system_prompt = (
                "You are an experienced senior professional congratulating a colleague on their career announcement, new position, or promotion. "
                "CRITICAL INSTRUCTIONS: "
                "1. Offer warm, genuine, executive-to-peer appreciation and congratulations for their new role. "
                "2. Directly mention their role, company, or team if present in the post. "
                "3. DO NOT force cybersecurity terminology unless their post is explicitly about a security role. "
                "4. STRICTLY NO QUESTIONS. Do NOT include any question marks ('?'). "
                "5. Keep it concise (1 to 2 sentences max) in a warm, polished, human tone. "
                "6. NEVER use AI clichés ('testament', 'beacon', 'delve', 'pivotal', 'game-changer')."
            )
            user_prompt = (
                f"Author: {author_name} ({author_title})\n"
                f"Career Announcement:\n\"{post_content}\"\n\n"
                f"Write a warm, professional appreciation and congratulations comment (1-2 sentences):"
            )

        elif post_type == "CERTIFICATION_ACHIEVEMENT":
            system_prompt = (
                "You are an experienced professional congratulating a colleague on earning a certification, degree, or major accomplishment. "
                "CRITICAL INSTRUCTIONS: "
                "1. Commend their hard work, dedication, and discipline in an encouraging peer tone. "
                "2. Acknowledge the specific credential or achievement mentioned in the post. "
                "3. STRICTLY NO QUESTIONS. Do NOT include any question marks ('?'). "
                "4. Keep it concise (1 to 2 sentences max). "
                "5. NEVER use AI clichés ('testament', 'beacon', 'delve', 'pivotal', 'game-changer')."
            )
            user_prompt = (
                f"Author: {author_name} ({author_title})\n"
                f"Achievement Post:\n\"{post_content}\"\n\n"
                f"Write a supportive, professional congratulations recognizing their milestone (1-2 sentences):"
            )

        elif post_type == "PROJECT_OR_TOOL_LAUNCH":
            system_prompt = (
                "You are an experienced technology professional commenting on a colleague's product launch, project release, or open-source tool. "
                "CRITICAL INSTRUCTIONS: "
                "1. Commend the effort and dedication required to ship and build the project. "
                "2. Offer a warm, constructive affirmation on its practical value based on what it actually does. "
                "3. DO NOT force cybersecurity terminology unless the tool is specifically security-related. "
                "4. STRICTLY NO QUESTIONS. No question marks ('?'). "
                "5. 1 to 2 sentences max in a supportive peer tone."
            )
            user_prompt = (
                f"Author: {author_name} ({author_title})\n"
                f"Project Post:\n\"{post_content}\"\n\n"
                f"Write an appreciative, supportive comment on their project launch (1-2 sentences):"
            )

        elif post_type == "EVENT_OR_WEBINAR":
            system_prompt = (
                "You are a supportive peer commenting on a colleague's upcoming talk, webinar, podcast, or conference session. "
                "CRITICAL INSTRUCTIONS: "
                "1. Offer an encouraging note of support wishing them a fantastic session and high audience engagement. "
                "2. Directly reflect the topic of their session. "
                "3. STRICTLY NO QUESTIONS. No question marks ('?'). "
                "4. 1 to 2 sentences max."
            )
            user_prompt = (
                f"Author: {author_name} ({author_title})\n"
                f"Event Post:\n\"{post_content}\"\n\n"
                f"Write an encouraging note wishing them a successful session (1-2 sentences):"
            )

        elif post_type == "LEADERSHIP_AND_CULTURE":
            system_prompt = (
                "You are an experienced senior leader commenting on a colleague's post about management, work culture, team building, or career growth. "
                "CRITICAL INSTRUCTIONS: "
                "1. Express genuine appreciation for their perspective and validate the core insight. "
                "2. Offer a supportive, seasoned peer reflection on leadership and teamwork. "
                "3. STRICTLY NO QUESTIONS. No question marks ('?'). "
                "4. 1 to 2 sentences max in an appreciative tone."
            )
            user_prompt = (
                f"Author: {author_name} ({author_title})\n"
                f"Post Content:\n\"{post_content}\"\n\n"
                f"Write a supportive, validating leadership comment (1-2 sentences):"
            )

        else:
            # TECHNICAL_OR_INDUSTRY_INSIGHT or GENERAL_PROFESSIONAL
            system_prompt = (
                "You are an experienced senior professional commenting on a colleague's post based directly on the post's actual topic and nature. "
                "CRITICAL INSTRUCTIONS: "
                "1. Directly address the EXACT topic of the post (e.g. AI/ML, software engineering, cloud, data, security, product development, design, or modern business). "
                "2. Express genuine professional appreciation and validate their insight with an affirmative, constructive peer thought. "
                "3. DO NOT force cybersecurity terminology unless the post is explicitly about cybersecurity. Comment on the author's actual subject matter. "
                "4. STRICTLY NO QUESTIONS. Do NOT ask any questions or include question marks ('?'). Frame everything as an affirmative, supportive peer statement. "
                "5. Write 1 to 2 concise, polished sentences max. "
                "6. NEVER use generic empty praise ('Great post', 'Spot on', 'Thanks for sharing'). Pair your appreciation with specific technical or practical substance from their post. "
                "7. NEVER use AI buzzwords ('delve', 'testament', 'game-changer', 'fast-paced', 'in the digital age', 'crucial')."
            )
            user_prompt = (
                f"Author: {author_name} ({author_title})\n"
                f"Post Content:\n\"{post_content}\"\n\n"
                f"Write a 1-2 sentence appreciative, supportive comment addressing their exact topic without asking any questions:"
            )

        llm_response = self._call_llm(system_prompt, user_prompt)
        if not llm_response:
            # Deterministic domain fallbacks tailored to post nature (100% question-free & appreciative)
            lower = post_content.lower()

            if post_type == "CAREER_MILESTONE":
                comment = (
                    f"Huge congratulations on stepping into the new role{name_ref}! "
                    "Wishing you tremendous impact, fulfillment, and great success in this next chapter."
                )
            elif post_type == "CERTIFICATION_ACHIEVEMENT":
                comment = (
                    f"Huge congratulations on earning this milestone{name_ref}! "
                    "The discipline and dedicated preparation required to achieve this are significant. Very well deserved!"
                )
            elif post_type == "PROJECT_OR_TOOL_LAUNCH":
                comment = (
                    f"Fantastic work shipping this project{name_ref}! "
                    "Bringing new tools and solutions from concept to reality takes serious dedication, and it is great to see it out in the community."
                )
            elif post_type == "EVENT_OR_WEBINAR":
                comment = (
                    f"Wishing you a fantastic session and high-impact discussions{name_ref}! "
                    "Important conversation to be sharing with the broader community."
                )
            elif post_type == "LEADERSHIP_AND_CULTURE":
                comment = (
                    f"Really thoughtful perspective on team growth and operational alignment{name_ref}. "
                    "Grounding leadership in practical empathy and clear focus is what truly moves organizations forward."
                )
            # Software / Code / Development
            elif re.search(r'\b(code|coding|software|python|rust|javascript|typescript|golang|react|api|git)\b', lower):
                comment = (
                    "Really solid engineering perspective here. "
                    "Prioritizing maintainable design and pragmatic execution over premature complexity is what separates robust codebases from legacy debt."
                )
            # AI / ML / LLMs
            elif re.search(r'\b(ai|llm|gpt|genai|prompt|machine\s+learning|deep\s+learning|model)\b', lower):
                comment = (
                    "Strong observation on practical AI system design and model integration. "
                    "Balancing rapid model capabilities with reliable, deterministic execution boundaries is where the real engineering value is created."
                )
            # Cloud / Infrastructure / DevOps
            elif re.search(r'\b(cloud|aws|azure|gcp|kubernetes|k8s|docker|devops|infra|database|sql)\b', lower):
                comment = (
                    "Spot-on perspective on cloud infrastructure and operational hygiene. "
                    "Keeping systems streamlined, resilient, and well-architected by default makes a massive difference as environments scale."
                )
            # Cybersecurity (if explicitly cyber)
            elif re.search(r'\b(cve|vulnerability|exploit|brotli|rce|malware|ransomware|soc|iam|fido2|zero\s+trust|phishing|infosec|cyber)\b', lower):
                comment = (
                    "Really valuable technical breakdown on defensive posture and risk mitigation. "
                    "Prioritizing active signal over raw noise is essential for engineering and security teams alike."
                )
            else:
                comment = (
                    f"Really appreciate this thoughtful perspective{name_ref}. "
                    "Articulating these practical nuances brings valuable clarity to the broader professional community."
                )
        else:
            comment = llm_response.strip().strip('"')

        # Clean up any quotes or whitespace and normalize unicode punctuation
        comment = (
            comment.replace("\n", " ")
            .replace("“", '"')
            .replace("”", '"')
            .replace("‘", "'")
            .replace("’", "'")
            .replace("–", "-")
            .replace("—", "-")
            .replace("\u2011", "-")
            .replace("\u202f", " ")
            .replace("\u00a0", " ")
            .strip()
        )

        # STRICT ZERO-QUESTION ENFORCEMENT: Guarantee comment is purely appreciative & affirmative
        if "?" in comment:
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', comment) if s.strip()]
            statement_sentences = [s for s in sentences if not s.endswith("?") and "?" not in s]
            if statement_sentences:
                comment = " ".join(statement_sentences)
            else:
                comment = comment.replace("?", ".").strip()

        # Run through tone & anti-slop verification
        is_valid, violations, penalty = self.anti_slop.evaluate_comment_tone(comment, post_type=post_type)
        base_confidence = 94.0 if post_type in ["CAREER_MILESTONE", "CERTIFICATION_ACHIEVEMENT"] else 92.0
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

    def generate_connection_note(self, author_name: str, topic_or_context: str) -> str:
        """
        Generates a warm, professional connection invitation note (< 280 chars)
        referencing the author's recent post or perspective without asking questions.
        """
        first_name = author_name.split()[0] if author_name else "Colleague"
        clean_topic = topic_or_context.replace("\n", " ").strip()[:60] if topic_or_context else "systems engineering"

        note = f"Hi {first_name}, really appreciated your recent perspective on {clean_topic}. Would love to connect and follow your work here on LinkedIn!"
        if len(note) > 280:
            note = f"Hi {first_name}, really enjoyed your recent post. Would love to connect and follow your work here on LinkedIn!"
        return note

    def generate_thread_reply(self, original_comment: str, author_reply: str, author_name: str) -> str:
        """
        Generates a concise, supportive 1-2 sentence response to an incoming reply
        in an ongoing comment thread without question marks.
        """
        first_name = author_name.split()[0] if author_name else ""
        name_ref = f", {first_name}" if first_name else ""

        system_prompt = (
            "You are an experienced senior engineer continuing a thoughtful LinkedIn conversation. "
            "Write a concise, supportive 1-2 sentence follow-up acknowledging their reply. "
            "STRICTLY NO QUESTIONS. No question marks ('?'). "
            "Validate their point with seasoned peer perspective. Never use clichés or empty praise."
        )
        user_prompt = (
            f"Author replied: \"{author_reply}\"\n"
            f"Our previous comment: \"{original_comment}\"\n\n"
            f"Write a 1-2 sentence appreciative follow-up:"
        )

        reply = self._call_llm(system_prompt, user_prompt)
        if not reply:
            reply = f"Really appreciate the thoughtful follow-up{name_ref}. That operational nuance makes all the difference when putting these practices into production."

        # Clean quotes and strip questions
        reply = reply.strip().strip('"').replace("\n", " ")
        if "?" in reply:
            reply = reply.replace("?", ".").strip()

        return reply
