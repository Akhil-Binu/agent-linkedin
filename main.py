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
        active_mode = override_mode or self.config.linkedin_mode
        self.rate_limiter = RateLimiter(self.config.safety.rate_limits)
        self.evaluator = PostEvaluator(self.config)
        self.generator = ContentGenerator(self.config)
        self.hitl = HITLManager(self.config)
        self.analytics = AnalyticsTracker()
        self.content_bank = ContentBank()
        self.connector = get_linkedin_connector(active_mode)

    def close(self):
        """Closes any open browser connectors."""
        if hasattr(self.connector, "close"):
            try:
                self.connector.close()
            except Exception:
                pass

    def run_engagement_cycle(self):
        """Executes a complete scan & engage run."""
        header = f"🚀 LinkedBot Autonomous Engagement Loop [{self.config.domain.upper()}]"
        if RICH_AVAILABLE:
            console.print(Panel(header, style="bold cyan"))
        else:
            print(f"\n=== {header} ===\n")

        # 1. Check Rate Limit Safety Backoff
        can_like, like_msg = self.rate_limiter.can_perform("likes")
        can_comment, comment_msg = self.rate_limiter.can_perform("comments")

        if not can_like and not can_comment:
            logger.warning(f"Engagement paused: {like_msg} | {comment_msg}")
            return

        # 2. Ingest Feed
        feed = self.connector.get_feed(keywords=self.config.target_keywords)
        print(f"📡 Scanned {len(feed)} candidate posts from industry feed.\n")

        for post in feed:
            post_id = post.get("post_id", "unknown")
            author = post.get("author", {})
            content = post.get("content", "")

            print(f"--------------------------------------------------------")
            print(f"🔍 Post: {post_id} | Author: {author.get('name')} ({author.get('headline')})")
            print(f"   Snippet: \"{content[:90]}...\"")

            # 3. Analyze Post
            eval_result = self.evaluator.analyze_post(post_id, content, author)
            print(f"   -> Relevance: {eval_result.relevance_score * 100:.0f}% | Sentiment: {eval_result.sentiment} | Credibility: {eval_result.author_credibility}")
            print(f"   -> Confidence: {eval_result.confidence_score}%")

            if eval_result.flags:
                print(f"   -> Flags: {', '.join(eval_result.flags)}")

            # Record in SQLite Analytics
            self.analytics.record_evaluation(
                post_id=post_id,
                author=author,
                snippet=content,
                relevance=eval_result.relevance_score,
                sentiment=eval_result.sentiment,
                credibility=eval_result.author_credibility,
                should_like=eval_result.should_like,
                should_comment=eval_result.should_comment,
                confidence=eval_result.confidence_score
            )

            # 4. Handle Liking
            if eval_result.should_like:
                allowed, reason = self.rate_limiter.can_perform("likes")
                if allowed:
                    res = self.connector.like_post(post_id)
                    if res.get("error_code") == 429:
                        self.rate_limiter.trigger_rate_limit_backoff("LinkedIn API 429 received on like")
                        break
                    elif res.get("status") == "success":
                        self.rate_limiter.record_action("likes")
                        self.analytics.record_action("likes", post_id, "Liked high-signal post", eval_result.confidence_score)
                        print(f"   👍 [ACTION] Liked post ({eval_result.like_reason})")
                else:
                    print(f"   ⚠️ Like skipped: {reason}")
            else:
                print(f"   ⏭️ Like skipped: {eval_result.like_reason}")

            # 5. Handle Commenting
            if eval_result.should_comment:
                comment, confidence, violations = self.generator.generate_comment(
                    content, author, eval_result.suggested_angle
                )
                print(f"\n   💬 Proposed Comment (Confidence: {confidence}%):")
                print(f"      \"{comment}\"")

                if violations:
                    print(f"      Tone Warnings: {violations}")

                # HITL Check: < 85% or any policy violations routes to human review
                if confidence < self.config.hitl_threshold or violations:
                    print(f"   ⏳ [HITL ROUTING] Confidence ({confidence}%) < threshold ({self.config.hitl_threshold}%). Staged in HITL queue.")
                    self.hitl.enqueue(HITLItem(
                        action_type="comment",
                        target_id=post_id,
                        target_author=author.get("name"),
                        original_content=content[:200],
                        draft_content=comment,
                        confidence_score=confidence,
                        violations=violations,
                        reason="Confidence score below threshold or flagged for tone check"
                    ))
                else:
                    allowed, reason = self.rate_limiter.can_perform("comments")
                    if allowed:
                        res = self.connector.comment_post(post_id, comment)
                        if res.get("error_code") == 429:
                            self.rate_limiter.trigger_rate_limit_backoff("LinkedIn API 429 received on comment")
                            break
                        elif res.get("status") == "success":
                            self.rate_limiter.record_action("comments")
                            self.analytics.record_action("comments", post_id, comment, confidence)
                            print(f"   ✅ [ACTION] Comment published directly.")
                    else:
                        print(f"   ⚠️ Comment skipped: {reason}")
            else:
                print(f"   ⏭️ Comment skipped: {eval_result.comment_reason}")

        print("\n========================================================")
        print("✅ Engagement cycle completed successfully.")
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
    run_parser.add_argument("--reset-limits", action="store_true", help="Reset rate limit counters before running")

    # Command: reset-limits
    subparsers.add_parser("reset-limits", help="Reset all rate limit counters and cooldowns")

    # Command: post
    post_parser = subparsers.add_parser("post", help="Draft and schedule a thought-leadership post")
    post_parser.add_argument("--topic", type=str, help="Topic for the post", default=None)
    post_parser.add_argument("--from-bank", type=str, help="Post ID from content bank", default=None)
    post_parser.add_argument("--publish", action="store_true", help="Publish directly without HITL staging")
    post_parser.add_argument("--real", action="store_true", help="Publish to your real LinkedIn profile")

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

    args = parser.parse_args()
    
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
            bot.run_engagement_cycle()
        elif args.command == "post":
            bot.publish_or_draft_post(topic=args.topic, from_bank_id=args.from_bank, direct_publish=args.publish)
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
        else:
            parser.print_help()
    finally:
        bot.close()

if __name__ == "__main__":
    main()
