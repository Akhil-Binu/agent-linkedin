import os
import sys
from pathlib import Path
from typing import List, Dict, Any
import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

def get_base_dir() -> Path:
    """Returns the persistent base directory where runtime data, logs, and user configs live."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent

def get_bundle_dir() -> Path:
    """Returns the directory where bundled assets (config, templates) reside."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent

BASE_DIR = get_base_dir()
BUNDLE_DIR = get_bundle_dir()

# Load environment variables from .env in BASE_DIR, CWD, or default
env_locations = [BASE_DIR / ".env", Path.cwd() / ".env"]
loaded_env = False
for env_path in env_locations:
    if env_path.exists():
        load_dotenv(env_path)
        loaded_env = True
        break
if not loaded_env:
    load_dotenv()

def get_config_path(filename: str = "config.yaml") -> Path:
    """Resolves config files, falling back to bundled resources when frozen."""
    # 1. Custom or persistent user config
    persistent_cfg = BASE_DIR / "config" / filename
    if persistent_cfg.exists():
        return persistent_cfg
    # 2. Current working directory config
    cwd_cfg = Path.cwd() / "config" / filename
    if cwd_cfg.exists():
        return cwd_cfg
    # 3. Bundled config inside frozen executable
    bundled_cfg = BUNDLE_DIR / "config" / filename
    if bundled_cfg.exists():
        return bundled_cfg
    return persistent_cfg

CONFIG_DIR = BASE_DIR / "config"
PROJECT_ROOT = BASE_DIR
CONFIG_FILE = get_config_path("config.yaml")

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
    max_likes_per_hour: int = 100
    max_likes_per_day: int = 300
    max_comments_per_hour: int = 40
    max_comments_per_day: int = 100
    max_posts_per_day: int = 10
    max_connections_per_hour: int = 3
    max_connections_per_day: int = 10
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
    groq_api_key: str = Field(default="")
    gemini_api_key: str = Field(default="")
    grok_api_key: str = Field(default="")
    openai_api_key: str = Field(default="")
    anthropic_api_key: str = Field(default="")
    linkedin_mode: str = Field(default="MOCK")
    slack_webhook_url: str = Field(default="")
    telegram_bot_token: str = Field(default="")
    telegram_chat_id: str = Field(default="")
    hitl_threshold: int = Field(default=85)

def load_config() -> AppConfig:
    config_file = get_config_path("config.yaml")
    with open(config_file, "r", encoding="utf-8") as f:
        data: Dict[str, Any] = yaml.safe_load(f) or {}

    # Bind environment variables
    env_llm = os.getenv("LLM_PROVIDER", "LOCAL_MOCK")
    env_groq = os.getenv("GROQ_API_KEY", "")
    env_gemini = os.getenv("GEMINI_API_KEY", "")
    env_grok = os.getenv("GROK_API_KEY", os.getenv("XAI_API_KEY", ""))
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
        groq_api_key=env_groq,
        gemini_api_key=env_gemini,
        grok_api_key=env_grok,
        openai_api_key=env_openai,
        anthropic_api_key=env_anthropic,
        linkedin_mode=env_li_mode,
        slack_webhook_url=env_slack,
        telegram_bot_token=env_tg_token,
        telegram_chat_id=env_tg_chat,
        hitl_threshold=env_hitl_thresh,
    )
    return config
