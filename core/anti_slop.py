import re
from typing import List, Tuple
from config.settings import AntiSlopConfig

class AntiSlopFilter:
    """
    Enforces human-sounding communication and eliminates AI clichés,
    empty corporate buzzwords, and generic praise.
    """
    def __init__(self, config: AntiSlopConfig):
        self.banned_phrases = [p.lower() for p in config.banned_phrases]
        self.generic_comment_praise = [p.lower() for p in config.generic_comment_praise]

    def check_banned_phrases(self, text: str) -> List[str]:
        """Returns any matched banned AI clichés/phrases."""
        found = []
        lower = text.lower()
        for phrase in self.banned_phrases:
            pattern = r'\b' + re.escape(phrase) + r'\b'
            if re.search(pattern, lower):
                found.append(phrase)
        return found

    def check_generic_praise(self, text: str) -> List[str]:
        """Detects lazy/empty praise comments (e.g., 'Great post!')."""
        found = []
        lower = text.lower().strip()
        for phrase in self.generic_comment_praise:
            if phrase in lower:
                found.append(phrase)
        return found

    def count_emojis(self, text: str) -> int:
        """Counts standard emoji characters in text."""
        # Simple unicode range for emojis and pictographs
        emoji_pattern = re.compile(
            "[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50-\u2b55]",
            flags=re.UNICODE
        )
        return len(emoji_pattern.findall(text))

    def evaluate_comment_tone(self, comment: str, post_type: str = "TECHNICAL_DISCUSSION") -> Tuple[bool, List[str], int]:
        """
        Validates comment length and tone.
        Returns (is_valid, violations, score_penalty).
        """
        violations = []
        penalty = 0

        # Check banned phrases
        banned = self.check_banned_phrases(comment)
        if banned:
            violations.append(f"Contains banned AI clichés: {', '.join(banned)}")
            penalty += 35 * len(banned)

        # Check generic praise (allowed on career milestones and certifications where congratulations is intended)
        if post_type not in ["CAREER_MILESTONE", "CERTIFICATION_ACHIEVEMENT"]:
            praises = self.check_generic_praise(comment)
            if praises:
                violations.append(f"Contains generic praise: {', '.join(praises)}")
                penalty += 40

        # Check sentence count (target 1-3 sentences)
        sentences = [s for s in re.split(r'[.!?]+', comment) if s.strip()]
        if len(sentences) == 0:
            violations.append("Comment is empty.")
            penalty += 100
        elif len(sentences) > 3:
            violations.append(f"Comment is too long ({len(sentences)} sentences, max is 3).")
            penalty += 20

        # Emoji check
        emojis = self.count_emojis(comment)
        if emojis > 1:
            violations.append(f"Too many emojis in comment ({emojis}, max is 1).")
            penalty += 15

        is_valid = len(violations) == 0
        return is_valid, violations, penalty

    def evaluate_post_tone(self, post_text: str) -> Tuple[bool, List[str], int]:
        """
        Validates post structure, style, and tone against human quality checklist.
        """
        violations = []
        penalty = 0

        # Banned phrases
        banned = self.check_banned_phrases(post_text)
        if banned:
            violations.append(f"Contains banned clichés: {', '.join(banned)}")
            penalty += 25 * len(banned)

        # Check breathless starters
        lower = post_text.lower().strip()
        if lower.startswith("in today") or lower.startswith("here's a hard truth"):
            violations.append("Starts with forbidden breathless hook.")
            penalty += 30

        # Emoji count check (max 2)
        emojis = self.count_emojis(post_text)
        if emojis > 2:
            violations.append(f"Exceeded max emojis: {emojis} (allowed <= 2).")
            penalty += 15

        # Check paragraph formatting (requires short paragraphs and white space)
        paragraphs = [p for p in post_text.split("\n\n") if p.strip()]
        if len(paragraphs) < 3:
            violations.append("Post lacks paragraph spacing / white space structure.")
            penalty += 15

        is_valid = len(violations) == 0
        return is_valid, violations, penalty
