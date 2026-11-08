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
    Interacts directly with linkedin.com using strictly scoped card DOM selectors,
    keystroke jitter, and human delays.
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
        and attaches a unique DOM identifier (`data-lb-id`) to each card.
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

            # Organic mouse wheel scrolls to trigger feed updates
            for _ in range(3):
                self.page.mouse.wheel(0, random.randint(700, 1100))
                self._human_delay(1.5, 2.5)

            # Execute modern DOM post extraction and tag each card uniquely
            extracted = self.page.evaluate('''() => {
                const results = [];
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
                        // Tag this exact card with a persistent identifier
                        const uniqueId = `lb_post_${i + 1}`;
                        foundCard.setAttribute("data-lb-id", uniqueId);

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

                        results.push({
                            post_id: uniqueId,
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
        Locates the Like button STRICTLY inside the matching post card.
        """
        self._ensure_browser()
        try:
            logger.info(f"[RealLinkedIn] Locating Like button strictly inside card [{post_id}]...")

            clicked = self.page.evaluate('''(targetId) => {
                const card = document.querySelector(`div[data-lb-id='${targetId}']`);
                if (!card) {
                    return { success: false, reason: `Card [${targetId}] not found in DOM` };
                }

                const likeBtn = card.querySelector("button[aria-label*='React'], button[aria-label*='Reaction']");
                if (!likeBtn) {
                    return { success: false, reason: "Like button not found in card" };
                }

                const isLiked = likeBtn.getAttribute("aria-pressed") === "true";
                if (isLiked) {
                    return { success: true, status: "already_liked" };
                }

                likeBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
                likeBtn.click();
                return { success: true, status: "liked" };
            }''', post_id)

            if clicked.get("success"):
                self._human_delay(2.0, 3.5)
                logger.info(f"👍 [REAL ACTION] Successfully liked real post [{post_id}] ({clicked.get('status')})")
                return {"status": "success", "post_id": post_id}
            else:
                logger.warning(f"Could not like post [{post_id}]: {clicked.get('reason')}")
                return {"status": "error", "message": clicked.get("reason")}

        except Exception as e:
            logger.error(f"Failed to like post {post_id}: {e}")
            return {"status": "error", "message": str(e)}

    def comment_post(self, post_id: str, comment_text: str) -> Dict[str, Any]:
        """
        Locates the Comment button and Editor STRICTLY inside the matching post card.
        Guarantees that comments are NEVER posted to the wrong card.
        """
        self._ensure_browser()
        try:
            logger.info(f"[RealLinkedIn] Targeting comment box STRICTLY inside card [{post_id}]...")

            # 1. Click Comment button inside THAT card
            opened = self.page.evaluate('''(targetId) => {
                const card = document.querySelector(`div[data-lb-id='${targetId}']`);
                if (!card) return { success: false, reason: `Card [${targetId}] not found in DOM` };

                const commentBtn = card.querySelector("button[aria-label='Comment']");
                if (!commentBtn) return { success: false, reason: "Comment button not found inside card" };

                commentBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
                commentBtn.click();
                return { success: true };
            }''', post_id)

            if not opened.get("success"):
                logger.warning(f"Failed to open comment box on [{post_id}]: {opened.get('reason')}")
                return {"status": "error", "message": opened.get("reason")}

            self._human_delay(1.5, 2.5)

            # 2. Locate editor strictly inside this card
            card_locator = self.page.locator(f"div[data-lb-id='{post_id}']")
            editor = card_locator.locator("div.ql-editor, div[role='textbox'], p[data-placeholder*='comment']").first

            try:
                editor.wait_for(state="visible", timeout=6000)
            except Exception:
                return {"status": "error", "message": f"Editor inside card [{post_id}] did not become visible"}

            editor.click()
            self._human_delay(0.8, 1.5)

            # 3. Type comment with human keystroke jitter
            for char in comment_text:
                self.page.keyboard.type(char)
                time.sleep(random.uniform(0.015, 0.045))
                if char in [".", ",", "!"]:
                    time.sleep(random.uniform(0.1, 0.25))

            self._human_delay(2.0, 3.5)

            # 4. Click Submit button strictly inside this card
            submit_btn = card_locator.locator("button.comments-comment-box__submit-button, button:has-text('Comment')").first
            try:
                submit_btn.wait_for(state="visible", timeout=4000)
                submit_btn.click()
                self._human_delay(3.0, 5.0)
                logger.info(f"💬 [REAL ACTION] Published real comment to post [{post_id}]")
                return {"status": "success", "comment": comment_text}
            except Exception as e:
                return {"status": "error", "message": f"Could not click submit button in card [{post_id}]: {e}"}

        except Exception as e:
            logger.error(f"Failed to comment on {post_id}: {e}")
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
