import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from config.settings import AppConfig

class PostEvaluation(BaseModel):
    post_id: str
    post_type: str = "TECHNICAL_DISCUSSION" # "CAREER_MILESTONE", "CERTIFICATION_ACHIEVEMENT", "PROJECT_OR_TOOL_LAUNCH", "EVENT_OR_WEBINAR", "TECHNICAL_DISCUSSION"
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

    def _classify_post_type(self, text: str) -> str:
        """Categorizes post intent: CAREER_MILESTONE, CERTIFICATION_ACHIEVEMENT, PROJECT_OR_TOOL_LAUNCH, EVENT_OR_WEBINAR, LEADERSHIP_AND_CULTURE, TECHNICAL_OR_INDUSTRY_INSIGHT, GENERAL_PROFESSIONAL."""
        lower = text.lower()

        # 1. Career Milestone (New role, job start, joined as, promotion)
        career_patterns = [
            r"\b(starting|started)\s+a\s+new\s+position\b",
            r"\bhapp(y|ily)\s+to\s+(share|announce)\s+that\s+i('m| am)?\s*(starting|joining|joined)\b",
            r"\bexcited\s+to\s+(share|announce)\s+that\s+i('m| am)?\s*(starting|joining|joined)\b",
            r"\bthrilled\s+to\s+(share|announce|join)\b",
            r"\bpleased\s+to\s+(share|announce)\b",
            r"\bjoined\s+(as|the\s+team\s+at)\b",
            r"\bstarting\s+as\b",
            r"\bnew\s+role\s+as\b",
            r"\bpromoted\s+to\b",
            r"\bpromotion\s+to\b",
            r"\bcelebrating\s+my\s+new\s+role\b",
            r"\bnew\s+journey\s+(at|with)\b",
            r"\bfirst\s+day\s+(at|as)\b",
            r"\bnext\s+chapter\s+(at|in)\b",
            r"\bhonored\s+to\s+(step\s+into|join)\b",
            r"\bi('m| am)\s+joining\b",
            r"\baccepting\s+an\s+offer\b",
            r"\bnew\s+job\b"
        ]
        if any(re.search(p, lower) for p in career_patterns):
            return "CAREER_MILESTONE"

        # 2. Certification / Academic Achievement
        cert_patterns = [
            r"\b(passed|cleared|completed|earned|obtained)\s+(the|my|a)?\s*(cissp|ceh|cism|ccsp|security\+|oscp|ejpt|comptia|aws|gcp|azure|pmp|certification|credential|degree)\b",
            r"\bearned\s+(the|my|a)?\s*(cissp|certification|credential)\b",
            r"\bcertified\s+(in|as)\b",
            r"\bcredential\s+earned\b",
            r"\bgot\s+certified\b",
            r"\bcompleted\s+(the\s+)?certification\b",
            r"\bcertification\s+(achievement|unlocked|passed)\b",
            r"\bgraduated\s+from\b"
        ]
        if any(re.search(p, lower) for p in cert_patterns):
            return "CERTIFICATION_ACHIEVEMENT"

        # 3. Tool / Project / Open Source Launch
        project_patterns = [
            r"\b(open-source|open\s+source|github\s+repo|released\s+v[0-9]|proud\s+to\s+launch|published\s+a\s+new\s+tool|built\s+a\s+tool|shipped|launching|side\s+project|new\s+feature)\b"
        ]
        if any(re.search(p, lower) for p in project_patterns):
            return "PROJECT_OR_TOOL_LAUNCH"

        # 4. Event / Speaking / Conference
        event_patterns = [
            r"\b(speaking\s+at|hosting\s+a\s+webinar|panel\s+discussion|join\s+me\s+at|keynote\s+speaker|podcast|workshop|conference)\b"
        ]
        if any(re.search(p, lower) for p in event_patterns):
            return "EVENT_OR_WEBINAR"

        # 5. Leadership, Hiring, Career & Culture
        leadership_patterns = [
            r"\b(leadership|management|hiring|team\s+culture|work\s+culture|career\s+advice|mentorship|retention|remote\s+work|productivity|lessons\s+learned|strategy)\b"
        ]
        if any(re.search(p, lower) for p in leadership_patterns):
            return "LEADERSHIP_AND_CULTURE"

        # 6. Technical / Engineering / AI / Data / Architecture
        tech_patterns = [
            r"\b(code|coding|software|python|javascript|typescript|rust|golang|c\+\+|api|database|sql|nosql|cloud|aws|azure|gcp|docker|kubernetes|k8s|ai|llm|machine\s+learning|deep\s+learning|data\s+science|architecture|security|vulnerability|system\s+design|performance|backend|frontend)\b"
        ]
        if any(re.search(p, lower) for p in tech_patterns):
            return "TECHNICAL_OR_INDUSTRY_INSIGHT"

        return "GENERAL_PROFESSIONAL"

    def analyze_post(self, post_id: str, post_content: str, author_profile: Dict[str, Any]) -> PostEvaluation:
        flags = []
        sentiment = self._assess_sentiment(post_content)
        relevance_score = self._assess_relevance(post_content)
        author_credibility = self._assess_author(author_profile)
        post_type = self._classify_post_type(post_content)

        # Baseline safety checks
        if sentiment in ["controversial", "tragic", "negative"]:
            flags.append(f"Excluded due to sentiment: {sentiment}")
            return PostEvaluation(
                post_id=post_id,
                post_type=post_type,
                is_relevant=False,
                relevance_score=0.0,
                sentiment=sentiment,
                author_credibility=author_credibility,
                should_like=False,
                like_reason=f"Safety guard: avoid {sentiment} content",
                should_comment=False,
                comment_reason="Safety guard: no comments on unsafe/negative sentiment",
                confidence_score=95.0,
                flags=flags
            )

        if author_credibility == "spammer":
            flags.append("Excluded: author flagged as spammer/growth-hacker")
            return PostEvaluation(
                post_id=post_id,
                post_type=post_type,
                is_relevant=False,
                relevance_score=0.0,
                sentiment=sentiment,
                author_credibility=author_credibility,
                should_like=False,
                like_reason="Spam/low-credibility author",
                should_comment=False,
                comment_reason="Do not engage with spammers",
                confidence_score=99.0,
                flags=flags
            )

        # Content length check: must have enough substance to form an appreciative comment
        if len(post_content.strip()) < 25:
            flags.append("Insufficient post content length")
            return PostEvaluation(
                post_id=post_id,
                post_type=post_type,
                is_relevant=False,
                relevance_score=0.1,
                sentiment=sentiment,
                author_credibility=author_credibility,
                should_like=False,
                like_reason="Post too short",
                should_comment=False,
                comment_reason="Insufficient context",
                confidence_score=90.0,
                flags=flags
            )

        # Professional post is eligible for supportive engagement across topics
        is_relevant = True
        relevance_score = max(0.85, relevance_score)

        # Liking Criteria
        should_like = True
        like_reason = f"Supportive reaction on {post_type.lower()}"

        # Commenting Criteria
        should_comment = True

        # Confidence Calculation
        base_confidence = 90.0
        if author_credibility in ["peer", "potential_client"]:
            base_confidence += 5.0
        confidence_score = min(100.0, max(0.0, base_confidence))

        # Angle suggestion tailored to post nature
        lower_content = post_content.lower()

        if post_type == "CAREER_MILESTONE":
            suggested_angle = "Warm professional appreciation, congratulations, and wishing high impact in the new role"
            like_reason = "Celebrate career milestone"
            comment_reason = "Career milestone: professional congratulations and encouragement"
        elif post_type == "CERTIFICATION_ACHIEVEMENT":
            suggested_angle = "Supportive commendation for dedication, discipline, and achievement"
            like_reason = "Celebrate professional certification"
            comment_reason = "Certification achievement: supportive recognition"
        elif post_type == "PROJECT_OR_TOOL_LAUNCH":
            suggested_angle = "Commendation for shipping/building and constructive appreciation for practical utility"
            like_reason = "Supportive reaction for project launch"
            comment_reason = "Project launch: peer appreciation"
        elif post_type == "EVENT_OR_WEBINAR":
            suggested_angle = "Supportive wish for a successful session and strong attendee engagement"
            like_reason = "Support colleague speaking session"
            comment_reason = "Event / session: peer support"
        elif post_type == "LEADERSHIP_AND_CULTURE":
            suggested_angle = "Thoughtful leadership affirmation and validating the core team perspective"
            like_reason = "Appreciation for leadership insight"
            comment_reason = "Leadership / culture: validating insight"
        else:
            suggested_angle = "Appreciative peer validation directly addressing the author's specific topic"
            comment_reason = "Professional insight: supportive peer appreciation"

        return PostEvaluation(
            post_id=post_id,
            post_type=post_type,
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
