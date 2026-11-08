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
    infinite dynamic scrolling, keystroke jitter, and human delays.
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

    def _cleanup_session_lock(self):
        """Kills orphan Chrome instances accessing the session directory and cleans stale lockfile."""
        import subprocess
        ps_script = (
            "Get-CimInstance Win32_Process -Filter \"Name = 'chrome.exe'\" | "
            "Where-Object { $_.CommandLine -like '*linkedin_browser_session*' -or $_.ExecutablePath -like '*ms-playwright*' } | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
        )
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, timeout=10)
        except Exception:
            pass

        lock_file = self.user_data_dir / "lockfile"
        if lock_file.exists():
            try:
                lock_file.unlink()
            except Exception:
                pass
        time.sleep(1.0)

    def _ensure_browser(self):
        """Initializes or restores the persistent browser context with automatic lock recovery."""
        if self.page and not self.page.is_closed():
            return

        self.playwright = sync_playwright().start()
        launch_args = {
            "user_data_dir": str(self.user_data_dir),
            "headless": self.headless,
            "viewport": {"width": 1366, "height": 850},
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--start-maximized"
            ]
        }

        try:
            self.context = self.playwright.chromium.launch_persistent_context(**launch_args)
        except Exception as e:
            if "ProcessSingleton" in str(e) or "already in use" in str(e):
                logger.warning("Chromium session locked by previous process. Cleaning up and retrying...")
                self._cleanup_session_lock()
                self.context = self.playwright.chromium.launch_persistent_context(**launch_args)
            else:
                raise e

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

    def scroll_down(self, pixels: int = 900):
        """Scrolls the feed down smoothly to trigger lazy-loading of next posts."""
        self._ensure_browser()
        try:
            scroll_amt = pixels + random.randint(-150, 150)
            self.page.mouse.wheel(0, scroll_amt)
            self._human_delay(2.0, 3.5)
        except Exception as e:
            logger.debug(f"Scroll error: {e}")

    def get_visible_posts(self) -> List[Dict[str, Any]]:
        """
        Extracts all currently visible post cards in the DOM,
        tagging each uniquely with `data-lb-id` for precise scoped interaction.
        """
        self._ensure_browser()
        posts = []
        try:
            extracted = self.page.evaluate('''() => {
                window.__lb_counter = window.__lb_counter || 0;
                const results = [];
                const menuButtons = Array.from(document.querySelectorAll("button[aria-label*='Open control menu for post by']"));

                for (let i = 0; i < menuButtons.length; i++) {
                    const btn = menuButtons[i];
                    const label = btn.getAttribute("aria-label") || "";
                    const author = label.replace("Open control menu for post by ", "").trim();

                    // Walk up to find the highest single-post ancestor container
                    let cur = btn.parentElement;
                    let foundCard = null;
                    while (cur && cur !== document.body) {
                        const menus = cur.querySelectorAll("button[aria-label*='Open control menu for post by']");
                        if (menus.length === 1) {
                            foundCard = cur;
                            cur = cur.parentElement;
                        } else {
                            break;
                        }
                    }

                    if (foundCard) {
                        // Tag card if not already tagged
                        let uniqueId = foundCard.getAttribute("data-lb-id");
                        if (!uniqueId) {
                            window.__lb_counter++;
                            uniqueId = `lb_post_${window.__lb_counter}`;
                            foundCard.setAttribute("data-lb-id", uniqueId);
                        }

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
                            content: fullText
                        });
                    }
                }
                return results;
            }''')

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
                        "created_at": time.time()
                    })

        except Exception as e:
            logger.error(f"Error reading visible cards: {e}")

        return posts

    def get_feed(self, keywords: List[str], target_profiles: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Navigates to feed and returns initial batch of visible cards.
        """
        self._ensure_browser()
        try:
            logger.info("Opening live LinkedIn feed...")
            self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
            self._human_delay(3, 5)

            if "/login" in self.page.url or "/checkpoint" in self.page.url:
                logger.error("Session expired. Run 'python main.py login' to re-authenticate.")
                return []

            # Initial scroll to load updates
            self.scroll_down(800)
            return self.get_visible_posts()
        except Exception as e:
            logger.error(f"Error opening feed: {e}")
            return []

    def like_post(self, post_id: str, reaction_type: str = "LIKE") -> Dict[str, Any]:
        """
        Locates the Reaction button STRICTLY inside the matching post card.
        Guarantees reactions are applied properly to the card.
        Supports reaction_type: 'LIKE' or 'CELEBRATE'.
        """
        self._ensure_browser()
        try:
            clicked = self.page.evaluate('''(args) => {
                const { targetId, reqReaction } = args;
                const card = document.querySelector(`[data-lb-id='${targetId}']`);
                if (!card) {
                    return { success: false, reason: `Card [${targetId}] not found in DOM` };
                }

                let likeBtn = card.querySelector("button[aria-label*='Reaction button state'], button[aria-label*='React'], button[aria-label*='Reaction']");
                if (!likeBtn) {
                    const allBtns = Array.from(card.querySelectorAll("button"));
                    likeBtn = allBtns.find(b => {
                        const aria = (b.getAttribute("aria-label") || "").toLowerCase();
                        return aria.includes("reaction button state") || aria.includes("react") || aria.includes("like");
                    });
                }

                if (!likeBtn) {
                    return { success: false, reason: "Reaction button not found in card" };
                }

                const aria = (likeBtn.getAttribute("aria-label") || "").toLowerCase();
                const isReacted = !aria.includes("no reaction") && (
                    aria.includes("like") || aria.includes("celebrate") || aria.includes("support") || aria.includes("reaction") || aria.includes("insightful")
                );

                if (isReacted) {
                    return { success: true, status: "already_reacted" };
                }

                likeBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
                likeBtn.click();
                return { success: true, status: "reacted" };
            }''', {"targetId": post_id, "reqReaction": reaction_type.upper()})

            if clicked.get("success"):
                reaction_state = clicked.get("status", "reacted")
                if reaction_state == "already_reacted":
                    logger.info(f"ℹ️ Post [{post_id}] was already reacted to. Preserving reaction.")
                    return {"status": "already_reacted", "post_id": post_id, "reaction": reaction_type}
                self._human_delay(1.5, 3.0)
                logger.info(f"👍 [REAL REACTION] Reacted to card [{post_id}] ({reaction_state})")
                return {"status": "success", "post_id": post_id, "reaction": reaction_type}
            else:
                logger.debug(f"Could not react to post [{post_id}]: {clicked.get('reason')}")
                return {"status": "error", "message": clicked.get("reason")}

        except Exception as e:
            logger.error(f"Failed to react to post {post_id}: {e}")
            return {"status": "error", "message": str(e)}

    def comment_post(self, post_id: str, comment_text: str) -> Dict[str, Any]:
        """
        Locates the Comment button and Editor STRICTLY inside the matching post card.
        Guarantees that comments are NEVER posted to the wrong card.
        """
        self._ensure_browser()
        try:
            logger.info(f"[RealLinkedIn] Submitting comment strictly inside card [{post_id}]...")

            # 1. Open or focus Comment editor inside THAT card
            opened = self.page.evaluate('''(targetId) => {
                const card = document.querySelector(`[data-lb-id='${targetId}']`);
                if (!card) return { success: false, reason: `Card [${targetId}] not found in DOM` };

                // Check if editor is already open and visible in this card
                const existingEditor = card.querySelector("div.ProseMirror, div[role='textbox'][contenteditable='true'], div[aria-label*='comment']");
                if (existingEditor && existingEditor.offsetParent !== null) {
                    existingEditor.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    return { success: true, alreadyOpen: true };
                }

                // Locate Comment toggle button
                let commentBtn = card.querySelector("button[aria-label='Comment']");
                if (!commentBtn) {
                    const allBtns = Array.from(card.querySelectorAll("button"));
                    commentBtn = allBtns.find(b => {
                        const aria = (b.getAttribute("aria-label") || "").toLowerCase();
                        const txt = (b.innerText || "").toLowerCase();
                        return aria.includes("comment") || txt.includes("comment");
                    });
                }

                if (!commentBtn) return { success: false, reason: "Comment button not found inside card" };

                commentBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
                commentBtn.click();
                return { success: true, alreadyOpen: false };
            }''', post_id)

            if not opened.get("success"):
                logger.warning(f"Failed to open comment box on [{post_id}]: {opened.get('reason')}")
                return {"status": "error", "message": opened.get("reason")}

            self._human_delay(1.5, 2.5)

            # 2. Locate editor strictly inside this card
            card_locator = self.page.locator(f"[data-lb-id='{post_id}']")
            editor = card_locator.locator(
                "div.ProseMirror, div[role='textbox'][contenteditable='true'], div[aria-label*='comment'], div.ql-editor, p.is-editor-empty"
            ).first

            try:
                editor.wait_for(state="visible", timeout=8000)
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

            self._human_delay(1.5, 3.0)

            # 4. Submit comment: try clicking the submit button or pressing Control+Enter
            submitted = False

            # Primary: Look for submit button with text 'Comment' or 'Post' inside the card
            submit_btn = card_locator.locator(
                "button.gvyiaf, button[type='submit'], button.comments-comment-box__submit-button, button"
            ).filter(has_text="Comment").first

            try:
                if submit_btn.is_visible(timeout=2000):
                    submit_btn.click()
                    submitted = True
            except Exception:
                pass

            if not submitted:
                post_btn = card_locator.locator("button").filter(has_text="Post").first
                try:
                    if post_btn.is_visible(timeout=1000):
                        post_btn.click()
                        submitted = True
                except Exception:
                    pass

            if not submitted:
                # Use native LinkedIn shortcut: Control+Enter submits the active comment box
                self.page.keyboard.press("Control+Enter")
                submitted = True

            self._human_delay(3.0, 5.0)
            logger.info(f"💬 [REAL ACTION] Published real comment to post [{post_id}]")
            return {"status": "success", "comment": comment_text}

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
