from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class LinkedInConnectorBase(ABC):
    """
    Standard interface for LinkedIn API interactions.
    """

    @abstractmethod
    def get_feed(self, keywords: List[str], target_profiles: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Scans recent posts from target niches or key influencers.
        Returns a list of post dictionaries containing post_id, author, content, timestamp, etc.
        """
        pass

    @abstractmethod
    def like_post(self, post_id: str, reaction_type: str = "LIKE") -> Dict[str, Any]:
        """
        Applies a like / reaction to a post.
        Returns response dict with success status and details.
        """
        pass

    @abstractmethod
    def comment_post(self, post_id: str, comment_text: str) -> Dict[str, Any]:
        """
        Publishes a comment on a target post.
        Returns response dict with success status and comment_id.
        """
        pass

    @abstractmethod
    def create_post(self, draft_text: str, media_attachment: Optional[str] = None) -> Dict[str, Any]:
        """
        Publishes an original thought leadership post to LinkedIn.
        Returns response dict with status and created post ID/URL.
        """
        pass

    def search_posts(self, query: str, sort_by: str = "date_posted") -> List[Dict[str, Any]]:
        """
        Searches LinkedIn content by keyword or hashtag with date sorting.
        Default sorts by 'date_posted' (Past 24 hours / latest).
        """
        return []

    def send_connection_request(self, profile_url: str, note: Optional[str] = None) -> Dict[str, Any]:
        """
        Sends a warm connection request with an optional personalized note.
        """
        return {"status": "skipped", "message": "Not implemented"}

    def reply_to_comment(self, post_id: str, reply_text: str) -> Dict[str, Any]:
        """
        Posts a contextual follow-up reply in an existing comment thread.
        """
        return {"status": "skipped", "message": "Not implemented"}
