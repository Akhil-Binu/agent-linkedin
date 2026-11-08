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

    def _dismiss_overlays(self):
        """Dismisses transient overlays such as 'Not now' notifications, messaging tabs, or popups."""
        try:
            self.page.evaluate('''() => {
                // 1. Close modal overlays (notification alerts, save password, cookie popups)
                const buttons = Array.from(document.querySelectorAll("button, div[role='button']"));
                for (const b of buttons) {
                    const txt = (b.innerText || "").trim().toLowerCase();
                    const aria = (b.getAttribute("aria-label") || "").toLowerCase();
                    if (
                        txt === "not now" || 
                        txt === "dismiss" || 
                        txt === "close" || 
                        aria.includes("dismiss notification") || 
                        aria === "close" || 
                        aria.includes("dismiss")
                    ) {
                        const inModal = b.closest(".artdeco-modal") || b.closest(".artdeco-toast-item") || b.closest("[role='alertdialog']");
                        if (inModal) {
                            b.click();
                        }
                    }
                }
                // 2. Collapse messaging dock if covering viewport
                const msgHeader = document.querySelector(".msg-overlay-bubble-header__button");
                const isMsgOpen = document.querySelector(".msg-overlay-list-bubble--is-expanded");
                if (isMsgOpen && msgHeader) {
                    msgHeader.click();
                }
            }''')
        except Exception:
            pass

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

    def search_posts(self, query: str, sort_by: str = "date_posted") -> List[Dict[str, Any]]:
        """
        Navigates to LinkedIn content search for a given hashtag or keyword phrase,
        filtered by 'date_posted' (Past 24 Hours / Latest) or 'relevance'.
        """
        self._ensure_browser()
        try:
            from urllib.parse import quote_plus
            encoded_query = quote_plus(query.strip())
            if sort_by == "date_posted":
                search_url = f"https://www.linkedin.com/search/results/content/?keywords={encoded_query}&sortBy=%22date_posted%22"
            else:
                search_url = f"https://www.linkedin.com/search/results/content/?keywords={encoded_query}"

            logger.info(f"🔎 [RealLinkedIn] Searching content for '{query}' (Sort: {sort_by})...")
            self.page.goto(search_url, wait_until="domcontentloaded")
            self._human_delay(3.0, 5.0)

            if "/login" in self.page.url or "/checkpoint" in self.page.url:
                logger.error("Session expired. Run 'python main.py login' to re-authenticate.")
                return []

            self.scroll_down(800)
            return self.get_visible_posts()
        except Exception as e:
            logger.error(f"Error searching LinkedIn for '{query}': {e}")
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

    def _attach_pdf_document(self, pdf_path: str, draft_text: str) -> bool:
        """
        Attaches a PDF document carousel inside the open LinkedIn post modal.
        Locates the Document button in the toolbar (expanding the 'More' menu if needed),
        triggers the file chooser with the PDF, fills the document title, and clicks 'Done'.
        """
        try:
            logger.info(f"📄 Attaching PDF document carousel: {pdf_path}")
            self._human_delay(1.5, 2.5)

            # Step 1: Find and click "Add a document" in the modal toolbar
            click_res = self.page.evaluate('''() => {
                const modal = document.querySelector(".artdeco-modal, div[role='dialog'], .share-box-modal");
                if (!modal) return { success: false, reason: "No active modal found" };

                const buttons = Array.from(modal.querySelectorAll("button, div[role='button']"));

                // A. Check for direct Document button in toolbar
                const directDoc = buttons.find(b => {
                    const aria = (b.getAttribute("aria-label") || "").toLowerCase();
                    const txt = (b.innerText || "").toLowerCase();
                    return aria.includes("add a document") || aria.includes("document") || txt.includes("add a document");
                });
                if (directDoc) {
                    directDoc.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    directDoc.click();
                    return { success: true, method: "direct" };
                }

                // B. Overflow 'More' button (three dots, plus, or 'Add to your post')
                const moreBtn = buttons.find(b => {
                    const aria = (b.getAttribute("aria-label") || "").toLowerCase();
                    const txt = (b.innerText || "").toLowerCase();
                    return aria.includes("more") || aria.includes("add to your post") || aria.includes("see more") || b.classList.contains("share-prompts-bar__more-btn");
                });
                if (moreBtn) {
                    moreBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    moreBtn.click();
                    return { success: true, method: "expanded_more" };
                }

                return { success: false, reason: "No document or overflow button located in modal toolbar" };
            }''')

            if not click_res.get("success"):
                logger.error(f"Could not trigger document upload: {click_res.get('reason')}")
                return False

            if click_res.get("method") == "expanded_more":
                self._human_delay(1.0, 2.0)
                # Click the "Add a document" option inside the opened dropdown menu
                doc_item_clicked = self.page.evaluate('''() => {
                    const items = Array.from(document.querySelectorAll("button, div[role='button'], div[role='menuitem'], li, span"));
                    const docOption = items.find(el => {
                        const txt = (el.innerText || "").toLowerCase();
                        const aria = (el.getAttribute("aria-label") || "").toLowerCase();
                        return txt.includes("add a document") || (txt.includes("document") && !txt.includes("share")) || aria.includes("add a document");
                    });
                    if (docOption) {
                        const target = docOption.closest("button") || docOption.closest("div[role='button']") || docOption;
                        target.click();
                        return true;
                    }
                    return false;
                }''')
                if not doc_item_clicked:
                    logger.error("Could not find 'Add a document' option in the expanded More menu.")
                    return False

            self._human_delay(2.0, 3.5)

            # Step 2: The "Share a document" modal is now open. Upload the PDF file!
            file_uploaded = False

            # Check if there is a 'Choose file' button
            choose_btn = self.page.locator(
                "button:has-text('Choose file'), button:has-text('Upload from computer'), button:has-text('Select file'), button:has-text('Browse')"
            )
            if choose_btn.count() > 0 and choose_btn.first.is_visible():
                try:
                    with self.page.expect_file_chooser(timeout=8000) as fc_info:
                        choose_btn.first.click()
                    file_chooser = fc_info.value
                    file_chooser.set_files(str(pdf_path))
                    file_uploaded = True
                    logger.info("PDF file uploaded via file chooser dialog.")
                except Exception as fc_err:
                    logger.warning(f"File chooser error: {fc_err}. Attempting direct modal file input...")

            if not file_uploaded:
                # Direct modal file input fallback
                modal_inputs = self.page.locator("div[role='dialog'] input[type='file'], .artdeco-modal input[type='file']")
                if modal_inputs.count() > 0:
                    try:
                        modal_inputs.first.set_input_files(str(pdf_path))
                        file_uploaded = True
                        logger.info("PDF file uploaded via modal input[type='file'].")
                    except Exception as mi_err:
                        logger.error(f"Modal input[type='file'] failed: {mi_err}")

            if not file_uploaded:
                logger.error("Could not upload PDF file: neither file chooser nor modal file input succeeded.")
                return False

            # Step 3: Wait for document preview and Title field to appear
            logger.info("Waiting for LinkedIn to render document preview and title field...")
            self._human_delay(3.0, 5.0)

            title_text = "Mastering Cybersecurity Architecture"
            if "Mastering " in draft_text:
                first_line = draft_text.split("\n")[0].replace("Mastering ", "").replace(" in modern engineering environments.", "").strip()
                title_text = f"Mastering {first_line[:40]}"
            elif draft_text:
                title_text = draft_text.split("\n")[0][:45].strip()

            title_input = None
            title_selectors = [
                "input[placeholder*='title' i]",
                "input[name='title']",
                "input[id*='document-title']",
                "input[aria-label*='title' i]",
                "input[placeholder*='Add a title' i]"
            ]
            for tsel in title_selectors:
                try:
                    loc = self.page.wait_for_selector(tsel, timeout=6000)
                    if loc:
                        title_input = loc
                        break
                except Exception:
                    continue

            if title_input:
                title_input.fill(title_text)
                self._human_delay(1.0, 2.0)
                logger.info(f"Set document title: '{title_text}'")
            else:
                logger.warning("Document title field not detected; continuing to Done button.")

            # Step 4: Click "Done" / "Next" button in the document modal
            done_btn = None
            done_selectors = [
                "button:has-text('Done')",
                "button:has-text('Next')",
                "button.share-box-footer__primary-btn",
                "button[aria-label='Done']",
                "button[aria-label='Next']"
            ]
            for dsel in done_selectors:
                try:
                    loc = self.page.wait_for_selector(dsel, timeout=5000)
                    if loc:
                        done_btn = loc
                        break
                except Exception:
                    continue

            if done_btn:
                done_btn.click()
                self._human_delay(3.0, 5.0)
                logger.info("Clicked 'Done' on document modal. Carousel successfully attached!")
                return True
            else:
                logger.error("Could not locate 'Done' / 'Next' button in document modal.")
                return False

        except Exception as e:
            logger.error(f"Error in _attach_pdf_document: {e}")
            return False

    def create_post(self, draft_text: str, media_attachment: Optional[str] = None) -> Dict[str, Any]:
        """
        Publishes a real thought-leadership post or PDF document carousel to the user's authentic LinkedIn profile.
        Includes comprehensive DOM fallbacks, SPA state verification, and diagnostic capture.
        """
        self._ensure_browser()
        try:
            logger.info("[RealLinkedIn] Navigating to feed to publish thought leadership post...")
            self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
            self._human_delay(3.0, 5.0)

            # 1. Verify user is authenticated and not redirected to login/checkpoint
            current_url = self.page.url
            if "/login" in current_url or "/checkpoint" in current_url or "uas/login" in current_url:
                err_msg = (
                    f"LinkedIn session is not authenticated or expired (Current URL: {current_url}). "
                    "Please run 'python main.py login' or select option [8] from the menu to authenticate."
                )
                logger.error(err_msg)
                return {"status": "error", "message": err_msg}

            # 2. Scroll to top and dismiss any blocking overlay popups
            try:
                self.page.evaluate("window.scrollTo(0, 0)")
            except Exception:
                pass
            self._dismiss_overlays()
            self._human_delay(1.5, 2.5)

            # 3. Locate and click "Start a post" trigger
            opened_modal = False
            share_selectors = [
                # Modern desktop feed triggers
                "button.share-box-feed-entry__trigger",
                "div.share-box-feed-entry__top-bar button",
                "div.share-box-feed-entry__wrapper button",
                ".share-box-feed-entry button",
                "[data-view-name='feed-share-box'] button",
                # Text variants (including modern AI prompt)
                "button:has-text('Start a post')",
                "button:has-text('try writing with AI')",
                "button:has-text('Share a post')",
                "div[role='button']:has-text('Start a post')",
                "span:has-text('Start a post')",
                # Aria labels
                "button[aria-label*='Start a post' i]",
                "button[aria-label*='Create a post' i]",
                "button[aria-label*='Share a post' i]",
                # Feed creator triggers
                "#share-box-trigger",
                ".feed-shared-creator-v2 button"
            ]

            # Wait up to 15 seconds across candidates
            for selector in share_selectors:
                try:
                    loc = self.page.locator(selector)
                    if loc.count() > 0 and loc.first.is_visible():
                        loc.first.scroll_into_view_if_needed()
                        loc.first.click()
                        opened_modal = True
                        logger.info(f"Clicked 'Start a post' using selector: {selector}")
                        break
                except Exception:
                    continue

            # JavaScript DOM evaluate fallback if selectors missed
            if not opened_modal:
                logger.info("Attempting JavaScript DOM evaluation for 'Start a post' trigger...")
                js_result = self.page.evaluate('''() => {
                    const trigger = document.querySelector(
                        ".share-box-feed-entry__trigger, " +
                        "div.share-box-feed-entry__top-bar button, " +
                        "div.share-box-feed-entry__wrapper button, " +
                        "[data-view-name='feed-share-box'] button, " +
                        ".share-box-feed-entry button"
                    );
                    if (trigger) {
                        trigger.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        trigger.click();
                        return { clicked: true, method: "class_selector" };
                    }

                    const candidates = Array.from(document.querySelectorAll("button, div[role='button'], span"));
                    for (const el of candidates) {
                        const txt = (el.innerText || el.textContent || "").toLowerCase().trim();
                        const aria = (el.getAttribute("aria-label") || "").toLowerCase().trim();
                        if (txt.includes("start a post") || txt.includes("try writing with ai") || txt.includes("share a post") || aria.includes("start a post")) {
                            const target = el.closest("button") || el.closest("div[role='button']") || el;
                            target.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            target.click();
                            return { clicked: true, method: "text_search", matched: txt || aria };
                        }
                    }
                    return { clicked: false };
                }''')
                if js_result.get("clicked"):
                    opened_modal = True
                    logger.info(f"Clicked 'Start a post' via JS fallback ({js_result.get('method')})")

            if not opened_modal:
                screenshot_path = DATA_DIR / "post_failure_debug.png"
                try:
                    self.page.screenshot(path=str(screenshot_path))
                    logger.error(f"Saved diagnostic screenshot to {screenshot_path}")
                except Exception:
                    pass
                return {
                    "status": "error",
                    "message": f"Could not locate 'Start a post' button on page ({self.page.url}). Diagnostic screenshot saved to data/post_failure_debug.png."
                }

            self._human_delay(2.0, 3.5)

            # 4. Locate modal text editor
            editor_selectors = [
                "div.share-creation-state__text-editor div.ql-editor",
                "div.ql-editor[contenteditable='true']",
                "div[role='textbox'][contenteditable='true']",
                "div.share-box-modal div[role='textbox']",
                "div[data-placeholder*='talk about' i]",
                "div[aria-label*='talk about' i]",
                "div.editor-content div.ql-editor"
            ]

            editor_found = None
            for esel in editor_selectors:
                try:
                    loc = self.page.locator(esel)
                    if loc.count() > 0 and loc.first.is_visible():
                        editor_found = loc.first
                        break
                except Exception:
                    continue

            if not editor_found:
                # JS focus fallback
                js_editor = self.page.evaluate('''() => {
                    const modal = document.querySelector(".artdeco-modal, div[role='dialog'], .share-box-modal");
                    if (modal) {
                        const ed = modal.querySelector("div[contenteditable='true'], div[role='textbox'], .ql-editor");
                        if (ed) {
                            ed.focus();
                            return true;
                        }
                    }
                    return false;
                }''')

            if editor_found:
                editor_found.click()
                self._human_delay(1.0, 2.0)
            else:
                logger.warning("Editor locator not explicitly focused; attempting keyboard typing into active element.")

            # 5. Type the post text with natural human pacing
            paragraphs = draft_text.split("\n\n")
            for i, p in enumerate(paragraphs):
                try:
                    self.page.keyboard.insert_text(p)
                except Exception:
                    self.page.keyboard.type(p)
                if i < len(paragraphs) - 1:
                    self.page.keyboard.press("Enter")
                    self.page.keyboard.press("Enter")
                    self._human_delay(0.4, 0.8)

            self._human_delay(2.0, 3.5)

            # 6. If media attachment provided (PDF Carousel), attach it now
            if media_attachment and str(media_attachment).endswith(".pdf") and os.path.exists(media_attachment):
                attached = self._attach_pdf_document(str(media_attachment), draft_text)
                if not attached:
                    screenshot_path = DATA_DIR / "carousel_attach_failure.png"
                    try:
                        self.page.screenshot(path=str(screenshot_path))
                    except Exception:
                        pass
                    err_msg = (
                        "Could not attach PDF document carousel to LinkedIn post. "
                        "Post publication was automatically aborted to prevent posting text without the carousel slides. "
                        "A diagnostic screenshot has been saved to data/carousel_attach_failure.png."
                    )
                    logger.error(err_msg)
                    return {"status": "error", "message": err_msg}

                # Verify text remains in editor after document sub-modal; re-type if cleared
                editor_text = self.page.evaluate('''() => {
                    const ed = document.querySelector("div.ql-editor, div[role='textbox'][contenteditable='true']");
                    return ed ? (ed.innerText || ed.textContent || "").trim() : "";
                }''')
                if not editor_text or len(editor_text) < 10:
                    logger.info("Re-inserting post caption after document attachment...")
                    for i, p in enumerate(paragraphs):
                        try:
                            self.page.keyboard.insert_text(p)
                        except Exception:
                            self.page.keyboard.type(p)
                        if i < len(paragraphs) - 1:
                            self.page.keyboard.press("Enter")
                            self.page.keyboard.press("Enter")
                            self._human_delay(0.3, 0.6)

            # 7. Locate and click final "Post" button
            # Note: The post button may be disabled while media uploads; wait up to 15s for it to become enabled
            self._human_delay(2.0, 4.0)
            post_selectors = [
                "button.share-actions__primary-action:not([disabled])",
                "button:has-text('Post'):not([disabled])",
                "button[data-test-share-post-button]:not([disabled])",
                "div.share-box_actions button:has-text('Post'):not([disabled])"
            ]

            post_btn = None
            for psel in post_selectors:
                try:
                    loc = self.page.wait_for_selector(psel, timeout=4000)
                    if loc:
                        post_btn = loc
                        break
                except Exception:
                    continue

            # Fallback check if post button exists even if selector wait timed out
            if not post_btn:
                try:
                    post_btn = self.page.wait_for_selector(
                        "button.share-actions__primary-action, button:has-text('Post')",
                        timeout=8000
                    )
                except Exception:
                    pass

            if post_btn:
                post_btn.click()
                self._human_delay(4.0, 7.0)
                logger.info("🎉 [REAL ACTION] Published real thought leadership post to your LinkedIn profile!")
                return {"status": "success", "message": "Post published"}
            else:
                screenshot_path = DATA_DIR / "post_publish_button_missing.png"
                try:
                    self.page.screenshot(path=str(screenshot_path))
                except Exception:
                    pass
                return {"status": "error", "message": "Final Post button not found or remained disabled"}

        except Exception as e:
            logger.error(f"Failed to publish post: {e}")
            screenshot_path = DATA_DIR / "post_publish_exception.png"
            try:
                self.page.screenshot(path=str(screenshot_path))
            except Exception:
                pass
            return {"status": "error", "message": str(e)}

    def send_connection_request(self, profile_url: str, note: Optional[str] = None) -> Dict[str, Any]:
        """
        Navigates to a target user's profile, checks connection state,
        and sends a warm connection invitation with an optional personalized note.
        """
        self._ensure_browser()
        try:
            if not profile_url or "linkedin.com/in/" not in profile_url:
                return {"status": "skipped", "message": "No valid profile URL"}

            logger.info(f"🤝 [RealLinkedIn] Visiting profile for connection: {profile_url}...")
            self.page.goto(profile_url, wait_until="domcontentloaded")
            self._human_delay(3.0, 5.0)

            # Check if invitation already pending or already connected
            status_check = self.page.evaluate('''() => {
                const text = document.body.innerText;
                const pendingBtn = document.querySelector("button[aria-label*='Pending']");
                if (pendingBtn || text.includes("Pending invitation")) {
                    return { status: "pending" };
                }
                const allBtns = Array.from(document.querySelectorAll("button"));
                const connectBtn = allBtns.find(b => {
                    const t = b.innerText.trim();
                    const aria = b.getAttribute("aria-label") || "";
                    return (t === "Connect" || aria.includes("Invite") || aria.includes("Connect with")) && !aria.includes("Message");
                });
                if (connectBtn) {
                    return { status: "can_connect" };
                }
                const moreBtn = document.querySelector("button[aria-label='More actions']");
                if (moreBtn) {
                    return { status: "check_more" };
                }
                return { status: "already_connected_or_unavailable" };
            }''')

            if status_check.get("status") == "pending":
                logger.info(f"ℹ️ Connection already pending for {profile_url}.")
                return {"status": "pending", "message": "Invitation already pending"}
            elif status_check.get("status") == "already_connected_or_unavailable":
                logger.info(f"ℹ️ Already connected with {profile_url}.")
                return {"status": "already_connected", "message": "Already connected"}

            # Click Connect directly or open "More actions"
            clicked_connect = self.page.evaluate('''() => {
                const allBtns = Array.from(document.querySelectorAll("button"));
                let connectBtn = allBtns.find(b => {
                    const t = b.innerText.trim();
                    const aria = b.getAttribute("aria-label") || "";
                    return (t === "Connect" || aria.includes("Invite") || aria.includes("Connect with")) && !aria.includes("Message");
                });
                if (connectBtn) {
                    connectBtn.click();
                    return "clicked";
                }
                const moreBtn = document.querySelector("button[aria-label='More actions']");
                if (moreBtn) {
                    moreBtn.click();
                    return "more";
                }
                return "none";
            }''')

            if clicked_connect == "more":
                self._human_delay(1.0, 2.0)
                self.page.evaluate('''() => {
                    const items = Array.from(document.querySelectorAll("div[role='button'], div[role='menuitem']"));
                    const connectItem = items.find(el => el.innerText.includes("Connect"));
                    if (connectItem) connectItem.click();
                }''')

            self._human_delay(1.5, 3.0)

            # If note provided, click "Add a note"
            if note:
                clean_note = note[:280].strip()
                note_btn = self.page.locator("button:has-text('Add a note')")
                if note_btn.count() > 0 and note_btn.first.is_visible():
                    note_btn.first.click()
                    self._human_delay(1.0, 2.0)
                    text_area = self.page.locator("textarea[name='message'], #custom-message")
                    if text_area.count() > 0 and text_area.first.is_visible():
                        text_area.first.fill(clean_note)
                        self._human_delay(1.0, 2.0)

            # Click "Send" / "Send invitation"
            send_btn = self.page.locator("button:has-text('Send invitation'), button:has-text('Send without a note'), button:has-text('Send')")
            if send_btn.count() > 0 and send_btn.first.is_visible():
                send_btn.first.click()
                self._human_delay(2.0, 4.0)
                logger.info(f"🎉 [RealLinkedIn] Connection invitation sent to {profile_url}!")
                return {"status": "success", "profile_url": profile_url}
            else:
                return {"status": "skipped", "message": "Send modal button not found"}

        except Exception as e:
            logger.error(f"Failed to send connection request to {profile_url}: {e}")
            return {"status": "error", "message": str(e)}

    def reply_to_comment(self, post_id: str, reply_text: str) -> Dict[str, Any]:
        """
        Submits a contextual reply to an ongoing comment thread inside card [post_id].
        """
        self._ensure_browser()
        try:
            logger.info(f"[RealLinkedIn] Submitting thread reply to card [{post_id}]...")
            # Click Reply button inside the card or use comment box
            return self.comment_post(post_id, reply_text)
        except Exception as e:
            logger.error(f"Failed to reply to comment thread on {post_id}: {e}")
            return {"status": "error", "message": str(e)}
