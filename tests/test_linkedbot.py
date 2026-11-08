import unittest
import time
from pathlib import Path
import tempfile
import json

from config.settings import AppConfig, AntiSlopConfig, RateLimitConfig, load_config
from core.anti_slop import AntiSlopFilter
from core.rate_limiter import RateLimiter
from core.evaluator import PostEvaluator
from core.hitl import HITLManager, HITLItem
from core.generator import ContentGenerator
from core.analytics import AnalyticsTracker
from core.content_bank import ContentBank
from core.scheduler import AutonomousScheduler

class TestAntiSlop(unittest.TestCase):
    def setUp(self):
        config = AntiSlopConfig(
            banned_phrases=["delve", "game-changer", "in today's fast-paced world", "testament"],
            generic_comment_praise=["great post", "totally agree", "thanks for sharing"]
        )
        self.filter = AntiSlopFilter(config)

    def test_detects_banned_cliches(self):
        text = "Let's delve into this game-changer in today's fast-paced world."
        banned = self.filter.check_banned_phrases(text)
        self.assertIn("delve", banned)
        self.assertIn("game-changer", banned)
        self.assertIn("in today's fast-paced world", banned)

    def test_detects_generic_praise(self):
        valid, violations, penalty = self.filter.evaluate_comment_tone("Great post! Totally agree.")
        self.assertFalse(valid)
        self.assertTrue(any("generic praise" in v for v in violations))

    def test_accepts_clean_value_comment(self):
        valid, violations, penalty = self.filter.evaluate_comment_tone(
            "Hardware tokens bypass AiTM phishing kits, but user resistance remains high. How are you handling rollout?"
        )
        self.assertTrue(valid)
        self.assertEqual(len(violations), 0)

class TestPostEvaluator(unittest.TestCase):
    def setUp(self):
        config = load_config()
        self.evaluator = PostEvaluator(config)

    def test_rejects_political_or_toxic_post(self):
        result = self.evaluator.analyze_post(
            "p1",
            "This upcoming election is rigged! Disgusting politicians.",
            {"headline": "Political Blogger"}
        )
        self.assertFalse(result.should_like)
        self.assertFalse(result.should_comment)
        self.assertIn(result.sentiment, ["controversial", "negative"])

    def test_rejects_spammer(self):
        result = self.evaluator.analyze_post(
            "p2",
            "10x your cybersecurity leads now! DM me.",
            {"headline": "Growth Hacker & 10x Affiliate Specialist"}
        )
        self.assertFalse(result.should_like)
        self.assertFalse(result.should_comment)

    def test_evaluates_high_signal_cybersecurity_post(self):
        result = self.evaluator.analyze_post(
            "p3",
            "Most cloud security breaches happen because IAM roles have AdministratorAccess attached.",
            {"headline": "CISO at FinTech Scaleup"}
        )
        self.assertTrue(result.is_relevant)
        self.assertTrue(result.should_like)
        self.assertTrue(result.confidence_score >= 80.0)

    def test_classifies_career_milestone_and_certifications(self):
        milestone = self.evaluator.analyze_post(
            "p4",
            "I'm happy to share that I'm starting a new position as Security Analyst at SentinelOne!",
            {"headline": "Security Analyst"}
        )
        self.assertEqual(milestone.post_type, "CAREER_MILESTONE")
        self.assertTrue(milestone.is_relevant)

        cert = self.evaluator.analyze_post(
            "p5",
            "Proud to announce that I have passed the CISSP exam!",
            {"headline": "SOC Engineer"}
        )
        self.assertEqual(cert.post_type, "CERTIFICATION_ACHIEVEMENT")
        self.assertTrue(cert.is_relevant)

class TestRateLimiter(unittest.TestCase):
    def setUp(self):
        self.temp_file = Path(tempfile.mktemp(suffix=".json"))
        config = RateLimitConfig(
            max_likes_per_hour=2,
            max_likes_per_day=5,
            backoff_cooldown_seconds=3600
        )
        self.limiter = RateLimiter(config, state_file=self.temp_file)

    def tearDown(self):
        if self.temp_file.exists():
            self.temp_file.unlink()

    def test_rate_limit_hourly_cap(self):
        allowed, _ = self.limiter.can_perform("likes")
        self.assertTrue(allowed)
        self.limiter.record_action("likes")

        allowed, _ = self.limiter.can_perform("likes")
        self.assertTrue(allowed)
        self.limiter.record_action("likes")

        allowed, msg = self.limiter.can_perform("likes")
        self.assertFalse(allowed)
        self.assertIn("Hourly like limit reached", msg)

    def test_rate_limit_backoff_cooldown(self):
        self.limiter.trigger_rate_limit_backoff("Test 429")
        allowed, msg = self.limiter.can_perform("likes")
        self.assertFalse(allowed)
        self.assertIn("safety backoff cooldown", msg)

class TestHITLManager(unittest.TestCase):
    def setUp(self):
        self.temp_file = Path(tempfile.mktemp(suffix=".json"))
        config = AppConfig()
        self.hitl = HITLManager(config, queue_file=self.temp_file)

    def tearDown(self):
        if self.temp_file.exists():
            self.temp_file.unlink()

    def test_enqueue_and_approve(self):
        item = HITLItem(
            action_type="comment",
            draft_content="Test comment on IAM hygiene.",
            confidence_score=78.5,
            reason="Low confidence score"
        )
        self.hitl.enqueue(item)

        pending = self.hitl.list_pending()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].id, item.id)

        self.hitl.update_item_status(item.id, "approved")
        pending_after = self.hitl.list_pending()
        self.assertEqual(len(pending_after), 0)

class TestAnalytics(unittest.TestCase):
    def setUp(self):
        self.temp_file = Path(tempfile.mktemp(suffix=".db"))
        self.tracker = AnalyticsTracker(db_path=self.temp_file)

    def tearDown(self):
        if self.temp_file.exists():
            self.temp_file.unlink()

    def test_record_and_aggregate(self):
        self.tracker.record_evaluation(
            post_id="p101",
            author={"name": "Alice", "headline": "Staff AppSec"},
            snippet="IAM least privilege testing",
            relevance=0.75,
            sentiment="constructive",
            credibility="peer",
            should_like=True,
            should_comment=True,
            confidence=94.0
        )
        self.tracker.record_action("likes", "p101", "Liked post", 94.0)

        metrics = self.tracker.get_summary_metrics()
        self.assertEqual(metrics["total_scanned"], 1)
        self.assertEqual(metrics["total_likes"], 1)
        self.assertEqual(metrics["avg_confidence"], 94.0)

class TestContentBank(unittest.TestCase):
    def setUp(self):
        self.bank = ContentBank()

    def test_bank_loads_cybersecurity_posts(self):
        posts = self.bank.get_all()
        self.assertGreater(len(posts), 0)

        # Test sub-domain filter
        iam_posts = self.bank.get_by_subdomain("IAM")
        self.assertGreater(len(iam_posts), 0)
        self.assertIn("IAM", iam_posts[0]["sub_domain"])

class TestSchedulerQuietHours(unittest.TestCase):
    def test_quiet_hours_over_midnight(self):
        sched = AutonomousScheduler(quiet_hours_start=22, quiet_hours_end=6)
        # Test method exists and returns a boolean
        result = sched.is_quiet_hours()
        self.assertIsInstance(result, bool)

class TestWebEndpoints(unittest.TestCase):
    def test_web_status_and_bank(self):
        from web.server import get_status, get_bank, get_queue
        status = get_status()
        self.assertEqual(status["domain"], "Cybersecurity")
        self.assertIn("mode", status)

        bank = get_bank()
        self.assertGreater(len(bank), 0)

        queue = get_queue()
        self.assertIsInstance(queue, list)

class TestDualTargetEngagementLoop(unittest.TestCase):
    def test_engagement_cycle_achieves_both_targets(self):
        from main import LinkedBotAgent
        bot = LinkedBotAgent(override_mode="MOCK")
        bot.rate_limiter.reset()

        bot.run_engagement_cycle(target_comments=15, target_likes=20, max_scrolls=10)

        self.assertGreaterEqual(len(bot.connector.liked_posts), 20)
        self.assertGreaterEqual(len(bot.connector.comments), 15)

        for c in bot.connector.comments:
            comment_text = c["comment_text"]
            self.assertNotIn("?", comment_text, f"Comment must not contain questions: {comment_text}")

class TestAdvancedFeatures(unittest.TestCase):
    def setUp(self):
        from main import LinkedBotAgent
        self.bot = LinkedBotAgent(override_mode="MOCK")
        self.bot.rate_limiter.reset()

    def test_targeted_search_ingestion(self):
        """Feature 1: Tests searching posts with hashtag/query."""
        posts = self.bot.connector.search_posts("#cybersecurity", sort_by="date_posted")
        self.assertIsInstance(posts, list)
        self.assertGreater(len(posts), 0)

    def test_warm_connection_request(self):
        """Feature 3: Tests connection note generation and request dispatch."""
        note = self.bot.generator.generate_connection_note("Elena Rostova", "IAM least privilege audits")
        self.assertIn("Elena", note)
        self.assertNotIn("?", note)
        self.assertLessEqual(len(note), 280)

        res = self.bot.connector.send_connection_request("https://linkedin.com/in/elena-rostova-appsec", note=note)
        self.assertEqual(res.get("status"), "success")
        self.assertEqual(len(self.bot.connector.connection_requests), 1)

    def test_thread_reply_generation(self):
        """Feature 5: Tests 2-way conversation reply generation."""
        reply = self.bot.generator.generate_thread_reply(
            original_comment="Focusing on reachability analysis cuts CVE noise.",
            author_reply="Thanks! We saw a 70% reduction in false alarms last quarter.",
            author_name="David Vance"
        )
        self.assertIsInstance(reply, str)
        self.assertGreater(len(reply), 15)
        self.assertNotIn("?", reply, "Thread reply must not contain questions")

    def test_carousel_generator(self):
        """Feature 6: Tests AI PDF carousel generation."""
        from core.carousel_generator import CarouselGenerator
        generator = CarouselGenerator()
        pdf_path = generator.generate_carousel_from_topic(
            topic="Zero Trust Kubernetes Security",
            category="DevSecOps",
            author_name="Akhil Binu"
        )
        self.assertTrue(pdf_path.exists())
        self.assertTrue(str(pdf_path).endswith(".pdf"))
        self.assertGreater(pdf_path.stat().st_size, 5000)

if __name__ == "__main__":
    unittest.main()
