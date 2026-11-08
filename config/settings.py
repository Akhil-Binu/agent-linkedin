import os
from pathlib import Path
from typing import List, Dict, Any
import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment variables from .env
load_dotenv()

CONFIG_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CONFIG_DIR.parent
CONFIG_FILE = CONFIG_DIR / "config.yaml"

class AntiSlopConfig(BaseModel):
    banned_phrases: List[str] = Field(default_factory=list)
    generic_comment_praise: List[str] = Field(default_factory=list)

class CommentingRules(BaseModel):
    max_sentences: int = 3
    min_sentences: int = 1
    required_modes: List[str] = Field(default_factory=list)
    tone: str = ""

class PostingRules(BaseModel):
    framework: List[str] = Field(default_factory=list)
    max_emojis: int = 2
    paragraph_style: str = ""

class RateLimitConfig(BaseModel):
    max_likes_per_hour: int = 10
    max_likes_per_day: int = 35
    max_comments_per_hour: int = 5
    max_comments_per_day: int = 15
    max_posts_per_day: int = 2
    backoff_cooldown_seconds: int = 3600

class SafetyConfig(BaseModel):
    rate_limits: RateLimitConfig = Field(default_factory=RateLimitConfig)
    confidence_threshold_auto_engage: int = 85

DEFAULT_KEYWORDS = [
    "cybersecurity", "infosec", "cloud security", "appsec",
    "devsecops", "ciso", "soc", "zero trust", "incident response", "iam"
]

class AppConfig(BaseModel):
    domain: str = "cybersecurity"
    niches: List[str] = Field(default_factory=list)
    target_keywords: List[str] = Field(default_factory=lambda: list(DEFAULT_KEYWORDS))
    target_personas: List[str] = Field(default_factory=list)
    anti_slop: AntiSlopConfig = Field(default_factory=AntiSlopConfig)
    commenting_rules: CommentingRules = Field(default_factory=CommentingRules)
    posting_rules: PostingRules = Field(default_factory=PostingRules)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)

    # Runtime and external env variables
    llm_provider: str = Field(default="LOCAL_MOCK")
    gemini_api_key: str = Field(default="")
    openai_api_key: str = Field(default="")
    anthropic_api_key: str = Field(default="")
    linkedin_mode: str = Field(default="MOCK")
    slack_webhook_url: str = Field(default="")
    telegram_bot_token: str = Field(default="")
    telegram_chat_id: str = Field(default="")
    hitl_threshold: int = Field(default=85)

def load_config() -> AppConfig:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data: Dict[str, Any] = yaml.safe_load(f) or {}

    # Bind environment variables
    env_llm = os.getenv("LLM_PROVIDER", "LOCAL_MOCK")
    env_gemini = os.getenv("GEMINI_API_KEY", "")
    env_openai = os.getenv("OPENAI_API_KEY", "")
    env_anthropic = os.getenv("ANTHROPIC_API_KEY", "")
    env_li_mode = os.getenv("LINKEDIN_MODE", "MOCK")
    env_slack = os.getenv("SLACK_WEBHOOK_URL", "")
    env_tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    env_tg_chat = os.getenv("TELEGRAM_CHAT_ID", "")
    env_hitl_thresh = int(os.getenv("HITL_CONFIDENCE_THRESHOLD", str(data.get("safety", {}).get("confidence_threshold_auto_engage", 85))))

    config = AppConfig(
        domain=data.get("domain", "cybersecurity"),
        niches=data.get("niches", []),
        target_keywords=data.get("target_keywords", []),
        target_personas=data.get("target_personas", []),
        anti_slop=AntiSlopConfig(**data.get("anti_slop", {})),
        commenting_rules=CommentingRules(**data.get("commenting_rules", {})),
        posting_rules=PostingRules(**data.get("posting_rules", {})),
        safety=SafetyConfig(**data.get("safety", {})),
        llm_provider=env_llm,
        gemini_api_key=env_gemini,
        openai_api_key=env_openai,
        anthropic_api_key=env_anthropic,
        linkedin_mode=env_li_mode,
        slack_webhook_url=env_slack,
        telegram_bot_token=env_tg_token,
        telegram_chat_id=env_tg_chat,
        hitl_threshold=env_hitl_thresh,
    )
    return config
