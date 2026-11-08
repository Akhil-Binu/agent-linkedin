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

    def get_feed(self, keywords: List[str], target_profiles: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        logger.info(f"[MockLinkedIn] Scanning feed for keywords: {keywords[:4]}...")
        return list(MOCK_CYBERSECURITY_FEED)

    def like_post(self, post_id: str) -> Dict[str, Any]:
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
