import os
import logging
from typing import List, Dict, Any, Optional
import requests
from connectors.base import LinkedInConnectorBase
from connectors.mock_linkedin import MockLinkedInConnector
from connectors.browser_linkedin import LinkedInSessionConnector
from connectors.playwright_linkedin import PlaywrightLinkedInConnector, PLAYWRIGHT_AVAILABLE

logger = logging.getLogger("LinkedBot.LinkedInClient")

class LinkedInLiveClient(LinkedInConnectorBase):
    """
    Production LinkedIn API Connector using LinkedIn REST / UGC API.
    Requires LINKEDIN_ACCESS_TOKEN.
    """
    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or os.getenv("LINKEDIN_ACCESS_TOKEN", "")
        self.base_url = "https://api.linkedin.com/v2"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }

    def get_feed(self, keywords: List[str], target_profiles: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        # LinkedIn API endpoint for feed / shares
        # In actual practice, reading network posts requires LinkedIn Partner access / Community Management API
        try:
            res = requests.get(f"{self.base_url}/shares", headers=self.headers, params={"q": "owners"}, timeout=15)
            if res.status_code == 200:
                data = res.json()
                return data.get("elements", [])
            elif res.status_code == 429:
                return [{"error": 429, "message": "Rate limited"}]
        except Exception as e:
            logger.error(f"Error querying LinkedIn API: {e}")
        return []

    def like_post(self, post_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/reactions"
        payload = {
            "root": post_id,
            "reactionType": "LIKE"
        }
        try:
            res = requests.post(url, headers=self.headers, json=payload, timeout=15)
            if res.status_code in [200, 201]:
                return {"status": "success", "post_id": post_id}
            elif res.status_code == 429:
                return {"status": "error", "error_code": 429, "message": "Rate limit exceeded"}
            return {"status": "error", "status_code": res.status_code, "text": res.text}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def comment_post(self, post_id: str, comment_text: str) -> Dict[str, Any]:
        url = f"{self.base_url}/socialActions/{post_id}/comments"
        payload = {
            "message": {
                "text": comment_text
            }
        }
        try:
            res = requests.post(url, headers=self.headers, json=payload, timeout=15)
            if res.status_code in [200, 201]:
                return {"status": "success", "response": res.json()}
            elif res.status_code == 429:
                return {"status": "error", "error_code": 429, "message": "Rate limit exceeded"}
            return {"status": "error", "status_code": res.status_code, "text": res.text}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def create_post(self, draft_text: str, media_attachment: Optional[str] = None) -> Dict[str, Any]:
        # Using UGC post endpoint
        url = f"{self.base_url}/ugcPosts"
        payload = {
            "author": "urn:li:person:YOUR_URN", # Populated by user profile
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": draft_text
                    },
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        try:
            res = requests.post(url, headers=self.headers, json=payload, timeout=15)
            if res.status_code in [200, 201]:
                return {"status": "success", "post_id": res.json().get("id")}
            elif res.status_code == 429:
                return {"status": "error", "error_code": 429, "message": "Rate limit exceeded"}
            return {"status": "error", "status_code": res.status_code, "text": res.text}
        except Exception as e:
            return {"status": "error", "message": str(e)}

def get_linkedin_connector(mode: str = "MOCK", headless: bool = False) -> LinkedInConnectorBase:
    """Factory to get the appropriate connector (REAL/PLAYWRIGHT, MOCK, BROWSER/SESSION, API)."""
    mode_upper = mode.upper()
    if mode_upper in ["REAL", "PLAYWRIGHT"]:
        if PLAYWRIGHT_AVAILABLE:
            logger.info("Initializing Real Playwright Browser Connector (Persistent User Session)")
            return PlaywrightLinkedInConnector(headless=headless)
        else:
            logger.warning("Playwright is not available. Falling back to Mock.")

    elif mode_upper in ["BROWSER", "SESSION"]:
        logger.info("Initializing LinkedIn Authenticated Session Connector (Cookie Mode)")
        return LinkedInSessionConnector()

    elif mode_upper == "API":
        token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
        if token:
            logger.info("Initializing Live LinkedIn REST API Connector")
            return LinkedInLiveClient(access_token=token)
        else:
            logger.warning("No LINKEDIN_ACCESS_TOKEN provided for API mode. Falling back to Mock.")

    logger.info("Initializing Mock LinkedIn Connector (Zero credentials required)")
    return MockLinkedInConnector()
