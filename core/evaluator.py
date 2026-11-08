import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from config.settings import AppConfig

class PostEvaluation(BaseModel):
    post_id: str
    is_relevant: bool
    relevance_score: float
    sentiment: str # "positive", "constructive", "neutral", "negative", "controversial", "tragic"
    author_credibility: str # "high", "peer", "potential_client", "unknown", "spammer"
    should_like: bool
    like_reason: str
    should_comment: bool
    comment_reason: str
    confidence_score: float # 0 - 100
    suggested_angle: Optional[str] = None
    flags: List[str] = Field(default_factory=list)

class PostEvaluator:
    """
    Evaluates discovered posts against cybersecurity relevance,
    author standing, sentiment safety, and engagement potential.
    """
    def __init__(self, config: AppConfig):
        self.config = config
        self.keywords = [k.lower() for k in config.target_keywords]
        self.personas = [p.lower() for p in config.target_personas]

    def _assess_sentiment(self, text: str) -> str:
        lower = text.lower()
        # Politics / partisan triggers
        political_terms = ["election", "democrats", "republicans", "partisan", "senate vote", "potus"]
        if any(term in lower for term in political_terms):
            return "controversial"

        # Tragic triggers
        tragic_terms = ["rest in peace", "rip", "passed away", "tragic accident", "heartbroken"]
        if any(term in lower for term in tragic_terms):
            return "tragic"

        # Pure outrage / venting without technical content
        toxic_terms = ["disgusting", "horrible humans", "boycott", "scumbags", "worst company ever"]
        if any(term in lower for term in toxic_terms):
            return "negative"

        return "constructive"

    def _assess_relevance(self, text: str) -> float:
        lower = text.lower()
        matches = [kw for kw in self.keywords if re.search(r'\b' + re.escape(kw) + r'\b', lower)]
        if not matches:
            return 0.0
        # Score scales with matching density (up to 1.0)
        score = min(1.0, len(matches) * 0.25)
        return score

    def _assess_author(self, author_profile: Dict[str, Any]) -> str:
        title = author_profile.get("headline", "").lower()
        if not title:
            return "unknown"

        # Spammer detection
        if any(w in title for w in ["growth hacker", "guaranteed leads", "crypto guru", "10x affiliate"]):
            return "spammer"

        # Peer / Practitioner
        peer_keywords = [
            "security engineer", "appsec", "infosec", "soc analyst", "pentester",
            "architect", "detection engineer", "secops", "threat intel", "red team",
            "blue team", "cloud security", "security researcher"
        ]
        if any(w in title for w in peer_keywords):
            return "peer"

        # Target Buyer / Leader
        leader_keywords = [
            "ciso", "vp security", "head of security", "director of security",
            "director of engineering", "cto", "cso", "chief security officer"
        ]
        if any(w in title for w in leader_keywords):
            return "potential_client"

        return "unknown"

    def analyze_post(self, post_id: str, post_content: str, author_profile: Dict[str, Any]) -> PostEvaluation:
        flags = []
        sentiment = self._assess_sentiment(post_content)
        relevance_score = self._assess_relevance(post_content)
        author_credibility = self._assess_author(author_profile)

        # Baseline checks
        if sentiment in ["controversial", "tragic", "negative"]:
            flags.append(f"Excluded due to sentiment: {sentiment}")
            return PostEvaluation(
                post_id=post_id,
                is_relevant=False,
                relevance_score=relevance_score,
                sentiment=sentiment,
                author_credibility=author_credibility,
                should_like=False,
                like_reason=f"Safety guard: avoid {sentiment} content",
                should_comment=False,
                comment_reason="Safety guard: no comments on unsafe/negative sentiment",
                confidence_score=95.0, # High confidence in skipping
                flags=flags
            )

        if author_credibility == "spammer":
            flags.append("Excluded: author flagged as spammer/growth-hacker")
            return PostEvaluation(
                post_id=post_id,
                is_relevant=False,
                relevance_score=relevance_score,
                sentiment=sentiment,
                author_credibility=author_credibility,
                should_like=False,
                like_reason="Spam/low-credibility author",
                should_comment=False,
                comment_reason="Do not engage with spammers",
                confidence_score=99.0,
                flags=flags
            )

        is_relevant = relevance_score >= 0.25
        if not is_relevant:
            flags.append("Low cybersecurity relevance")
            return PostEvaluation(
                post_id=post_id,
                is_relevant=False,
                relevance_score=relevance_score,
                sentiment=sentiment,
                author_credibility=author_credibility,
                should_like=False,
                like_reason="Not directly relevant to cybersecurity niche",
                should_comment=False,
                comment_reason="Out of scope",
                confidence_score=90.0,
                flags=flags
            )

        # Liking Criteria:
        # Directly cybersecurity + author is peer, potential client, or high-value builder
        should_like = author_credibility in ["peer", "potential_client", "high"] and is_relevant
        like_reason = "Relevant cybersecurity discussion from respected industry peer/leader" if should_like else "Author relevance unclear"

        # Commenting Criteria:
        # High relevance, constructive, poses an open problem or architecture discussion
        should_comment = is_relevant and (relevance_score >= 0.5)

        # Confidence Calculation
        base_confidence = 70.0
        if is_relevant:
            base_confidence += (relevance_score * 20.0)
        if author_credibility in ["peer", "potential_client"]:
            base_confidence += 10.0
        elif author_credibility == "unknown":
            base_confidence -= 15.0

        confidence_score = min(100.0, max(0.0, base_confidence))

        # Angle suggestion
        suggested_angle = None
        lower_content = post_content.lower()
        if "iam" in lower_content or "mfa" in lower_content or "auth" in lower_content:
            suggested_angle = "Identity perimeter & AiTM / credential bypass edge case"
        elif "cloud" in lower_content or "s3" in lower_content or "aws" in lower_content or "gcp" in lower_content:
            suggested_angle = "Cloud misconfiguration & alert volume vs signal"
        elif "ai" in lower_content or "llm" in lower_content:
            suggested_angle = "AI red teaming / prompt injection real-world risk"
        else:
            suggested_angle = "Practical operational friction vs theoretical posture"

        comment_reason = "High-signal cybersecurity post with opportunity to contribute technical nuance" if should_comment else "Low engagement signal"

        return PostEvaluation(
            post_id=post_id,
            is_relevant=is_relevant,
            relevance_score=relevance_score,
            sentiment=sentiment,
            author_credibility=author_credibility,
            should_like=should_like,
            like_reason=like_reason,
            should_comment=should_comment,
            comment_reason=comment_reason,
            confidence_score=round(confidence_score, 1),
            suggested_angle=suggested_angle,
            flags=flags
        )
