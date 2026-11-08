import logging
import time
from typing import List, Dict, Any, Optional
from connectors.base import LinkedInConnectorBase

logger = logging.getLogger("LinkedBot.MockLinkedIn")

MOCK_CYBERSECURITY_FEED = [
    {
        "post_id": "urn:li:post:1001",
        "author": {
            "name": "Sarah Lin",
            "headline": "CISO at Meridian Financial | Cloud Security & Identity",
            "profile_url": "https://linkedin.com/in/sarah-lin-ciso"
        },
        "content": (
            "Most cloud security breaches don't stem from sophisticated 0-day exploits. "
            "They happen because an engineer attached AdministratorAccess to a CI/CD runner at 2 AM and forgot to revoke it. "
            "If your team isn't auditing active IAM role usage and pruning stale permissions every 30 days, you are essentially flying blind in AWS."
        ),
        "created_at": time.time() - 1800,
        "likes_count": 42,
        "comments_count": 8
    },
    {
        "post_id": "urn:li:post:1002",
        "author": {
            "name": "David Vance",
            "headline": "Lead Detection Engineer | SecOps & Threat Intelligence",
            "profile_url": "https://linkedin.com/in/david-vance-secops"
        },
        "content": (
            "Our SOC cut alert volume by 64% last quarter simply by retiring every detection rule that hadn't produced a real incident in 90 days. "
            "More ingestion does not equal more security. Alert fatigue is a self-inflicted wound caused by treating SIEM ingestion volume as a KPI."
        ),
        "created_at": time.time() - 3600,
        "likes_count": 89,
        "comments_count": 21
    },
    {
        "post_id": "urn:li:post:1003",
        "author": {
            "name": "Elena Rostova",
            "headline": "Staff AppSec Engineer @ CloudNative Systems",
            "profile_url": "https://linkedin.com/in/elena-rostova-appsec"
        },
        "content": (
            "Mandating SMS or push-notification MFA is no longer the defensive shield many assume. "
            "With commodity adversary-in-the-middle kits, attackers harvest session tokens in real time. "
            "How is your engineering team approaching hardware-bound FIDO2 keys for internal developer accounts?"
        ),
        "created_at": time.time() - 7200,
        "likes_count": 115,
        "comments_count": 34
    },
    {
        "post_id": "urn:li:post:1004",
        "author": {
            "name": "Mark Sterling",
            "headline": "Growth Hacker & 10x Web3/Crypto Affiliate Specialist",
            "profile_url": "https://linkedin.com/in/mark-sterling-growth"
        },
        "content": (
            "Delve into our game-changing, revolutionary AI platform that is a testament to cutting-edge tech in today's fast-paced world! "
            "Drop a 'YES' below to get our free growth blueprint!"
        ),
        "created_at": time.time() - 9000,
        "likes_count": 12,
        "comments_count": 5
    },
    {
        "post_id": "urn:li:post:1005",
        "author": {
            "name": "Anonymous Insider",
            "headline": "Political Commentator & Tech Critic",
            "profile_url": "https://linkedin.com/in/anon-critic"
        },
        "content": (
            "The upcoming election is completely rigged and corrupt politicians are using cybersecurity agencies to silence dissent. "
            "Disgusting and horrible humans running the government."
        ),
        "created_at": time.time() - 10800,
        "likes_count": 3,
        "comments_count": 1
    },
    {
        "post_id": "urn:li:post:1006",
        "author": {
            "name": "Marcus Vance",
            "headline": "VP of Cybersecurity @ Sentinel Financial | CISO Advisor",
            "profile_url": "https://linkedin.com/in/marcus-vance-ciso"
        },
        "content": (
            "The critical flaw in most vulnerability management programs is treating CVSS score as an emergency ticket. "
            "If an exploit exists in a library that has zero network reachability and cannot be invoked at runtime, patching it immediately is operational theater. "
            "How does your team distinguish theoretical CVE score from actual exploit path?"
        ),
        "created_at": time.time() - 12000,
        "likes_count": 94,
        "comments_count": 19
    },
    {
        "post_id": "urn:li:post:1007",
        "author": {
            "name": "Alex Chen",
            "headline": "DevSecOps Lead @ ScaleApp | AppSec & CI/CD Security",
            "profile_url": "https://linkedin.com/in/alex-chen-devsecops"
        },
        "content": (
            "Hardcoded AWS secrets in private GitHub repos remain our #1 vector for credential leakage. "
            "Blocking developers at pre-commit with trufflehog and gitleaks is good, but without automated secret rotation, revoked credentials just linger in git history. "
            "What automated revocation patterns have worked best for your engineering teams?"
        ),
        "created_at": time.time() - 14000,
        "likes_count": 67,
        "comments_count": 14
    },
    {
        "post_id": "urn:li:post:1008",
        "author": {
            "name": "Rachel Adams",
            "headline": "Senior Threat Hunter & Malware Analyst",
            "profile_url": "https://linkedin.com/in/rachel-adams-threat"
        },
        "content": (
            "Ransomware operators are increasingly bypassing traditional EDR agents using Bring Your Own Vulnerable Driver (BYOVD) attacks. "
            "If kernel-level driver blocklists aren't strictly enforced across all production endpoints, sophisticated malware will simply blind your security telemetry. "
            "Is your threat intelligence team tracking driver abuse in your environment?"
        ),
        "created_at": time.time() - 16000,
        "likes_count": 112,
        "comments_count": 28
    },
    {
        "post_id": "urn:li:post:1009",
        "author": {
            "name": "Jason Miller",
            "headline": "Chief Security Officer @ Apex Cloud",
            "profile_url": "https://linkedin.com/in/jason-miller-cso"
        },
        "content": (
            "Zero Trust is not a product you purchase from a vendor booth at RSA. "
            "Zero Trust is the architectural discipline of assuming your internal network is already compromised, enforcing mutual TLS, and verifying identity on every single microservice hop. "
            "What has been your biggest cultural obstacle in deploying least privilege across legacy microservices?"
        ),
        "created_at": time.time() - 18000,
        "likes_count": 145,
        "comments_count": 42
    },
    {
        "post_id": "urn:li:post:1010",
        "author": {
            "name": "Priya Patel",
            "headline": "Staff AppSec Architect | API Security & OWASP Contributor",
            "profile_url": "https://linkedin.com/in/priya-patel-appsec"
        },
        "content": (
            "Broken Object Level Authorization (BOLA) remains the most dangerous and rampant API vulnerability in modern SaaS platforms. "
            "WAFs and API gateways can inspect syntax all day, but they cannot verify whether User A has permission to view Record ID 5492 belonging to User B. "
            "How are your security architects testing authorization logic inside automated CI tests?"
        ),
        "created_at": time.time() - 20000,
        "likes_count": 178,
        "comments_count": 51
    },
    {
        "post_id": "urn:li:post:1011",
        "author": {
            "name": "Daniel Thorne",
            "headline": "AI Security Researcher | LLM Red Teaming & Agent Safety",
            "profile_url": "https://linkedin.com/in/daniel-thorne-aisec"
        },
        "content": (
            "Prompt injection is not an LLM hallucination—it is unvalidated input execution. "
            "When you connect an LLM to internal database APIs and email systems without sandboxed runtime permissions, an untrusted prompt can exfiltrate sensitive records in seconds. "
            "What isolation boundaries are you enforcing between your autonomous agents and production datastores?"
        ),
        "created_at": time.time() - 22000,
        "likes_count": 204,
        "comments_count": 63
    }
]

class MockLinkedInConnector(LinkedInConnectorBase):
    """
    Offline simulator for testing LinkedBot logic, evaluation heuristics,
    rate limits, and comment generation without requiring live LinkedIn API credentials.
    """
    def __init__(self, simulate_rate_limit: bool = False):
        self.simulate_rate_limit = simulate_rate_limit
        self.liked_posts: List[str] = []
        self.comments: List[Dict[str, Any]] = []
        self.posts: List[Dict[str, Any]] = []
        self._scroll_step = 0

    def scroll_down(self, pixels: int = 900):
        self._scroll_step += 1
        logger.info(f"[MockLinkedIn] Scrolled feed down (scroll step: {self._scroll_step})")

    def get_visible_posts(self) -> List[Dict[str, Any]]:
        posts = list(MOCK_CYBERSECURITY_FEED)
        for i in range(1, (self._scroll_step * 5) + 1):
            posts.append({
                "post_id": f"urn:li:post:mock_dynamic_{i}",
                "author": {
                    "name": f"Practitioner {i}",
                    "headline": "Senior Cloud Infrastructure & Security Architect",
                    "profile_url": "https://linkedin.com"
                },
                "content": f"Modern distributed architectures require robust telemetry, automated canary deployments, and resilient failover patterns to maintain reliability at scale (Insight #{i}).",
                "created_at": time.time() - (i * 300),
                "likes_count": 25 + i,
                "comments_count": 5 + i
            })
        return posts

    def get_feed(self, keywords: List[str], target_profiles: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        logger.info(f"[MockLinkedIn] Scanning feed for keywords: {keywords[:4]}...")
        return list(MOCK_CYBERSECURITY_FEED)

    def like_post(self, post_id: str, reaction_type: str = "LIKE") -> Dict[str, Any]:
        if self.simulate_rate_limit:
            logger.warning("[MockLinkedIn] Simulated 429 Rate Limit Error encountered!")
            return {"status": "error", "error_code": 429, "message": "Rate limit exceeded"}

        self.liked_posts.append(post_id)
        logger.info(f"[MockLinkedIn] Successfully liked post: {post_id}")
        return {"status": "success", "post_id": post_id, "action": "LIKE"}

    def comment_post(self, post_id: str, comment_text: str) -> Dict[str, Any]:
        if self.simulate_rate_limit:
            logger.warning("[MockLinkedIn] Simulated 429 Rate Limit Error encountered!")
            return {"status": "error", "error_code": 429, "message": "Rate limit exceeded"}

        entry = {
            "comment_id": f"urn:li:comment:{len(self.comments) + 1}",
            "post_id": post_id,
            "comment_text": comment_text,
            "timestamp": time.time()
        }
        self.comments.append(entry)
        logger.info(f"[MockLinkedIn] Successfully commented on {post_id}:\n  -> \"{comment_text}\"")
        return {"status": "success", "comment": entry}

    def create_post(self, draft_text: str, media_attachment: Optional[str] = None) -> Dict[str, Any]:
        if self.simulate_rate_limit:
            return {"status": "error", "error_code": 429, "message": "Rate limit exceeded"}

        post_entry = {
            "post_id": f"urn:li:share:{int(time.time())}",
            "text": draft_text,
            "media": media_attachment,
            "timestamp": time.time()
        }
        self.posts.append(post_entry)
        logger.info(f"[MockLinkedIn] Published thought leadership post:\n{draft_text[:120]}...")
        return {"status": "success", "post": post_entry}
