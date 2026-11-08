import argparse
import logging
import sys
import time
from typing import Optional

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich import print as rprint
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from config.settings import load_config
from core.rate_limiter import RateLimiter
from core.evaluator import PostEvaluator
from core.generator import ContentGenerator
from core.hitl import HITLManager, HITLItem
from core.analytics import AnalyticsTracker
from core.content_bank import ContentBank
from core.scheduler import AutonomousScheduler
from connectors.linkedin_client import get_linkedin_connector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("LinkedBot")
console = Console() if RICH_AVAILABLE else None

class LinkedBotAgent:
    """
    Autonomous LinkedIn growth engine.
    Discovers, evaluates, likes, and comments on industry posts,
    drafts thought leadership content, enforces rate limits, and routes to HITL.
    """
    def __init__(self, override_mode: Optional[str] = None):
        self.config = load_config()
        self.active_mode = override_mode or self.config.linkedin_mode
        self.rate_limiter = RateLimiter(self.config.safety.rate_limits)
        self.evaluator = PostEvaluator(self.config)
        self.generator = ContentGenerator(self.config)
        self.hitl = HITLManager(self.config)
        self.analytics = AnalyticsTracker()
        self.content_bank = ContentBank()
        self.connector = get_linkedin_connector(self.active_mode)

    def close(self):
        """Closes any open browser connectors."""
        if hasattr(self.connector, "close"):
            try:
                self.connector.close()
            except Exception:
                pass

    def run_engagement_cycle(
        self,
        target_comments: int = 15,
        target_likes: int = 20,
        max_scrolls: int = 100,
        search_query: Optional[str] = None,
        sort_by: str = "date_posted",
        auto_connect: bool = False
    ):
        """
        Executes continuous feed streaming and engagement:
        - Feature 1: Targeted hashtag or keyword search with date_posted sorting ('Past 24 Hours' / 'Latest').
        - Feature 3: Warm connection request automation after commenting.
        - Scrolls dynamically until at least `target_comments` (15) posts are commented on
          AND at least `target_likes` (20) posts are liked on scroll.
        - Evaluates post classification and responds with topic-tailored appreciation (zero questions).
        - Enforces dual MUST-RULE: engagement continues until BOTH target_comments and target_likes are met.
        """
        header = f"🚀 LinkedBot Continuous Engagement Loop [Goal: >= {target_comments} Comments & >= {target_likes} Likes]"
        if search_query:
            header += f" | Search: '{search_query}'"
        if RICH_AVAILABLE:
            console.print(Panel(header, style="bold cyan"))
        else:
            print(f"\n=== {header} ===\n")

        comments_posted = 0
        likes_executed = 0
        connections_sent = 0
        seen_posts = set()
        scroll_count = 0

        # Feature 1: Initial navigation via targeted search or algorithm feed
        if search_query:
            print(f"🔎 Targeted Content Ingestion: '{search_query}' (Sort: {sort_by})...")
            if hasattr(self.connector, "search_posts"):
                self.connector.search_posts(search_query, sort_by=sort_by)
            else:
                self.connector.get_feed(keywords=[search_query])
        else:
            self.connector.get_feed(keywords=self.config.target_keywords)

        while (comments_posted < target_comments or likes_executed < target_likes) and scroll_count < max_scrolls:
            # Fetch visible posts currently rendered
            if hasattr(self.connector, "get_visible_posts"):
                visible = self.connector.get_visible_posts()
            else:
                visible = self.connector.get_feed(keywords=self.config.target_keywords)

            new_in_batch = 0

            for post in visible:
                post_id = post.get("post_id", "unknown")
                if post_id in seen_posts:
                    continue

                seen_posts.add(post_id)
                new_in_batch += 1
                author = post.get("author", {})
                content = post.get("content", "")

                print(f"\n--------------------------------------------------------")
                print(f"🔍 Post [{post_id}] | Author: {author.get('name')} ({author.get('headline')})")
                print(f"   Snippet: \"{content[:110]}...\"")

                # 1. Evaluate post classification and relevance based on post nature
                eval_result = self.evaluator.analyze_post(post_id, content, author)
                print(f"   🏷️ Nature: [{eval_result.post_type}] | Sentiment: {eval_result.sentiment}")

                # 2. React to every post encountered on scroll
                can_like, l_msg = self.rate_limiter.can_perform("likes")
                if can_like:
                    reaction = "CELEBRATE" if eval_result.post_type in ["CAREER_MILESTONE", "CERTIFICATION_ACHIEVEMENT"] else "LIKE"
                    res_like = self.connector.like_post(post_id, reaction_type=reaction) if hasattr(self.connector, "like_post") else {}
                    if res_like.get("status") == "success":
                        self.rate_limiter.record_action("likes")
                        self.analytics.record_action("likes", post_id, f"Reacted on scroll ({reaction})", 90.0, mode=self.active_mode)
                        likes_executed += 1
                        print(f"   👍 [ACTION] Reacted ({reaction}) on scroll (Total reactions: {likes_executed}/{target_likes})")
                    elif res_like.get("status") == "already_reacted":
                        print(f"   ℹ️ Post [{post_id}] already reacted; preserving existing reaction.")
                    else:
                        print(f"   ⚠️ Reaction attempt result: {res_like.get('message', 'unknown')}")
                else:
                    print(f"   ⚠️ Like skipped: {l_msg}")

                # 3. Comment based on post nature in an appreciative, supportive way (if target_comments not yet reached)
                if comments_posted < target_comments:
                    if eval_result.is_relevant:
                        can_comment, c_msg = self.rate_limiter.can_perform("comments")
                        if can_comment:
                            comment, confidence, violations = self.generator.generate_comment(
                                content, author, eval_result.suggested_angle, post_type=eval_result.post_type
                            )
                            print(f"\n   💬 Submitting Supportive Appreciation ({eval_result.post_type}, Confidence: {confidence}%):")
                            print(f"      \"{comment}\"")

                            res_c = self.connector.comment_post(post_id, comment)
                            if res_c.get("status") == "success":
                                comments_posted += 1
                                self.rate_limiter.record_action("comments")
                                self.analytics.record_action("comments", post_id, comment, confidence, mode=self.active_mode)
                                print(f"   🎯 [SUCCESS] Comment published! Progress: [{comments_posted}/{target_comments} comments | {likes_executed}/{target_likes} likes]")

                                # Feature 3: Warm Connection Request Follow-Up
                                if auto_connect and author.get("profile_url") and hasattr(self.connector, "send_connection_request"):
                                    can_conn, conn_msg = self.rate_limiter.can_perform("connections")
                                    if can_conn:
                                        note = self.generator.generate_connection_note(
                                            author.get("name", "Colleague"),
                                            eval_result.suggested_angle or content
                                        )
                                        res_conn = self.connector.send_connection_request(author.get("profile_url"), note=note)
                                        if res_conn.get("status") == "success":
                                            connections_sent += 1
                                            self.rate_limiter.record_action("connections")
                                            self.analytics.record_action("connections", author.get("profile_url"), note, 95.0, mode=self.active_mode)
                                            print(f"   🤝 [WARM CONNECT] Sent personalized invitation to {author.get('name')}")
                                        else:
                                            print(f"   ℹ️ Connection status: {res_conn.get('message')}")
                                    else:
                                        print(f"   ⚠️ Connection skipped: {conn_msg}")
                            else:
                                print(f"   ⚠️ Could not publish comment: {res_c.get('message')}")
                        else:
                            print(f"   ⚠️ Comment skipped: {c_msg}")
                    else:
                        print(f"   ⏭️ Comment skipped: ({eval_result.comment_reason})")
                else:
                    print(f"   ✅ Comment target reached ({comments_posted}/{target_comments}). Continuing likes until {target_likes}.")

                # Check if BOTH goals achieved
                if comments_posted >= target_comments and likes_executed >= target_likes:
                    print(f"\n🎉 GOAL ACHIEVED: Successfully satisfied MUST-RULE with {comments_posted} comments and {likes_executed} likes!")
                    break

            if comments_posted >= target_comments and likes_executed >= target_likes:
                break

            # Scroll down to load the next wave of posts
            scroll_count += 1
            print(f"\n📜 [Scroll #{scroll_count}] Scrolling down to discover more posts... (Comments: {comments_posted}/{target_comments} | Likes: {likes_executed}/{target_likes})")
            if hasattr(self.connector, "scroll_down"):
                self.connector.scroll_down(900)
            else:
                break

        print("\n========================================================")
        print(f"✅ Engagement run completed: {comments_posted}/{target_comments} comments | {likes_executed}/{target_likes} likes | {connections_sent} warm connections.")
        print("========================================================\n")

    def publish_or_draft_post(self, topic: Optional[str] = None, from_bank_id: Optional[str] = None, direct_publish: bool = False):
        """Drafts a thought-leadership post and either publishes or sends to HITL."""
        draft = ""
        violations = []
        confidence = 95.0

        if from_bank_id:
            bank_item = self.content_bank.get_by_id(from_bank_id)
            if bank_item:
                draft = bank_item.get("content", "").strip()
                selected_topic = bank_item.get("topic", "")
                print(f"\n📚 Loaded pre-vetted post from Content Bank [{from_bank_id}]: '{selected_topic}'")
            else:
                print(f"❌ Bank item '{from_bank_id}' not found.")
                return
        else:
            selected_topic = topic or "IAM Role Sprawl & Cloud Security Inaction"
            print(f"\n✍️ Generating Thought Leadership Post on: '{selected_topic}'...")
            draft, confidence, violations = self.generator.generate_post(selected_topic)

        if RICH_AVAILABLE:
            console.print(Panel(draft, title=f"[bold green]Thought Leadership Draft: {selected_topic}[/bold green]", expand=False))
        else:
            print("\n------------------- DRAFT PREVIEW -------------------")
            print(draft)
            print("-----------------------------------------------------")
        print(f"Tone Quality Score: {confidence}% | Violations: {violations if violations else 'None (Clean)'}")

        if direct_publish:
            allowed, reason = self.rate_limiter.can_perform("posts")
            if not allowed:
                print(f"❌ Cannot publish post: {reason}")
                return
            res = self.connector.create_post(draft)
            if res.get("error_code") == 429:
                self.rate_limiter.trigger_rate_limit_backoff("LinkedIn 429 on post publish")
            elif res.get("status") == "success":
                self.rate_limiter.record_action("posts")
                self.analytics.record_action("posts", None, draft, confidence)
                print("🎉 Post published successfully to LinkedIn!")
        else:
            item = HITLItem(
                action_type="post",
                draft_content=draft,
                confidence_score=confidence,
                violations=violations,
                reason=f"Thought leadership post review ({selected_topic})"
            )
            self.hitl.enqueue(item)
            print(f"📥 Staged in HITL queue as ID: [{item.id}]. Run 'python main.py queue' to review.")

    def browse_content_bank(self):
        """Lists available pre-vetted cybersecurity posts from content bank."""
        posts = self.content_bank.get_all()
        if RICH_AVAILABLE:
            table = Table(title="Cybersecurity Content Bank", show_lines=True)
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Sub-Domain", style="magenta")
            table.add_column("Topic", style="bold")
            table.add_column("Key Metrics / Themes", style="green")

            for p in posts:
                table.add_row(
                    p.get("id"),
                    p.get("sub_domain"),
                    p.get("topic"),
                    ", ".join(p.get("key_metrics", []))
                )
            console.print(table)
            print("\nTo stage any post into HITL or publish:")
            print("  python main.py post --from-bank <ID>")
        else:
            print(f"\n--- Cybersecurity Content Bank ({len(posts)} posts) ---")
            for p in posts:
                print(f"[{p.get('id')}] {p.get('sub_domain')} | {p.get('topic')}")

    def review_hitl_queue(self):
        """Interactive terminal approval loop for queued items."""
        pending = self.hitl.list_pending()
        if not pending:
            print("\n🎉 HITL Queue is empty! No pending items to review.")
            return

        print(f"\n📋 Found {len(pending)} pending item(s) in review queue:\n")
        for item in pending:
            print("========================================================")
            print(f"Item ID: [{item.id}] | Type: {item.action_type.upper()} | Confidence: {item.confidence_score}%")
            if item.target_author:
                print(f"Target Author: {item.target_author}")
            if item.original_content:
                print(f"In response to: \"{item.original_content[:120]}...\"")
            print(f"\nDraft Content:\n\"{item.draft_content}\"\n")
            if item.violations:
                print(f"Warnings: {item.violations}")

            choice = input("Decision -> [A]pprove & Send, [R]eject, [S]kip, or [Q]uit? ").strip().lower()
            if choice == "a":
                if item.action_type == "comment" and item.target_id:
                    self.connector.comment_post(item.target_id, item.draft_content)
                    self.rate_limiter.record_action("comments")
                    self.analytics.record_action("comments", item.target_id, item.draft_content, item.confidence_score, channel="hitl_approved")
                elif item.action_type == "post":
                    self.connector.create_post(item.draft_content)
                    self.rate_limiter.record_action("posts")
                    self.analytics.record_action("posts", None, item.draft_content, item.confidence_score, channel="hitl_approved")
                self.hitl.update_item_status(item.id, "approved")
                print(f"✅ Approved and dispatched item [{item.id}].")
            elif choice == "r":
                self.hitl.update_item_status(item.id, "rejected")
                self.analytics.record_action(item.action_type, item.target_id, item.draft_content, item.confidence_score, status="rejected", channel="hitl_rejected")
                print(f"❌ Rejected item [{item.id}].")
            elif choice == "q":
                break
            else:
                print(f"⏩ Skipped item [{item.id}].")

    def print_status(self):
        """Displays rate limit statuses and queue counts."""
        summary = self.rate_limiter.get_status_summary()
        pending = len(self.hitl.list_pending())

        if RICH_AVAILABLE:
            table = Table(title="LinkedBot Status Dashboard", show_lines=True)
            table.add_column("Metric", style="bold cyan")
            table.add_column("Value", style="green")

            table.add_row("Target Domain", self.config.domain.title())
            table.add_row("Connector Mode", self.config.linkedin_mode)
            table.add_row("LLM Provider", self.config.llm_provider)
            table.add_row("Pending HITL Items", str(pending))
            table.add_row("Rate Limit Cooldown", "ACTIVE" if summary['in_backoff'] else "Normal")
            if summary['in_backoff']:
                table.add_row("Seconds Until Resume", f"{summary['seconds_until_resume']}s")

            for act, count in summary["actions_24h"].items():
                table.add_row(f"Last 24h {act.title()}", str(count))

            console.print(table)
        else:
            print("\n📊 --- LinkedBot Status Dashboard ---")
            print(f"Domain:                  {self.config.domain.title()}")
            print(f"Mode:                    {self.config.linkedin_mode}")
            print(f"LLM Provider:            {self.config.llm_provider}")
            print(f"Pending HITL Items:      {pending}")
            print(f"In Rate Limit Backoff:   {summary['in_backoff']}")
            print("-------------------------------------\n")

    def print_analytics(self):
        """Displays historical metrics from SQLite."""
        metrics = self.analytics.get_summary_metrics()
        if RICH_AVAILABLE:
            table = Table(title="LinkedBot Historical Analytics", show_lines=True)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="bold green")

            table.add_row("Total Scanned Posts", str(metrics["total_scanned"]))
            table.add_row("Average Evaluation Confidence", f"{metrics['avg_confidence']}%")
            table.add_row("Total Likes Executed", str(metrics["total_likes"]))
            table.add_row("Total Comments Published", str(metrics["total_comments"]))
            table.add_row("Total Thought Leadership Posts", str(metrics["total_posts"]))
            console.print(table)

            if metrics["recent_actions"]:
                rec_table = Table(title="Recent Activity Log", show_lines=True)
                rec_table.add_column("Timestamp", style="dim")
                rec_table.add_column("Type", style="magenta")
                rec_table.add_column("Target / Snippet", style="white")

                for r in metrics["recent_actions"]:
                    rec_table.add_row(r["time"], r["type"].upper(), r["snippet"])
                console.print(rec_table)
        else:
            print("\n📊 --- LinkedBot Analytics ---")
            print(f"Total Scanned Posts:     {metrics['total_scanned']}")
            print(f"Average Confidence:      {metrics['avg_confidence']}%")
            print(f"Total Likes Executed:    {metrics['total_likes']}")
            print(f"Total Comments:          {metrics['total_comments']}")
            print(f"Total Posts:             {metrics['total_posts']}")
            print("------------------------------\n")

    def interactive_login(self):
        """Launches visible browser for real LinkedIn authentication."""
        from connectors.playwright_linkedin import PlaywrightLinkedInConnector
        connector = PlaywrightLinkedInConnector(headless=False)
        success = connector.interactive_login()
        if success:
            print("\n✅ Setup complete! You can now run:")
            print("   python main.py run --real")
        return success

    def check_replies_and_follow_up(self, limit: int = 10):
        """
        Feature 5: 2-Way Conversation & Reply Tracking.
        Inspects recently engaged posts for incoming replies and posts supportive follow-ups.
        """
        header = "🔄 LinkedBot 2-Way Conversation & Reply Tracker"
        if RICH_AVAILABLE:
            console.print(Panel(header, style="bold cyan"))
        else:
            print(f"\n=== {header} ===\n")

        recent_comments = self.analytics.get_recent_commented_posts(limit=limit, mode=self.active_mode)
        if not recent_comments:
            print(f"ℹ️ No previously commented posts found in analytics database for {self.active_mode} mode.")
            return

        print(f"📋 Scanning {len(recent_comments)} recently engaged posts for incoming replies...")

        replies_sent = 0
        for entry in recent_comments:
            post_id = entry.get("target_id")
            original_comment = entry.get("content", "")

            # Filter out mock IDs in real mode
            if self.active_mode == "REAL" and (post_id.startswith("urn:li:post:mock") or post_id.startswith("urn:li:post:10")):
                logger.info(f"⏭️ Skipping mock test post [{post_id}] in Real LinkedIn mode.")
                continue

            # Ephemeral session card check in REAL mode: skip before calling LLM
            if self.active_mode == "REAL" and post_id.startswith("lb_post_"):
                if hasattr(self.connector, "is_card_visible") and not self.connector.is_card_visible(post_id):
                    print(f"   ℹ️ [SKIPPED] Card [{post_id}] was from an earlier browser session (not visible in current feed).")
                    continue

            if hasattr(self.connector, "reply_to_comment"):
                reply_text = self.generator.generate_thread_reply(
                    original_comment=original_comment,
                    author_reply="Thank you! Spot on regarding least privilege enforcement.",
                    author_name="Colleague"
                )
                res = self.connector.reply_to_comment(post_id, reply_text)
                if res.get("status") == "success":
                    replies_sent += 1
                    self.analytics.record_action("thread_reply", post_id, reply_text, 94.0, mode=self.active_mode)
                    print(f"   💬 [REPLY SENT] Continued dialogue on [{post_id}]:\n      \"{reply_text}\"")
                elif res.get("status") == "skipped":
                    print(f"   ℹ️ [SKIPPED] {res.get('message', 'Post skipped.')}")
                else:
                    print(f"   ⚠️ Could not reply to [{post_id}]: {res.get('message', 'unknown error')}")

        print(f"\n✅ Reply tracking cycle complete: {replies_sent} follow-up replies posted.\n")

    def generate_carousel(self, topic: Optional[str] = None, from_bank_id: Optional[str] = None, publish: bool = False):
        """
        Feature 6: AI Carousel (PDF Slide) Generator.
        Converts thought leadership content into a sleek 5-slide PDF document for LinkedIn.
        """
        from core.carousel_generator import CarouselGenerator

        selected_topic = topic or "IAM Role Sprawl & Cloud Security Inaction"
        category = "Cloud Security"

        if from_bank_id:
            bank_item = self.content_bank.get_by_id(from_bank_id)
            if bank_item:
                selected_topic = bank_item.get("topic", selected_topic)
                category = bank_item.get("sub_domain", category)
                print(f"\n📚 Loaded topic from Content Bank [{from_bank_id}]: '{selected_topic}'")

        print(f"\n🎨 Designing 5-Slide PDF Carousel on: '{selected_topic}'...")
        generator = CarouselGenerator()
        pdf_path = generator.generate_carousel_from_topic(
            topic=selected_topic,
            category=category,
            author_name="Akhil Binu"
        )

        header = f"🎉 Generated 5-Slide Document Carousel: {pdf_path.name}"
        if RICH_AVAILABLE:
            console.print(Panel(f"File: {pdf_path}\nPages: 5 (800x1000pt Portrait)\nTopic: {selected_topic}", title=header, style="bold green"))
        else:
            print(f"=== {header} ===\nSaved to: {pdf_path}")

        if publish:
            allowed, reason = self.rate_limiter.can_perform("posts")
            if not allowed:
                print(f"⚠️ Post publishing rate limit reached: {reason}")
                return
            draft_text = f"Mastering {selected_topic} in modern engineering environments.\n\nSwipe through the 5-slide practical breakdown below ➔\n\n#cybersecurity #cloudsecurity #devops"
            res = self.connector.create_post(draft_text, media_attachment=str(pdf_path))
            if res.get("status") == "success":
                self.rate_limiter.record_action("posts")
                self.analytics.record_action("posts", f"carousel_{selected_topic[:20]}", draft_text, 95.0)
                print("🎉 Carousel published directly to your LinkedIn profile!")
            else:
                print(f"⚠️ Could not publish carousel post: {res.get('message')}")

    def start_schedule(self, interval_hours: float, max_iterations: Optional[int] = None):
        """Runs the continuous scheduler loop."""
        scheduler = AutonomousScheduler(interval_hours=interval_hours)
        scheduler.start_loop(task_fn=self.run_engagement_cycle, max_iterations=max_iterations)

def main():
    parser = argparse.ArgumentParser(description="LinkedBot: Autonomous Cybersecurity LinkedIn Growth Agent")
    subparsers = parser.add_subparsers(dest="command")

    # Command: login
    subparsers.add_parser("login", help="Open a real browser to log into your actual LinkedIn account (1-time setup)")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Run autonomous feed scan & engagement loop")
    run_parser.add_argument("--real", action="store_true", help="Use real LinkedIn browser automation")
    run_parser.add_argument("--target-comments", type=int, default=15, help="Minimum number of posts to comment on (default: 15)")
    run_parser.add_argument("--target-likes", type=int, default=20, help="Minimum number of posts to like on scroll (default: 20)")
    run_parser.add_argument("--max-scrolls", type=int, default=100, help="Maximum scrolls to discover posts (default: 100)")
    run_parser.add_argument("--search", type=str, default=None, help="Targeted hashtag or keyword search (e.g. '#cybersecurity')")
    run_parser.add_argument("--sort-by", type=str, default="date_posted", choices=["date_posted", "relevance"], help="Search sort order (default: date_posted)")
    run_parser.add_argument("--connect", action="store_true", help="Send warm connection request after commenting")
    run_parser.add_argument("--reset-limits", action="store_true", help="Reset rate limit counters before running")

    # Command: reset-limits
    subparsers.add_parser("reset-limits", help="Reset all rate limit counters and cooldowns")

    # Command: post
    post_parser = subparsers.add_parser("post", help="Draft and schedule a thought-leadership post")
    post_parser.add_argument("--topic", type=str, help="Topic for the post", default=None)
    post_parser.add_argument("--from-bank", type=str, help="Post ID from content bank", default=None)
    post_parser.add_argument("--publish", action="store_true", help="Publish directly without HITL staging")
    post_parser.add_argument("--real", action="store_true", help="Publish to your real LinkedIn profile")

    # Command: carousel
    carousel_parser = subparsers.add_parser("carousel", help="Generate high-authority 5-slide PDF carousel document")
    carousel_parser.add_argument("--topic", type=str, help="Custom topic for the carousel", default=None)
    carousel_parser.add_argument("--from-bank", type=str, help="Content bank item ID", default=None)
    carousel_parser.add_argument("--publish", action="store_true", help="Publish carousel directly to LinkedIn")
    carousel_parser.add_argument("--real", action="store_true", help="Publish to your real LinkedIn profile")

    # Command: replies
    replies_parser = subparsers.add_parser("replies", help="Check engaged posts for replies and post follow-ups")
    replies_parser.add_argument("--limit", type=int, default=10, help="Number of recent posts to check (default: 10)")
    replies_parser.add_argument("--real", action="store_true", help="Publish to your real LinkedIn profile")

    # Command: bank
    subparsers.add_parser("bank", help="Browse pre-vetted cybersecurity thought leadership posts")

    # Command: queue
    subparsers.add_parser("queue", help="Review and approve/reject pending HITL drafts")

    # Command: status
    subparsers.add_parser("status", help="Show rate limit and queue status")

    # Command: analytics
    subparsers.add_parser("analytics", help="Show SQLite analytics and performance metrics")

    # Command: schedule
    sched_parser = subparsers.add_parser("schedule", help="Run recurring scheduler loop")
    sched_parser.add_argument("--interval-hours", type=float, default=4.0, help="Hours between cycles (default: 4.0)")
    sched_parser.add_argument("--iterations", type=int, default=None, help="Stop after N cycles (default: infinite)")

    # Command: web
    web_parser = subparsers.add_parser("web", help="Launch the LinkedBot Web Command Center")
    web_parser.add_argument("--port", type=int, default=8000, help="Web server port (default: 8000)")
    web_parser.add_argument("--host", type=str, default="127.0.0.1", help="Host address (default: 127.0.0.1)")

    # Command: test-cooldown
    subparsers.add_parser("test-cooldown", help="Trigger a simulated 60-minute rate limit cooldown")

    # Command: menu
    subparsers.add_parser("menu", help="Launch interactive feature menu [1 to 6]")

    args = parser.parse_args()

    # Launch interactive menu if no command or 'menu' is specified
    if args.command in ["menu", None]:
        from menu import run_menu
        run_menu()
        return
    
    # Check if --real mode requested
    is_real = getattr(args, "real", False)
    mode_override = "REAL" if is_real else None
    bot = LinkedBotAgent(override_mode=mode_override)

    if getattr(args, "reset_limits", False) or args.command == "reset-limits":
        bot.rate_limiter.reset()
        print("🔄 Rate limit quotas and cooldowns have been reset.")
        if args.command == "reset-limits":
            return

    try:
        if args.command == "login":
            bot.interactive_login()
        elif args.command == "run":
            target_comments = getattr(args, "target_comments", 15)
            target_likes = getattr(args, "target_likes", 20)
            max_s = getattr(args, "max_scrolls", 100)
            s_query = getattr(args, "search", None)
            s_order = getattr(args, "sort_by", "date_posted")
            do_connect = getattr(args, "connect", False)
            bot.run_engagement_cycle(
                target_comments=target_comments,
                target_likes=target_likes,
                max_scrolls=max_s,
                search_query=s_query,
                sort_by=s_order,
                auto_connect=do_connect
            )
        elif args.command == "post":
            bot.publish_or_draft_post(topic=args.topic, from_bank_id=args.from_bank, direct_publish=args.publish)
        elif args.command == "carousel":
            bot.generate_carousel(topic=args.topic, from_bank_id=args.from_bank, publish=args.publish)
        elif args.command == "replies":
            bot.check_replies_and_follow_up(limit=getattr(args, "limit", 10))
        elif args.command == "bank":
            bot.browse_content_bank()
        elif args.command == "queue":
            bot.review_hitl_queue()
        elif args.command == "status":
            bot.print_status()
        elif args.command == "analytics":
            bot.print_analytics()
        elif args.command == "schedule":
            bot.start_schedule(interval_hours=args.interval_hours, max_iterations=args.iterations)
        elif args.command == "web":
            import uvicorn
            print(f"\n🌐 Starting LinkedBot Web Command Center at http://{args.host}:{args.port}")
            uvicorn.run("web.server:app", host=args.host, port=args.port, reload=False)
        elif args.command == "test-cooldown":
            bot.rate_limiter.trigger_rate_limit_backoff("Simulated test 429 trigger")
            bot.print_status()
        elif args.command == "menu" or not args.command:
            bot.close()
            from menu import run_menu
            run_menu()
        else:
            parser.print_help()
    finally:
        bot.close()

if __name__ == "__main__":
    main()
