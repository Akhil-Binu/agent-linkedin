import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, Tuple
from config.settings import RateLimitConfig

logger = logging.getLogger("LinkedBot.RateLimiter")

STATE_FILE = Path(__file__).resolve().parent.parent / "rate_limit_state.json"

class RateLimiter:
    """
    Guards LinkedIn interaction limits and handles rate-limit backoffs.
    Saves and loads state across executions.
    """
    def __init__(self, config: RateLimitConfig, state_file: Path = STATE_FILE):
        self.config = config
        self.state_file = state_file
        self.state = self._load_state()

    def _default_state(self) -> Dict[str, Any]:
        return {
            "backoff_until": 0.0,
            "actions": {
                "likes": [],
                "comments": [],
                "posts": []
            }
        }

    def _load_state(self) -> Dict[str, Any]:
        if not self.state_file.exists():
            return self._default_state()
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception as e:
            logger.warning(f"Could not load rate limit state ({e}). Resetting to default.")
            return self._default_state()

    def _save_state(self):
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write rate limit state: {e}")

    def _prune_actions(self, action_type: str, now: float):
        """Removes actions older than 24 hours."""
        cutoff_24h = now - 86400
        self.state["actions"][action_type] = [
            ts for ts in self.state["actions"].get(action_type, []) if ts > cutoff_24h
        ]

    def trigger_rate_limit_backoff(self, reason: str = "Rate limit hit or 429 received"):
        """Enforces a hard 60-minute pause."""
        cooldown = self.config.backoff_cooldown_seconds
        resume_time = time.time() + cooldown
        self.state["backoff_until"] = resume_time
        self._save_state()
        logger.critical(
            f"RATE LIMIT ALERT: {reason}. Pausing all LinkedIn actions for {cooldown // 60} minutes."
        )

    def reset(self):
        """Resets all action counters and cooldowns."""
        self.state = self._default_state()
        self._save_state()

    def can_perform(self, action_type: str) -> Tuple[bool, str]:
        """
        Validates if action ('likes', 'comments', 'posts') can be performed right now.
        """
        now = time.time()

        # Check backoff cooldown
        backoff_until = self.state.get("backoff_until", 0.0)
        if now < backoff_until:
            rem = int(backoff_until - now)
            return False, f"In 60-minute safety backoff cooldown. {rem // 60}m {rem % 60}s remaining."

        if action_type not in self.state["actions"]:
            return False, f"Unknown action type: {action_type}"

        self._prune_actions(action_type, now)
        timestamps = self.state["actions"][action_type]

        # Check hourly and daily limits
        cutoff_1h = now - 3600
        hourly_count = sum(1 for ts in timestamps if ts > cutoff_1h)
        daily_count = len(timestamps)

        if action_type == "likes":
            if hourly_count >= self.config.max_likes_per_hour:
                return False, f"Hourly like limit reached ({hourly_count}/{self.config.max_likes_per_hour})"
            if daily_count >= self.config.max_likes_per_day:
                return False, f"Daily like limit reached ({daily_count}/{self.config.max_likes_per_day})"

        elif action_type == "comments":
            if hourly_count >= self.config.max_comments_per_hour:
                return False, f"Hourly comment limit reached ({hourly_count}/{self.config.max_comments_per_hour})"
            if daily_count >= self.config.max_comments_per_day:
                return False, f"Daily comment limit reached ({daily_count}/{self.config.max_comments_per_day})"

        elif action_type == "posts":
            if daily_count >= self.config.max_posts_per_day:
                return False, f"Daily post limit reached ({daily_count}/{self.config.max_posts_per_day})"

        return True, "Permitted"

    def record_action(self, action_type: str):
        """Records an action occurrence."""
        now = time.time()
        if action_type in self.state["actions"]:
            self.state["actions"][action_type].append(now)
            self._save_state()

    def get_status_summary(self) -> Dict[str, Any]:
        """Returns readable status of quotas and cooldowns."""
        now = time.time()
        backoff_until = self.state.get("backoff_until", 0.0)
        is_cooling_down = now < backoff_until

        status = {
            "in_backoff": is_cooling_down,
            "seconds_until_resume": max(0, int(backoff_until - now)) if is_cooling_down else 0,
            "actions_24h": {}
        }
        for act in ["likes", "comments", "posts"]:
            self._prune_actions(act, now)
            status["actions_24h"][act] = len(self.state["actions"].get(act, []))
        return status
