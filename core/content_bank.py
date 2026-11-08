import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
import random
from config.settings import get_config_path

CONTENT_BANK_FILE = get_config_path("content_bank.yaml")

class ContentBank:
    """
    Manages pre-vetted, high-authority cybersecurity thought-leadership posts.
    """
    def __init__(self, file_path: Optional[Path] = None):
        self.file_path = file_path or get_config_path("content_bank.yaml")
        self.posts = self._load_posts()

    def _load_posts(self) -> List[Dict[str, Any]]:
        if not self.file_path.exists():
            return []
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                return data.get("posts", [])
        except Exception:
            return []

    def get_all(self) -> List[Dict[str, Any]]:
        return self.posts

    def get_by_id(self, post_id: str) -> Optional[Dict[str, Any]]:
        for p in self.posts:
            if p.get("id") == post_id:
                return p
        return None

    def get_by_subdomain(self, sub_domain: str) -> List[Dict[str, Any]]:
        return [p for p in self.posts if sub_domain.lower() in p.get("sub_domain", "").lower()]

    def pick_random(self, sub_domain: Optional[str] = None) -> Optional[Dict[str, Any]]:
        candidates = self.get_by_subdomain(sub_domain) if sub_domain else self.posts
        if not candidates:
            return None
        return random.choice(candidates)
