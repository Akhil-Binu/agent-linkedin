import os
import time
import random
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from playwright.sync_api import sync_playwright, Page, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from connectors.base import LinkedInConnectorBase

logger = logging.getLogger("LinkedBot.PlaywrightConnector")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SESSION_DIR = DATA_DIR / "linkedin_browser_session"

class PlaywrightLinkedInConnector(LinkedInConnectorBase):
    """
    Real-world autonomous LinkedIn agent connector using a persistent browser context.
    Interacts directly with linkedin.com using realistic human behavior,
    DOM selectors, typing jitter, and persistent session storage.
    """
    def __init__(self, headless: bool = False):
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright is not installed. Run 'pip install playwright' and 'playwright install chromium'.")

        self.headless = headless
        self.user_data_dir = SESSION_DIR
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def _ensure_browser(self):
        """Initializes or restores the persistent browser context."""
        if self.page and not self.page.is_closed():
            return

        self.playwright = sync_playwright().start()
        # Launch persistent context to preserve cookies, session, local storage
        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.user_data_dir),
            headless=self.headless,
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized"
            ]
        )
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        self.page.set_default_timeout(20000)

    def close(self):
        """Closes browser context."""
        try:
            if self.context:
                self.context.close()
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass
        self.page = None
        self.context = None
        self.playwright = None

    def _human_delay(self, min_sec: float = 2.0, max_sec: float = 5.0):
        """Simulates human reaction time."""
        sleep_dur = round(random.uniform(min_sec, max_sec), 2)
        time.sleep(sleep_dur)

    def _type_human(self, selector: str, text: str):
        """Types text character by character with organic timing jitter."""
        self.page.click(selector)
        for char in text:
            self.page.keyboard.type(char)
            # 20ms to 70ms per character jitter
            time.sleep(random.uniform(0.02, 0.07))
            if char in [".", "\n", "!"]:
                time.sleep(random.uniform(0.2, 0.5))

    def interactive_login(self) -> bool:
        """
        Launches a visible browser window allowing the user to log in manually once
        (handling 2FA, OTP, email verification). Saves session permanently.
        """
        logger.info("Starting interactive login session. Please log in on the browser window...")
        self.headless = False
        self._ensure_browser()

        self.page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
        print("\n" + "="*60)
        print("🔑 ACTION REQUIRED: LinkedIn Login Window Opened")
        print("Please log into your real LinkedIn account in the browser.")
        print("The agent will automatically detect when you reach the feed.")
        print("="*60 + "\n")

        # Wait up to 5 minutes for user to reach feed
        start_time = time.time()
        logged_in = False
        while time.time() - start_time < 300:
            current_url = self.page.url
            if "/feed" in current_url:
                logged_in = True
                break
            time.sleep(2)

        if logged_in:
            print("\n🎉 Login verified! Session stored permanently in 'data/linkedin_browser_session'.")
            self._human_delay(3, 5)
            self.close()
            return True
        else:
            print("\n❌ Login timed out after 5 minutes.")
            self.close()
            return False

    def is_logged_in(self) -> bool:
        """Checks if active session exists without prompt."""
        self._ensure_browser()
        try:
            self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
            self._human_delay(2, 4)
            return "/feed" in self.page.url
        except Exception:
            return False

    def get_feed(self, keywords: List[str], target_profiles: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Extracts real live posts from the user's authentic LinkedIn feed.
        """
        self._ensure_browser()
        posts = []
        try:
            logger.info("Opening live LinkedIn feed...")
            self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
            self._human_delay(3, 6)

            # Check if login required
            if "/login" in self.page.url or "/checkpoint" in self.page.url:
                logger.error("Session expired or checkpoint hit. Run 'python main.py login' to re-authenticate.")
                return []

            # Scroll down slowly to load updates
            for _ in range(3):
                self.page.mouse.wheel(0, random.randint(600, 1000))
                self._human_delay(2, 3)

            # Try to click 'see more' buttons on truncated posts
            see_mores = self.page.query_selector_all("button:has-text('see more'), button:has-text('…see more')")
            for btn in see_mores[:4]:
                try:
                    btn.click(timeout=1000)
                except Exception:
                    pass

            # Find post containers
            containers = self.page.query_selector_all("div.feed-shared-update-v2, div[data-urn]")
            logger.info(f"Detected {len(containers)} real post containers on feed.")

            for i, c in enumerate(containers[:10]):
                try:
                    # Post URN / ID
                    urn = c.get_attribute("data-urn") or f"urn:li:feed_item:{i+1}"

                    # Author Name
                    author_elem = c.query_selector(
                        ".update-components-actor__name, .feed-shared-actor__name, span[dir='ltr'] span"
                    )
                    author_name = author_elem.inner_text().strip() if author_elem else "LinkedIn Professional"

                    # Author Headline
                    headline_elem = c.query_selector(
                        ".update-components-actor__description, .feed-shared-actor__description, .update-components-actor__sub-description"
                    )
                    author_headline = headline_elem.inner_text().strip() if headline_elem else ""

                    # Post text content
                    text_elem = c.query_selector(
                        ".feed-shared-update-v2__description, .update-components-text, div.feed-shared-inline-show-more-text"
                    )
                    content = text_elem.inner_text().strip() if text_elem else ""

                    if content and len(content) > 30:
                        posts.append({
                            "post_id": urn,
                            "author": {
                                "name": author_name,
                                "headline": author_headline,
                                "profile_url": "https://www.linkedin.com"
                            },
                            "content": content,
                            "created_at": time.time(),
                            "_element_index": i
                        })
                except Exception as e:
                    logger.debug(f"Could not parse container {i}: {e}")

        except Exception as e:
            logger.error(f"Error reading live feed: {e}")

        return posts

    def like_post(self, post_id: str) -> Dict[str, Any]:
        """
        Locates the real Like button for the post and executes a natural click.
        """
        self._ensure_browser()
        try:
            logger.info(f"[RealLinkedIn] Locating Like button for {post_id}...")

            # Locate container with matching urn
            container = self.page.query_selector(f"div[data-urn='{post_id}']")
            if not container:
                # Fallback to general containers
                container = self.page

            # Find Like button
            like_button = container.query_selector(
                "button.react-button__trigger, button[aria-label*='React Like'], button[aria-label*='Like']"
            )
            if not like_button:
                return {"status": "error", "message": "Like button not found"}

            # Check if already liked
            aria_pressed = like_button.get_attribute("aria-pressed")
            if aria_pressed == "true":
                logger.info("Post was already liked. Skipping duplicate click.")
                return {"status": "success", "message": "Already liked"}

            # Scroll into view & human click
            like_button.scroll_into_view_if_needed()
            self._human_delay(1.5, 3.0)
            like_button.click()
            self._human_delay(2.0, 4.0)

            logger.info(f"👍 [REAL ACTION] Successfully liked real LinkedIn post: {post_id}")
            return {"status": "success", "post_id": post_id}

        except Exception as e:
            logger.error(f"Failed to like post {post_id}: {e}")
            return {"status": "error", "message": str(e)}

    def comment_post(self, post_id: str, comment_text: str) -> Dict[str, Any]:
        """
        Opens comment box, types the substantive comment with keystroke jitter, and submits.
        """
        self._ensure_browser()
        try:
            logger.info(f"[RealLinkedIn] Submitting comment to {post_id}...")
            container = self.page.query_selector(f"div[data-urn='{post_id}']") or self.page

            # 1. Click Comment button to open box
            comment_btn = container.query_selector(
                "button.comment-button, button[aria-label*='Comment'], button.social-actions__button"
            )
            if comment_btn:
                comment_btn.scroll_into_view_if_needed()
                self._human_delay(1.0, 2.0)
                comment_btn.click()
                self._human_delay(1.5, 3.0)

            # 2. Locate editor
            editor = container.query_selector(
                "div.ql-editor[contenteditable='true'], div[role='textbox']"
            )
            if not editor:
                return {"status": "error", "message": "Comment input editor not found"}

            editor.click()
            self._human_delay(1.0, 2.0)

            # 3. Type comment with human keystroke jitter
            for char in comment_text:
                self.page.keyboard.type(char)
                time.sleep(random.uniform(0.015, 0.05))

            self._human_delay(2.0, 4.0)

            # 4. Click Submit
            submit_btn = container.query_selector(
                "button.comments-comment-box__submit-button, button:has-text('Post')"
            )
            if submit_btn:
                submit_btn.click()
                self._human_delay(3.0, 5.0)
                logger.info(f"💬 [REAL ACTION] Published real comment to LinkedIn post {post_id}")
                return {"status": "success", "comment": comment_text}
            else:
                return {"status": "error", "message": "Comment submit button not found"}

        except Exception as e:
            logger.error(f"Failed to comment on {post_id}: {e}")
            return {"status": "error", "message": str(e)}

    def create_post(self, draft_text: str, media_attachment: Optional[str] = None) -> Dict[str, Any]:
        """
        Publishes a real thought-leadership post to the user's authentic LinkedIn profile.
        """
        self._ensure_browser()
        try:
            logger.info("[RealLinkedIn] Navigating to feed to publish post...")
            self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
            self._human_delay(3.0, 5.0)

            # Click "Start a post"
            start_post_btn = self.page.query_selector(
                "button.share-box-feed-entry__trigger, button:has-text('Start a post')"
            )
            if not start_post_btn:
                return {"status": "error", "message": "Could not locate 'Start a post' button"}

            start_post_btn.click()
            self._human_delay(2.0, 3.5)

            # Locate modal editor
            editor = self.page.wait_for_selector(
                "div.share-creation-state__text-editor div.ql-editor, div.ql-editor[contenteditable='true']",
                timeout=10000
            )
            if not editor:
                return {"status": "error", "message": "Post editor modal not found"}

            editor.click()
            self._human_delay(1.0, 2.0)

            # Split paragraphs and type with human jitter
            paragraphs = draft_text.split("\n\n")
            for i, p in enumerate(paragraphs):
                for char in p:
                    self.page.keyboard.type(char)
                    time.sleep(random.uniform(0.015, 0.045))
                if i < len(paragraphs) - 1:
                    self.page.keyboard.press("Enter")
                    self.page.keyboard.press("Enter")
                    self._human_delay(0.5, 1.2)

            self._human_delay(3.0, 6.0)

            # Click final "Post" button
            post_btn = self.page.wait_for_selector(
                "button.share-actions__primary-action, button:has-text('Post')",
                timeout=10000
            )
            if post_btn:
                post_btn.click()
                self._human_delay(4.0, 8.0)
                logger.info("🎉 [REAL ACTION] Published real thought leadership post to your LinkedIn profile!")
                return {"status": "success", "message": "Post published"}
            else:
                return {"status": "error", "message": "Final Post button not found"}

        except Exception as e:
            logger.error(f"Failed to publish post: {e}")
            return {"status": "error", "message": str(e)}
