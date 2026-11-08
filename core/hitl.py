import json
import logging
import time
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests
from pydantic import BaseModel, Field
from config.settings import AppConfig

logger = logging.getLogger("LinkedBot.HITL")

QUEUE_FILE = Path(__file__).resolve().parent.parent / "hitl_queue.json"

class HITLItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    action_type: str # "comment", "post", "like"
    target_id: Optional[str] = None # e.g. post_id if comment or like
    target_author: Optional[str] = None
    original_content: Optional[str] = None # snippet of post being replied to
    draft_content: str # the text to post or comment
    confidence_score: float
    violations: List[str] = Field(default_factory=list)
    reason: str
    status: str = "pending" # "pending", "approved", "rejected"
    created_at: float = Field(default_factory=time.time)

class HITLManager:
    """
    Manages Human-in-the-Loop review queue for drafts with confidence < 85%
    or original posts pending publication.
    """
    def __init__(self, config: AppConfig, queue_file: Path = QUEUE_FILE):
        self.config = config
        self.queue_file = queue_file
        self._ensure_file()

    def _ensure_file(self):
        if not self.queue_file.exists():
            self._save_items([])

    def _load_items(self) -> List[Dict[str, Any]]:
        try:
            with open(self.queue_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read HITL queue file: {e}")
            return []

    def _save_items(self, items: List[Dict[str, Any]]):
        try:
            with open(self.queue_file, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write HITL queue file: {e}")

    def enqueue(self, item: HITLItem):
        items = self._load_items()
        items.append(item.model_dump())
        self._save_items(items)
        logger.info(f"Queued item [{item.id}] for human review (confidence: {item.confidence_score}%, reason: {item.reason})")
        self._send_notifications(item)

    def _send_notifications(self, item: HITLItem):
        msg = (
            f"🔔 *LinkedBot Approval Required*\n"
            f"• Type: {item.action_type.upper()}\n"
            f"• Confidence: {item.confidence_score}%\n"
            f"• Reason: {item.reason}\n"
            f"• Draft:\n> {item.draft_content}"
        )
        # Slack Webhook
        if self.config.slack_webhook_url:
            try:
                requests.post(self.config.slack_webhook_url, json={"text": msg}, timeout=5)
            except Exception as e:
                logger.warning(f"Slack webhook dispatch failed: {e}")

        # Telegram Bot
        if self.config.telegram_bot_token and self.config.telegram_chat_id:
            try:
                url = f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage"
                requests.post(url, json={"chat_id": self.config.telegram_chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=5)
            except Exception as e:
                logger.warning(f"Telegram alert dispatch failed: {e}")

    def list_pending(self) -> List[HITLItem]:
        items = self._load_items()
        return [HITLItem(**i) for i in items if i.get("status") == "pending"]

    def update_item_status(self, item_id: str, new_status: str, edited_content: Optional[str] = None) -> bool:
        items = self._load_items()
        updated = False
        for i in items:
            if i.get("id") == item_id:
                i["status"] = new_status
                if edited_content:
                    i["draft_content"] = edited_content
                updated = True
                break
        if updated:
            self._save_items(items)
        return updated
