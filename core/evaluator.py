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
    reaction_type: str = "LIKE" # "LIKE", "CELEBRATE", "SUPPORT", "INSIGHTFUL", "LOVE"
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
        # Politics / partisan / geopolitical triggers
        political_terms = [
            "election", "democrats", "republicans", "partisan", "senate vote", "potus",
            "akhand bharat", "geopolitics", "geopolitical", "territory", "territorial",
            "border dispute", "war", "conflict", "regime", "propaganda"
        ]
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

    def _is_non_english(self, text: str) -> bool:
        """
        Detects if a post is predominantly written in a non-English language.
        Flags non-Latin alphabets (Cyrillic, Arabic, Devanagari/Hindi, CJK, etc.)
        as well as Latin-script foreign languages (Spanish, Portuguese, French, German, Italian, etc.).
        """
        if not text or len(text.strip()) < 10:
            return False

        # 1. Non-Latin foreign script detection
        foreign_scripts = re.findall(r'[\u0400-\u04FF\u0600-\u06FF\u0900-\u097F\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF\u0590-\u05FF\u0E00-\u0E7F]', text)
        if len(foreign_scripts) >= 5:
            return True

        lower = text.lower()
        words = re.findall(r'\b[a-zA-Záéíóúãõâêîôûàèìòùçñäöüß]{2,}\b', lower)
        if len(words) < 6:
            return False

        # Common markers for Portuguese / Spanish / French / German / Italian
        foreign_markers = {
            # Portuguese / Spanish
            "para", "com", "por", "uma", "não", "mais", "sobre", "todos", "este", "como",
            "você", "trabalho", "compartilhar", "certificação", "sucesso", "parabéns", "jornada",
            "obrigado", "estou", "nossa", "minha", "equipe", "estamos", "desafio", "conhecimento",
            "compartir", "certificación", "éxito", "gracias", "nuestro", "nuestra", "felicidades",
            "desarrollo", "aprendizaje", "oportunidad", "muy", "también", "está", "están",
            # French
            "dans", "pour", "avec", "cette", "notre", "votre", "équipe", "travail", "formation",
            "félicitations", "nouveau", "poste", "partager", "très", "heureux",
            # German
            "und", "für", "mit", "eine", "einer", "nicht", "auch", "unsere", "ihre", "arbeit",
            "herzlichen", "glückwunsch", "erfolg", "weiterbildung",
            # Italian
            "congratulazioni", "nuovo", "ruolo", "felice", "nostro", "nostra", "lavoro", "grazie"
        }

        english_stopwords = {
            "the", "be", "to", "of", "and", "a", "in", "that", "have", "i", "it", "for", "not",
            "on", "with", "he", "as", "you", "do", "at", "this", "but", "his", "by", "from",
            "they", "we", "say", "her", "she", "or", "an", "will", "my", "one", "all", "would",
            "there", "their", "what", "so", "up", "out", "if", "about", "who", "get", "which",
            "go", "me", "when", "make", "can", "like", "time", "no", "just", "him", "know",
            "take", "people", "into", "year", "your", "good", "some", "could", "them", "see",
            "other", "than", "then", "now", "look", "only", "come", "its", "over", "think",
            "also", "back", "after", "use", "two", "how", "our", "work", "first", "well", "way",
            "even", "new", "want", "because", "any", "these", "give", "day", "most", "us", "is", "are"
        }

        foreign_count = sum(1 for w in words if w in foreign_markers)
        english_count = sum(1 for w in words if w in english_stopwords)

        if foreign_count >= 3 and foreign_count >= english_count:
            return True
        if foreign_count >= 5:
            return True

        return False

    def _is_ad_or_sponsored(self, text: str, author_profile: Dict[str, Any]) -> bool:
        """
        Detects if a post is a paid advertisement, sponsored campaign, or sales pitch.
        """
        if author_profile.get("is_sponsored"):
            return True

        lower = text.lower()
        if re.search(r'\b(promoted|sponsored|advertisement)\b', lower):
            if re.search(r'\bpromoted\s+to\b', lower):
                return False
            if re.search(r'\b(sponsored\s+by|promoted\s+post|advertisement)\b', lower) or lower.startswith("promoted") or lower.startswith("sponsored"):
                return True

        ad_cues = [
            r"\bbook\s+a\s+demo\b",
            r"\bschedule\s+a\s+demo\b",
            r"\brequest\s+a\s+demo\b",
            r"\buse\s+code\s+['\"a-z0-9_-]+\s+for\b",
            r"\bpromo\s+code\b",
            r"\bdiscount\s+code\b",
            r"\bget\s+[0-9]+%\s+off\b",
            r"\bsave\s+[0-9]+%\s+(today|now)\b",
            r"\bstart\s+your\s+free\s+trial\b",
            r"\bsign\s+up\s+for\s+(a\s+)?free\s+trial\b",
            r"\blimited\s+time\s+offer\b",
            r"\bpricing\s+starts\s+at\b",
            r"\bclaim\s+your\s+(free\s+)?(spot|discount|seat|trial)\b"
        ]
        return any(re.search(pat, lower) for pat in ad_cues)

    def _is_hiring_post(self, text: str) -> bool:
        """
        Detects if a post is an employer/recruiter hiring announcement, job vacancy, or referral call.
        Does NOT trigger on personal career announcements ('I started a new role', 'I joined...').
        """
        lower = text.lower()

        # If it's a personal career milestone, it's not a job vacancy listing
        personal_milestone_cues = [
            r"\b(starting|started)\s+a\s+new\s+position\b",
            r"\bhapp(y|ily)\s+to\s+(share|announce)\s+that\s+i('m| am)?\s*(starting|joining|joined)\b",
            r"\bexcited\s+to\s+(share|announce)\s+that\s+i('m| am)?\s*(starting|joining|joined)\b",
            r"\bi('m| am)\s+joining\b",
            r"\bmy\s+new\s+role\s+as\b",
            r"\bthrilled\s+to\s+join\b"
        ]
        if any(re.search(p, lower) for p in personal_milestone_cues):
            return False

        hiring_cues = [
            r"\bwe('re| are)\s+hiring\b",
            r"\bi('m| am)\s+hiring\b",
            r"\bteam\s+is\s+hiring\b",
            r"\bcompany\s+is\s+hiring\b",
            r"\bactively\s+hiring\b",
            r"\bnow\s+hiring\b",
            r"\blooking\s+to\s+hire\b",
            r"\blooking\s+for\s+(a|an|experienced|talented|junior|senior|lead|staff)?\s*(engineer|developer|analyst|architect|consultant|candidate|intern|manager|specialist)\s+to\s+join\b",
            r"\bjoin\s+our\s+(team|company|firm|organization|family)\b",
            r"\bjoin\s+us\s+as\b",
            r"\bjob\s+(opening|openings|vacancy|vacancies|opportunity|opportunities|alert)\b",
            r"\bopen\s+(position|positions|roles?|vacancies)\b",
            r"\bimmediate\s+openings?\b",
            r"\bapply\s+(here|now|today|via|at)\b",
            r"\bhow\s+to\s+apply\b",
            r"\bsend\s+(your\s+)?(cv|resume)\b",
            r"\bshare\s+(your\s+)?(cv|resume)\b",
            r"\bdrop\s+(your\s+)?(cv|resume)\b",
            r"\bdm\s+(me\s+)?(your\s+)?(cv|resume)\b",
            r"\bemail\s+(your\s+)?(cv|resume)\b",
            r"\breferral(s)?\s+available\b",
            r"\bhiring\s+(alert|urgently|immediately)\b",
            r"\bhiring\s+for\s+(the\s+position|our\s+client|roles?)\b",
            r"\b(job|career)\s+description\b",
            r"#hiring\b",
            r"#jobopening\b",
            r"#recruiting\b",
            r"#recruitment\b",
            r"#jobs\b",
            r"#jobopportunity\b"
        ]
        return any(re.search(pat, lower) for pat in hiring_cues)

    def _is_competitive_cert_or_ctf(self, text: str) -> bool:
        """
        Detects if a post is about a competitive exam, practical / hands-on cybersecurity certification,
        or a CTF challenge (CEH, CompTIA Security+/CySA+/PenTest+, eJPT, OSCP, HackTheBox, TryHackMe, etc.).
        """
        lower = text.lower()
        competitive_patterns = [
            # CTFs & Practical Labs
            r"\b(ctf|ctfs)\b",
            r"\bhack\s*the\s*box\b",
            r"\bhtb\b",
            r"\btry\s*hack\s*me\b",
            r"\bthm\b",
            r"\bpicoctf\b",
            r"\bdefcon\s+ctf\b",
            r"\bcyber\s+apocalypse\b",
            r"\bcyberdefenders\b",
            r"\bblue\s*team\s*labs\b",
            r"\bbtlo\b",
            r"\bvulnhub\b",
            r"\boverthewire\b",
            r"\bunderthewire\b",
            r"\bproving\s+grounds\b",
            r"\bctfd\b",
            r"\bpwning\s+(boxes|machines)\b",

            # CompTIA Certifications
            r"\bcomptia\b",
            r"\bsecurity\+\b",
            r"\bsec\+\b",
            r"\bcysa\+\b",
            r"\bpentest\+\b",
            r"\bcasp\+\b",
            r"\bsecurityx\b",
            r"\bnetwork\+\b",
            r"\blinux\+\b",

            # EC-Council
            r"\bceh\b",
            r"\bcertified\s+ethical\s+hacker\b",
            r"\bceh\s+practical\b",
            r"\bchfi\b",
            r"\becsa\b",
            r"\blpt\b",

            # eLearnSecurity / INE
            r"\bejpt\b",
            r"\belearnsecurity\s+junior\s+penetration\s+tester\b",
            r"\bejptv[1-3]\b",
            r"\becppt\b",
            r"\bewpt\b",
            r"\bewptx\b",
            r"\becir\b",
            r"\becdfp\b",
            r"\bine\s+security\b",

            # OffSec
            r"\boscp\b",
            r"\boffsec\b",
            r"\boffensive\s+security\s+certified\s+professional\b",
            r"\boswp\b",
            r"\bosep\b",
            r"\boswe\b",
            r"\bosed\b",
            r"\bosce\b",
            r"\bosda\b",

            # ISC2 & ISACA
            r"\bcissp\b",
            r"\bccsp\b",
            r"\bsscp\b",
            r"\bcgrc\b",
            r"\bcsslp\b",
            r"\bisc2\s+cc\b",
            r"\bcism\b",
            r"\bcisa\b",
            r"\bcrisc\b",

            # SANS / GIAC
            r"\bgiac\b",
            r"\bgsec\b",
            r"\bgcih\b",
            r"\bgpen\b",
            r"\bgcfa\b",
            r"\bgnfa\b",
            r"\bgwapt\b",
            r"\bgrem\b",
            r"\bgmon\b",
            r"\bgcpn\b",

            # Red Team / Hands-On
            r"\bcrto\b",
            r"\bcertified\s+red\s+team\s+operator\b",
            r"\bcrte\b",
            r"\bpaces\b",
            r"\bbscp\b",
            r"\bburp\s+suite\s+certified\s+practitioner\b",
            r"\bpnpt\b",
            r"\bpjpt\b",
            r"\bcrtp\b",

            # Cloud Security Certifications
            r"\baws\s+certified\s+security\b",
            r"\bazure\s+security\s+engineer\b",
            r"\baz-500\b",
            r"\bsc-200\b",
            r"\bsc-300\b",
            r"\bsc-900\b",
            r"\bprofessional\s+cloud\s+security\s+engineer\b",

            # University / Academic Competitive Milestone
            r"\bgate\b",
            r"\bpassed\s+the\s+exam\b",
            r"\bcleared\s+the\s+exam\b",
            r"\bmaster('s)?\s+degree\b",
            r"\bphd\b"
        ]
        return any(re.search(pat, lower) for pat in competitive_patterns)

    def _is_course_certificate_post(self, text: str) -> bool:
        """
        Detects generic online video course completion certificates (Coursera, Udemy,
        LinkedIn Learning, etc.) which should be avoided from commenting.
        """
        lower = text.lower()
        course_cues = [
            r"\bcoursera\b",
            r"\budemy\b",
            r"\blinkedin\s+learning\b",
            r"\bedx\b",
            r"\bpluralsight\b",
            r"\bskillsoft\b",
            r"\bsimplilearn\b",
            r"\bgreat\s+learning\b",
            r"\bsololearn\b",
            r"\bdatacamp\b",
            r"\bcodecademy\b",
            r"\balison\b",
            r"\bfuturelearn\b",
            r"\bfreecodecamp\b",
            r"\bcertificate\s+of\s+completion\b",
            r"\bcertificate\s+of\s+attendance\b",
            r"\bcertificate\s+of\s+participation\b",
            r"\bcompleted\s+the\s+course\b",
            r"\bcompleted\s+(a|an)?\s*online\s+course\b",
            r"\bcompleted\s+the\s+training\b",
            r"\bfinished\s+the\s+course\b",
            r"\bcourse\s+certificate\b",
            r"\bwebinar\s+certificate\b",
            r"\bmasterclass\s+certificate\b",
            r"\battended\s+the\s+masterclass\b",
            r"\bcompleted\s+the\s+bootcamp\b",
            r"\bbootcamp\s+certificate\b",
            r"\bcompleted\s+the\s+workshop\b",
            r"\bworkshop\s+certificate\b",
            r"\bcourse\s+completed\b"
        ]
        return any(re.search(pat, lower) for pat in course_cues)

    def _classify_post_type(self, text: str) -> str:
        """Categorizes post intent: CAREER_MILESTONE, CERTIFICATION_ACHIEVEMENT, COMPETITIVE_EXAM_OR_CTF, PROJECT_OR_TOOL_LAUNCH, EVENT_OR_WEBINAR, LEADERSHIP_AND_CULTURE, TECHNICAL_OR_INDUSTRY_INSIGHT, GENERAL_PROFESSIONAL."""
        lower = text.lower()

        # 0. Competitive Certification / CTF
        if self._is_competitive_cert_or_ctf(text):
            return "COMPETITIVE_EXAM_OR_CTF"

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

        # 6. Holiday / Festive / Personal Celebration
        festive_patterns = [
            r"\b(happy\s+(diwali|deepavali|new\s+year|holidays|christmas|eid|thanksgiving|hanukkah))\b",
            r"\b(wishing\s+everyone\s+a\s+(happy|peaceful|blessed|prosperous))\b",
            r"\bfestival\s+of\s+lights\b",
            r"\bseason('s)?\s+greetings\b"
        ]
        if any(re.search(p, lower) for p in festive_patterns):
            return "HOLIDAY_OR_CELEBRATION"

        # 7. Technical / Engineering / AI / Data / Architecture
        tech_patterns = [
            r"\b(code|coding|software|python|javascript|typescript|rust|golang|c\+\+|api|database|sql|nosql|cloud|aws|azure|gcp|docker|kubernetes|k8s|ai|llm|machine\s+learning|deep\s+learning|data\s+science|architecture|security|vulnerability|system\s+design|performance|backend|frontend)\b"
        ]
        if any(re.search(p, lower) for p in tech_patterns):
            return "TECHNICAL_OR_INDUSTRY_INSIGHT"

        return "GENERAL_PROFESSIONAL"

    def _determine_reaction_type(self, post_type: str, text: str) -> str:
        """
        Determines the optimal LinkedIn reaction based on post nature:
        - CELEBRATE: Career milestones, certifications, competitive exams (CEH, CompTIA, eJPT), CTFs.
        - SUPPORT: Overcoming setbacks, learning journeys, career shifts, mentorship, resilience, mental health.
        - INSIGHTFUL: Deep technical architecture, security analysis, CVE breakdowns, tool launches.
        - LOVE: Festive greetings (Diwali, New Year, etc.), heartfelt gratitude, team praise.
        - LIKE: General industry commentary, news, professional updates.
        """
        lower = text.lower()

        # 1. CELEBRATE for accomplishments, exams, certs, CTFs, career advances
        if post_type in ["CAREER_MILESTONE", "CERTIFICATION_ACHIEVEMENT", "COMPETITIVE_EXAM_OR_CTF"]:
            return "CELEBRATE"

        # 2. LOVE for festive celebrations or heartfelt gratitude/tributes
        if post_type == "HOLIDAY_OR_CELEBRATION" or any(w in lower for w in [
            "happy diwali", "happy new year", "merry christmas", "eid mubarak",
            "so grateful", "deep gratitude", "heartfelt thank", "thank you to my mentor",
            "celebrating my team", "shoutout to my team"
        ]):
            return "LOVE"

        # 3. SUPPORT for learning in public, overcoming obstacles, career pivots, resilience, burnout
        support_patterns = [
            r"\b(struggle|struggled|struggling|burnout|mental\s+health|laid\s+off|job\s+loss|rejection|career\s+pivot|career\s+transition|non-tech\s+to\s+tech|imposter\s+syndrome|failure|lessons\s+learned\s+from\s+failing|perseverance|resilience|never\s+give\s+up|journey\s+wasn't\s+easy|keep\s+going|tough\s+journey)\b"
        ]
        if any(re.search(p, lower) for p in support_patterns):
            return "SUPPORT"

        # 4. INSIGHTFUL for technical architecture, vulnerability disclosures, tools, system design
        if post_type in ["TECHNICAL_OR_INDUSTRY_INSIGHT", "PROJECT_OR_TOOL_LAUNCH"]:
            return "INSIGHTFUL"

        tech_patterns = [
            r"\b(architecture|vulnerability|cve|zero\s+trust|least\s+privilege|iam|devsecops|system\s+design|threat\s+modeling|reverse\s+engineering|kernel|api\s+security|telemetry|detection\s+rule|observability|brotli|rce)\b"
        ]
        if any(re.search(p, lower) for p in tech_patterns):
            return "INSIGHTFUL"

        # 5. Default professional reaction
        return "LIKE"

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

        # 1. Non-English post check
        if self._is_non_english(post_content):
            flags.append("Excluded: Non-English language detected")
            return PostEvaluation(
                post_id=post_id,
                post_type="NON_ENGLISH",
                is_relevant=False,
                relevance_score=0.0,
                sentiment=sentiment,
                author_credibility=author_credibility,
                should_like=False,
                like_reason="Non-English post",
                should_comment=False,
                comment_reason="Filtered: Non-English post (English-only engagement enforced)",
                confidence_score=95.0,
                flags=flags
            )

        # 2. LinkedIn Ad / Sponsored post check
        if self._is_ad_or_sponsored(post_content, author_profile):
            flags.append("Excluded: LinkedIn Ad / Sponsored promotional post")
            return PostEvaluation(
                post_id=post_id,
                post_type="SPONSORED_OR_AD",
                is_relevant=False,
                relevance_score=0.0,
                sentiment=sentiment,
                author_credibility=author_credibility,
                should_like=False,
                like_reason="Ad / Sponsored post",
                should_comment=False,
                comment_reason="Filtered: LinkedIn Ad / Sponsored promotional post",
                confidence_score=98.0,
                flags=flags
            )

        # 3. Hiring / Job vacancy post check
        if self._is_hiring_post(post_content):
            flags.append("Excluded: Hiring / Job vacancy post")
            return PostEvaluation(
                post_id=post_id,
                post_type="HIRING_OR_JOB_ALERT",
                is_relevant=False,
                relevance_score=0.0,
                sentiment=sentiment,
                author_credibility=author_credibility,
                should_like=True,
                like_reason="Supportive reaction on job opening",
                should_comment=False,
                comment_reason="Filtered: Hiring / job opening post (avoided per user rule)",
                confidence_score=95.0,
                flags=flags
            )

        # 4. Course Certificate vs Competitive Cert / CTF / Practical Exams
        is_competitive = self._is_competitive_cert_or_ctf(post_content)
        is_course_cert = self._is_course_certificate_post(post_content)

        if is_course_cert and not is_competitive:
            flags.append("Excluded: Generic online course completion certificate")
            return PostEvaluation(
                post_id=post_id,
                post_type="COURSE_CERTIFICATE",
                is_relevant=False,
                relevance_score=0.0,
                sentiment=sentiment,
                author_credibility=author_credibility,
                should_like=True,
                like_reason="Supportive reaction for course completion",
                should_comment=False,
                comment_reason="Filtered: Generic online course completion certificate (Coursera/Udemy/LinkedIn Learning)",
                confidence_score=95.0,
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

        if is_competitive:
            post_type = "COMPETITIVE_EXAM_OR_CTF"
            suggested_angle = "Supportive peer congratulations recognizing competitive exam / CTF milestone"
            like_reason = "Celebrate competitive exam / CTF accomplishment"
            comment_reason = "Competitive exam / CTF: supportive peer recognition"
        elif post_type == "CAREER_MILESTONE":
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
        elif post_type == "HOLIDAY_OR_CELEBRATION":
            suggested_angle = "Warm holiday greeting and festive celebration wishes"
            like_reason = "Celebrate holiday greeting"
            comment_reason = "Holiday / festive post: polite celebration wish"
        else:
            suggested_angle = "Appreciative peer validation directly addressing the author's specific topic"
            comment_reason = "Professional insight: supportive peer appreciation"

        # Dynamically determine the matching LinkedIn reaction
        reaction_type = self._determine_reaction_type(post_type, post_content)
        if reaction_type == "SUPPORT" and post_type in ["GENERAL_PROFESSIONAL", "LEADERSHIP_AND_CULTURE"]:
            post_type = "COMMUNITY_SUPPORT_AND_JOURNEY"
            suggested_angle = "Empathetic, encouraging peer affirmation validating resilience, learning, and growth"
            like_reason = "Support colleague through learning journey and challenges"
            comment_reason = "Supportive peer encouragement on learning journey"

        return PostEvaluation(
            post_id=post_id,
            post_type=post_type,
            is_relevant=is_relevant,
            relevance_score=relevance_score,
            sentiment=sentiment,
            author_credibility=author_credibility,
            should_like=should_like,
            like_reason=like_reason,
            reaction_type=reaction_type,
            should_comment=should_comment,
            comment_reason=comment_reason,
            confidence_score=round(confidence_score, 1),
            suggested_angle=suggested_angle,
            flags=flags
        )
