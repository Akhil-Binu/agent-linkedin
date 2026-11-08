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
    def __init__(self, headless: bool = True):
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
        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.user_data_dir),
            headless=self.headless,
            viewport={"width": 1366, "height": 850},
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

    def _human_delay(self, min_sec: float = 2.0, max_sec: float = 4.0):
        """Simulates human reaction time."""
        sleep_dur = round(random.uniform(min_sec, max_sec), 2)
        time.sleep(sleep_dur)

    def interactive_login(self) -> bool:
        """
        Launches a visible browser window allowing the user to log in manually once.
        Saves session permanently in data/linkedin_browser_session.
        """
        logger.info("Opening visible LinkedIn login window...")
        self.headless = False
        self._ensure_browser()

        self.page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
        print("\n" + "="*60)
        print("🔑 ACTION REQUIRED: LinkedIn Login Window Opened")
        print("Please log into your real LinkedIn account in the browser window.")
        print("LinkedBot will automatically detect when you reach the feed.")
        print("="*60 + "\n")

        start_time = time.time()
        logged_in = False
        while time.time() - start_time < 300:
            current_url = self.page.url
            if "/feed" in current_url:
                logged_in = True
                break
            time.sleep(2)

        if logged_in:
            print("\n🎉 Authentication verified! Session permanently stored.")
            self._human_delay(3, 5)
            self.close()
            return True
        else:
            print("\n❌ Login timed out after 5 minutes.")
            self.close()
            return False

    def is_logged_in(self) -> bool:
        """Checks if active session exists on feed."""
        self._ensure_browser()
        try:
            self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
            self._human_delay(2, 3)
            return "/feed" in self.page.url
        except Exception:
            return False

    def get_feed(self, keywords: List[str], target_profiles: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Extracts real live posts from the user's authentic LinkedIn feed
        using modern LinkedIn component and accessibility structures.
        """
        self._ensure_browser()
        posts = []
        try:
            logger.info("Navigating to live LinkedIn feed...")
            self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
            self._human_delay(3, 5)

            # Check if logged in
            if "/login" in self.page.url or "/checkpoint" in self.page.url:
                logger.error("Session expired. Run 'python main.py login' to re-authenticate.")
                return []

            # Organic mouse wheel scrolls to trigger lazy loading
            for _ in range(3):
                self.page.mouse.wheel(0, random.randint(700, 1100))
                self._human_delay(1.5, 2.5)

            # Execute modern DOM post extraction directly in page context
            extracted = self.page.evaluate('''() => {
                const results = [];
                // Posts in modern LinkedIn are labeled via control buttons:
                const menuButtons = Array.from(document.querySelectorAll("button[aria-label*='Open control menu for post by']"));

                for (let i = 0; i < menuButtons.length; i++) {
                    const btn = menuButtons[i];
                    const label = btn.getAttribute("aria-label") || "";
                    const author = label.replace("Open control menu for post by ", "").trim();

                    // Walk up to find the closest card container with reaction buttons
                    let container = btn.parentElement;
                    let foundCard = null;
                    for (let step = 0; step < 10; step++) {
                        if (!container) break;
                        const hasReact = container.querySelector("button[aria-label*='React'], button[aria-label*='Reaction'], button[aria-label='Comment']");
                        if (hasReact) {
                            foundCard = container;
                            break;
                        }
                        container = container.parentElement;
                    }

                    if (foundCard) {
                        // Extract text nodes
                        const textElements = Array.from(foundCard.querySelectorAll("p, span[dir='ltr']"));
                        const fullText = textElements.map(el => el.innerText.trim()).filter(txt => txt.length > 20).join("\\n");

                        // Extract headline
                        const spans = Array.from(foundCard.querySelectorAll("span"));
                        let headline = "";
                        for (const s of spans) {
                            const txt = s.innerText.trim();
                            if (txt.length > 15 && txt.length < 130 && !txt.includes(author) && !txt.includes("follower") && !txt.includes("ago") && !txt.includes("commented") && !txt.includes("like this")) {
                                headline = txt;
                                break;
                            }
                        }

                        // Try finding post urn in links
                        let postUrn = "";
                        const linkWithUrn = foundCard.querySelector("a[href*='/feed/update/urn:li:activity:']");
                        if (linkWithUrn) {
                            const m = linkWithUrn.getAttribute("href").match(/urn:li:activity:[0-9]+/);
                            if (m) postUrn = m[0];
                        }
                        if (!postUrn) {
                            postUrn = `urn:li:live_post:${i+1}`;
                        }

                        results.push({
                            post_id: postUrn,
                            author_name: author,
                            author_headline: headline,
                            content: fullText,
                            index: i
                        });
                    }
                }
                return results;
            }''')

            logger.info(f"Successfully extracted {len(extracted)} real posts from your LinkedIn feed.")

            for item in extracted:
                content = item.get("content", "").strip()
                if content and len(content) > 30:
                    posts.append({
                        "post_id": item.get("post_id"),
                        "author": {
                            "name": item.get("author_name"),
                            "headline": item.get("author_headline") or "Cybersecurity Practitioner",
                            "profile_url": "https://www.linkedin.com"
                        },
                        "content": content,
                        "created_at": time.time(),
                        "_menu_index": item.get("index")
                    })

        except Exception as e:
            logger.error(f"Error reading live feed: {e}")

        return posts

    def like_post(self, post_id: str) -> Dict[str, Any]:
        """
        Locates the Like/Reaction button on the specified real post and clicks it.
        """
        self._ensure_browser()
        try:
            logger.info(f"[RealLinkedIn] Executing Like on {post_id}...")

            # Locate post container by searching for link with URN or by control button
            clicked = self.page.evaluate('''(targetId) => {
                // Try finding by exact urn link
                let container = null;
                const link = document.querySelector(`a[href*='${targetId}']`);
                if (link) {
                    let cur = link.parentElement;
                    for (let i = 0; i < 10; i++) {
                        if (!cur) break;
                        if (cur.querySelector("button[aria-label*='React'], button[aria-label*='Reaction']")) {
                            container = cur;
                            break;
                        }
                        cur = cur.parentElement;
                    }
                }

                if (!container) {
                    // Fallback to first post with reaction button
                    container = document.querySelector("button[aria-label*='React'], button[aria-label*='Reaction']")?.parentElement?.parentElement;
                }

                if (container) {
                    const likeBtn = container.querySelector("button[aria-label*='React'], button[aria-label*='Reaction']");
                    if (likeBtn) {
                        const isLiked = likeBtn.getAttribute("aria-pressed") === "true";
                        if (!isLiked) {
                            likeBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            likeBtn.click();
                            return { success: true, status: "liked" };
                        } else {
                            return { success: true, status: "already_liked" };
                        }
                    }
                }
                return { success: false, status: "not_found" };
            }''', post_id)

            if clicked.get("success"):
                self._human_delay(2.0, 4.0)
                logger.info(f"👍 [REAL ACTION] Successfully liked real post: {post_id} ({clicked.get('status')})")
                return {"status": "success", "post_id": post_id}
            else:
                return {"status": "error", "message": "Reaction button not found"}

        except Exception as e:
            logger.error(f"Failed to like post: {e}")
            return {"status": "error", "message": str(e)}

    def comment_post(self, post_id: str, comment_text: str) -> Dict[str, Any]:
        """
        Opens the real comment box, types the substantive comment with keystroke jitter, and posts.
        """
        self._ensure_browser()
        try:
            logger.info(f"[RealLinkedIn] Submitting comment to real post {post_id}...")

            # Click the comment button on the card
            opened = self.page.evaluate('''(targetId) => {
                let container = null;
                const link = document.querySelector(`a[href*='${targetId}']`);
                if (link) {
                    let cur = link.parentElement;
                    for (let i = 0; i < 10; i++) {
                        if (!cur) break;
                        if (cur.querySelector("button[aria-label='Comment']")) {
                            container = cur;
                            break;
                        }
                        cur = cur.parentElement;
                    }
                }
                if (!container) {
                    container = document.querySelector("button[aria-label='Comment']")?.parentElement?.parentElement;
                }

                if (container) {
                    const btn = container.querySelector("button[aria-label='Comment']");
                    if (btn) {
                        btn.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        btn.click();
                        return true;
                    }
                }
                return false;
            }''', post_id)

            self._human_delay(2.0, 3.5)

            # Find the active comment box
            editor = self.page.wait_for_selector(
                "div.ql-editor[contenteditable='true'], div[role='textbox'], p[data-placeholder*='comment']",
                timeout=7000
            )
            if not editor:
                return {"status": "error", "message": "Comment input editor not opened"}

            editor.click()
            self._human_delay(0.8, 1.5)

            # Type text character by character with organic human jitter
            for char in comment_text:
                self.page.keyboard.type(char)
                time.sleep(random.uniform(0.015, 0.045))
                if char in [".", ",", "!"]:
                    time.sleep(random.uniform(0.1, 0.25))

            self._human_delay(2.0, 4.0)

            # Submit comment
            submit_btn = self.page.wait_for_selector(
                "button.comments-comment-box__submit-button, button:has-text('Comment')",
                timeout=5000
            )
            if submit_btn:
                submit_btn.click()
                self._human_delay(3.0, 5.0)
                logger.info(f"💬 [REAL ACTION] Published real comment to LinkedIn post {post_id}")
                return {"status": "success", "comment": comment_text}
            else:
                return {"status": "error", "message": "Submit comment button not found"}

        except Exception as e:
            logger.error(f"Failed to post comment: {e}")
            return {"status": "error", "message": str(e)}

    def create_post(self, draft_text: str, media_attachment: Optional[str] = None) -> Dict[str, Any]:
        """
        Publishes a real thought-leadership post to the user's authentic LinkedIn profile.
        """
        self._ensure_browser()
        try:
            logger.info("[RealLinkedIn] Navigating to feed to publish thought leadership post...")
            self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
            self._human_delay(3.0, 5.0)

            # Click "Start a post" button
            start_post_btn = self.page.wait_for_selector(
                "button:has-text('Start a post'), button[aria-label*='Start a post']",
                timeout=10000
            )
            if not start_post_btn:
                return {"status": "error", "message": "Could not locate 'Start a post' button"}

            start_post_btn.click()
            self._human_delay(2.0, 3.5)

            # Locate modal text editor
            editor = self.page.wait_for_selector(
                "div.share-creation-state__text-editor div.ql-editor, div.ql-editor[contenteditable='true'], div[role='textbox']",
                timeout=10000
            )
            if not editor:
                return {"status": "error", "message": "Post editor modal not found"}

            editor.click()
            self._human_delay(1.0, 2.0)

            # Split paragraphs and type with organic human timing
            paragraphs = draft_text.split("\n\n")
            for i, p in enumerate(paragraphs):
                for char in p:
                    self.page.keyboard.type(char)
                    time.sleep(random.uniform(0.015, 0.045))
                if i < len(paragraphs) - 1:
                    self.page.keyboard.press("Enter")
                    self.page.keyboard.press("Enter")
                    self._human_delay(0.5, 1.0)

            self._human_delay(3.0, 5.0)

            # Click final "Post" button
            post_btn = self.page.wait_for_selector(
                "button.share-actions__primary-action, button:has-text('Post')",
                timeout=10000
            )
            if post_btn:
                post_btn.click()
                self._human_delay(4.0, 7.0)
                logger.info("🎉 [REAL ACTION] Published real thought leadership post to your LinkedIn profile!")
                return {"status": "success", "message": "Post published"}
            else:
                return {"status": "error", "message": "Final Post button not found"}

        except Exception as e:
            logger.error(f"Failed to publish post: {e}")
            return {"status": "error", "message": str(e)}
