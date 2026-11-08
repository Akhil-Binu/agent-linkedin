import os
import time
import random
import logging
from typing import List, Dict, Any, Optional
import requests
from connectors.base import LinkedInConnectorBase

logger = logging.getLogger("LinkedBot.BrowserConnector")

class LinkedInSessionConnector(LinkedInConnectorBase):
    """
    LinkedIn session connector using the user's browser `li_at` authentication cookie.
    Allows real feed reading, liking, and commenting on personal LinkedIn accounts
    without requiring enterprise partner API approvals.
    """
    def __init__(self, li_at_cookie: Optional[str] = None):
        self.li_at = li_at_cookie or os.getenv("LINKEDIN_LI_AT", "")
        self.session = requests.Session()
        self._setup_session()

    def _setup_session(self):
        if not self.li_at:
            logger.warning("No LINKEDIN_LI_AT cookie found. Live browser session will require configuration.")
            return

        self.session.cookies.set("li_at", self.li_at, domain=".linkedin.com")
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "X-RestLi-Protocol-Version": "2.0.0"
        })

    def _jitter_delay(self, min_sec: float = 3.0, max_sec: float = 8.0):
        """Simulate natural human pause to prevent behavioral bot detection."""
        delay = round(random.uniform(min_sec, max_sec), 2)
        logger.debug(f"Human jitter sleep: {delay}s")
        time.sleep(delay)

    def is_configured(self) -> bool:
        return bool(self.li_at and len(self.li_at) > 10)

    def get_feed(self, keywords: List[str], target_profiles: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Scans LinkedIn feed via authenticated Voyager endpoints.
        If unauthorized or unconfigured, returns graceful error or falls back.
        """
        if not self.is_configured():
            logger.warning("[SessionConnector] LINKEDIN_LI_AT not set. Switch LINKEDIN_MODE to MOCK or add cookie in .env.")
            return []

        logger.info("[SessionConnector] Querying authenticated LinkedIn session feed...")
        url = "https://www.linkedin.com/voyager/api/feed/updatesV2?count=10&q=feed"
        
        # Voyager requires csrf-token (JSESSIONID)
        jsessionid = self.session.cookies.get("JSESSIONID", "").replace('"', '')
        if jsessionid:
            self.session.headers["csrf-token"] = jsessionid

        try:
            res = self.session.get(url, timeout=15)
            if res.status_code == 200:
                data = res.json()
                elements = data.get("elements", [])
                results = []
                for el in elements:
                    urn = el.get("urn", "")
                    actor = el.get("actor", {})
                    commentary = el.get("commentary", {}).get("text", {}).get("text", "")
                    if commentary:
                        results.append({
                            "post_id": urn,
                            "author": {
                                "name": actor.get("name", {}).get("text", "LinkedIn Member"),
                                "headline": actor.get("description", {}).get("text", "Professional"),
                                "profile_url": actor.get("navigationContext", {}).get("url", "")
                            },
                            "content": commentary,
                            "created_at": time.time()
                        })
                return results
            elif res.status_code == 429:
                logger.error("[SessionConnector] Rate limit 429 hit from LinkedIn.")
                return [{"error": 429, "message": "Rate limit exceeded"}]
            elif res.status_code == 401 or res.status_code == 403:
                logger.error("[SessionConnector] Authentication expired. Please refresh your LINKEDIN_LI_AT cookie.")
                return []
            else:
                logger.warning(f"[SessionConnector] Voyager feed returned status {res.status_code}")
                return []
        except Exception as e:
            logger.error(f"[SessionConnector] Error fetching feed: {e}")
            return []

    def like_post(self, post_id: str) -> Dict[str, Any]:
        if not self.is_configured():
            return {"status": "error", "message": "No session cookie"}

        self._jitter_delay(2.0, 5.0)
        url = "https://www.linkedin.com/voyager/api/feed/reactions"
        payload = {
            "root": post_id,
            "reactionType": "LIKE"
        }
        jsessionid = self.session.cookies.get("JSESSIONID", "").replace('"', '')
        if jsessionid:
            self.session.headers["csrf-token"] = jsessionid

        try:
            res = self.session.post(url, json=payload, timeout=15)
            if res.status_code in [200, 201]:
                return {"status": "success", "post_id": post_id}
            elif res.status_code == 429:
                return {"status": "error", "error_code": 429, "message": "Rate limited"}
            return {"status": "error", "status_code": res.status_code}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def comment_post(self, post_id: str, comment_text: str) -> Dict[str, Any]:
        if not self.is_configured():
            return {"status": "error", "message": "No session cookie"}

        # Natural typing and human delay before commenting
        self._jitter_delay(4.0, 9.0)
        url = f"https://www.linkedin.com/voyager/api/feed/comments"
        payload = {
            "rootUrn": post_id,
            "commentText": comment_text
        }
        jsessionid = self.session.cookies.get("JSESSIONID", "").replace('"', '')
        if jsessionid:
            self.session.headers["csrf-token"] = jsessionid

        try:
            res = self.session.post(url, json=payload, timeout=15)
            if res.status_code in [200, 201]:
                return {"status": "success", "comment": comment_text}
            elif res.status_code == 429:
                return {"status": "error", "error_code": 429, "message": "Rate limited"}
            return {"status": "error", "status_code": res.status_code}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def create_post(self, draft_text: str, media_attachment: Optional[str] = None) -> Dict[str, Any]:
        if not self.is_configured():
            return {"status": "error", "message": "No session cookie"}

        self._jitter_delay(5.0, 12.0)
        url = "https://www.linkedin.com/voyager/api/contentcreation/normShares"
        payload = {
            "commentary": {
                "text": draft_text
            },
            "visibility": "PUBLIC"
        }
        jsessionid = self.session.cookies.get("JSESSIONID", "").replace('"', '')
        if jsessionid:
            self.session.headers["csrf-token"] = jsessionid

        try:
            res = self.session.post(url, json=payload, timeout=15)
            if res.status_code in [200, 201]:
                return {"status": "success", "post_id": res.json().get("urn")}
            elif res.status_code == 429:
                return {"status": "error", "error_code": 429, "message": "Rate limited"}
            return {"status": "error", "status_code": res.status_code}
        except Exception as e:
            return {"status": "error", "message": str(e)}
