import os
import re
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import portrait
from config.settings import BASE_DIR

logger = logging.getLogger("LinkedBot.Carousel")

OUTPUT_DIR = BASE_DIR / "data" / "carousels"

# Slide Dimensions: LinkedIn 4:5 Portrait Ratio (800 x 1000 pt)
PAGE_WIDTH = 800
PAGE_HEIGHT = 1000

class CarouselGenerator:
    """
    Generates high-authority, 5-slide PDF document carousels tailored for LinkedIn.
    Uses modern dark-mode aesthetic with cyber-cyan accents and crisp typography.
    """
    def __init__(self, output_dir: Path = OUTPUT_DIR):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _draw_background(self, c: canvas.Canvas):
        """Draws dark slate background with subtle cyber accents."""
        # Main background: Dark slate / navy
        c.setFillColor(colors.HexColor("#0B0F19"))
        c.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=True, stroke=False)

        # Top neon accent line
        c.setFillColor(colors.HexColor("#00E5FF"))
        c.rect(0, PAGE_HEIGHT - 6, PAGE_WIDTH, 6, fill=True, stroke=False)

        # Subtle bottom bar
        c.setFillColor(colors.HexColor("#151D2E"))
        c.rect(0, 0, PAGE_WIDTH, 60, fill=True, stroke=False)

    def _draw_card(self, c: canvas.Canvas, x: float, y: float, w: float, h: float, border_color: str = "#24324D", bg_color: str = "#111827"):
        """Draws rounded container box for slide content."""
        c.setFillColor(colors.HexColor(bg_color))
        c.setStrokeColor(colors.HexColor(border_color))
        c.setLineWidth(1.5)
        c.roundRect(x, y, w, h, 16, fill=True, stroke=True)

    def _draw_header(self, c: canvas.Canvas, tag: str, slide_num: int, total_slides: int = 5):
        """Draws category tag and slide counter."""
        # Category Tag badge
        c.setFillColor(colors.HexColor("#00E5FF"))
        c.setFont("Helvetica-Bold", 14)
        c.drawString(60, PAGE_HEIGHT - 60, f"// {tag.upper()}")

        # Slide Number
        c.setFillColor(colors.HexColor("#7E8B9B"))
        c.setFont("Helvetica-Bold", 15)
        c.drawRightString(PAGE_WIDTH - 60, PAGE_HEIGHT - 60, f"{slide_num:02d} / {total_slides:02d}")

        # Thin separator line
        c.setStrokeColor(colors.HexColor("#1F293D"))
        c.setLineWidth(1)
        c.line(60, PAGE_HEIGHT - 75, PAGE_WIDTH - 60, PAGE_HEIGHT - 75)

    def _draw_footer(self, c: canvas.Canvas, is_last: bool = False, handle: str = "Akhil Binu"):
        """Draws slide footer with handle and swipe indicator."""
        c.setFillColor(colors.HexColor("#8E9CAE"))
        c.setFont("Helvetica", 14)
        c.drawString(60, 24, f"🛡️ {handle} • Senior Cybersecurity & Cloud")

        if not is_last:
            c.setFillColor(colors.HexColor("#00E5FF"))
            c.setFont("Helvetica-Bold", 14)
            c.drawRightString(PAGE_WIDTH - 60, 24, "SWIPE NEXT ➔")
        else:
            c.setFillColor(colors.HexColor("#00FF66"))
            c.setFont("Helvetica-Bold", 14)
            c.drawRightString(PAGE_WIDTH - 60, 24, "SAVE & FOLLOW 🔖")

    def _wrap_text(self, text: str, max_chars: int = 40) -> List[str]:
        """Wraps text into lines based on word boundaries."""
        words = text.split()
        lines = []
        current_line = []
        current_len = 0

        for word in words:
            if current_len + len(word) + 1 <= max_chars:
                current_line.append(word)
                current_len += len(word) + 1
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_len = len(word)
        if current_line:
            lines.append(" ".join(current_line))
        return lines

    def generate_carousel_from_topic(
        self,
        topic: str,
        category: str = "Cloud Security",
        author_name: str = "Akhil Binu",
        custom_slides: Optional[List[Dict[str, Any]]] = None
    ) -> Path:
        """
        Creates a 5-slide PDF carousel document.
        Returns the absolute Path of the generated PDF file.
        """
        slug = re.sub(r'[^a-zA-Z0-9]+', '_', topic.lower()).strip('_')[:35]
        filename = f"carousel_{slug}_{int(time.time())}.pdf"
        pdf_path = self.output_dir / filename

        c = canvas.Canvas(str(pdf_path), pagesize=(PAGE_WIDTH, PAGE_HEIGHT))

        # Default 5-slide structured playbook if custom slides not provided
        slides = custom_slides or self._build_default_slide_content(topic, category)

        for i, slide in enumerate(slides):
            slide_num = i + 1
            is_last = (slide_num == len(slides))

            # Background & Shell
            self._draw_background(c)
            self._draw_header(c, category, slide_num, len(slides))
            self._draw_footer(c, is_last=is_last, handle=author_name)

            if slide_num == 1:
                # Slide 1: Cover / Hook
                self._render_cover_slide(c, slide, author_name)
            elif slide_num == 2:
                # Slide 2: The Core Problem / Breakdown
                self._render_problem_slide(c, slide)
            elif slide_num == 3:
                # Slide 3: The Common Pitfall / Anti-Pattern
                self._render_pitfall_slide(c, slide)
            elif slide_num == 4:
                # Slide 4: Actionable 3-Step Playbook
                self._render_playbook_slide(c, slide)
            else:
                # Slide 5: Key Takeaway & Conclusion
                self._render_summary_slide(c, slide, author_name)

            c.showPage()

        c.save()
        logger.info(f"🎉 [Carousel] Successfully generated PDF carousel: {pdf_path}")
        return pdf_path

    def _render_cover_slide(self, c: canvas.Canvas, slide: Dict[str, Any], author: str):
        """Renders Slide 1: High-impact Title and Subtitle."""
        # Top badge
        c.setFillColor(colors.HexColor("#1E293B"))
        c.setStrokeColor(colors.HexColor("#00E5FF"))
        c.roundRect(60, PAGE_HEIGHT - 170, 280, 42, 8, fill=True, stroke=True)
        c.setFillColor(colors.HexColor("#00E5FF"))
        c.setFont("Helvetica-Bold", 14)
        c.drawString(80, PAGE_HEIGHT - 144, "PRACTICAL PLAYBOOK")

        # Main Title (wrapped)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 40)
        title_lines = self._wrap_text(slide.get("title", ""), max_chars=28)
        y = PAGE_HEIGHT - 250
        for line in title_lines:
            c.drawString(60, y, line)
            y -= 52

        # Subtitle / Hook in container card
        card_y = 300
        self._draw_card(c, 60, card_y, PAGE_WIDTH - 120, 220, border_color="#00E5FF", bg_color="#0F172A")

        c.setFillColor(colors.HexColor("#94A3B8"))
        c.setFont("Helvetica-Bold", 16)
        c.drawString(90, card_y + 175, "WHAT YOU WILL LEARN:")

        c.setFillColor(colors.HexColor("#E2E8F0"))
        c.setFont("Helvetica", 19)
        hook_lines = self._wrap_text(slide.get("hook", ""), max_chars=44)
        hy = card_y + 135
        for hline in hook_lines:
            c.drawString(90, hy, hline)
            hy -= 32

        # Call to action banner
        c.setFillColor(colors.HexColor("#00E5FF"))
        c.setFont("Helvetica-Bold", 18)
        c.drawString(60, 160, "Swipe across to inspect the breakdown ➔")

    def _render_problem_slide(self, c: canvas.Canvas, slide: Dict[str, Any]):
        """Renders Slide 2: The Core Challenge / Status Quo."""
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 34)
        c.drawString(60, PAGE_HEIGHT - 130, slide.get("title", "The Current Reality"))

        # Stat / Callout Card
        stat_box_y = PAGE_HEIGHT - 380
        self._draw_card(c, 60, stat_box_y, PAGE_WIDTH - 120, 200, border_color="#EF4444", bg_color="#18131E")
        c.setFillColor(colors.HexColor("#EF4444"))
        c.setFont("Helvetica-Bold", 48)
        c.drawString(90, stat_box_y + 125, slide.get("stat_highlight", "82% of Breaches"))

        c.setFillColor(colors.HexColor("#E2E8F0"))
        c.setFont("Helvetica", 19)
        stat_lines = self._wrap_text(slide.get("stat_desc", "Originate from misconfigured privileges and unpruned developer roles."), max_chars=45)
        sy = stat_box_y + 75
        for sline in stat_lines:
            c.drawString(90, sy, sline)
            sy -= 30

        # Detailed breakdown points
        points_y = stat_box_y - 80
        c.setFillColor(colors.HexColor("#00E5FF"))
        c.setFont("Helvetica-Bold", 20)
        c.drawString(60, points_y, "Why standard processes fall short:")

        y = points_y - 45
        for pt in slide.get("points", []):
            self._draw_card(c, 60, y - 45, PAGE_WIDTH - 120, 75, border_color="#24324D", bg_color="#111827")
            c.setFillColor(colors.HexColor("#00E5FF"))
            c.setFont("Helvetica-Bold", 18)
            c.drawString(85, y - 5, "✕")
            c.setFillColor(colors.HexColor("#CBD5E1"))
            c.setFont("Helvetica", 18)
            c.drawString(120, y - 5, pt[:60])
            y -= 95

    def _render_pitfall_slide(self, c: canvas.Canvas, slide: Dict[str, Any]):
        """Renders Slide 3: The Common Pitfall & Architecture Gap."""
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 34)
        c.drawString(60, PAGE_HEIGHT - 130, slide.get("title", "The Hidden Vulnerability"))

        # Main explanation card
        card_y = PAGE_HEIGHT - 480
        self._draw_card(c, 60, card_y, PAGE_WIDTH - 120, 310, border_color="#F59E0B", bg_color="#191714")

        c.setFillColor(colors.HexColor("#F59E0B"))
        c.setFont("Helvetica-Bold", 20)
        c.drawString(90, card_y + 260, "⚠️  THE CRITICAL MISCONCEPTION:")

        c.setFillColor(colors.HexColor("#E2E8F0"))
        c.setFont("Helvetica", 19)
        pitfall_lines = self._wrap_text(slide.get("pitfall_text", ""), max_chars=46)
        py = card_y + 215
        for pline in pitfall_lines:
            c.drawString(90, py, pline)
            py -= 32

        # Direct impact card below
        impact_y = 180
        self._draw_card(c, 60, impact_y, PAGE_WIDTH - 120, 220, border_color="#3B82F6", bg_color="#0F172A")
        c.setFillColor(colors.HexColor("#3B82F6"))
        c.setFont("Helvetica-Bold", 18)
        c.drawString(90, impact_y + 170, "THE REAL-WORLD IMPACT:")

        c.setFillColor(colors.HexColor("#CBD5E1"))
        c.setFont("Helvetica", 18)
        impact_lines = self._wrap_text(slide.get("impact_text", ""), max_chars=46)
        iy = impact_y + 125
        for iline in impact_lines:
            c.drawString(90, iy, iline)
            iy -= 30

    def _render_playbook_slide(self, c: canvas.Canvas, slide: Dict[str, Any]):
        """Renders Slide 4: 3-Step Practical Fix."""
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 34)
        c.drawString(60, PAGE_HEIGHT - 130, slide.get("title", "The 3-Step Action Plan"))

        steps = slide.get("steps", [
            ("01", "Automate Role Pruning", "Run scheduled scans to discover and revoke inactive IAM privileges every 30 days."),
            ("02", "Hardware Security Keys", "Enforce FIDO2 WebAuthn keys for internal developer accounts to neutralize token theft."),
            ("03", "Continuous Verification", "Enforce CI/CD policy-as-code assertions to reject wildcard permissions prior to deployment.")
        ])

        y = PAGE_HEIGHT - 220
        for num, step_title, step_desc in steps:
            self._draw_card(c, 60, y - 130, PAGE_WIDTH - 120, 140, border_color="#00E5FF", bg_color="#101C31")

            # Step number circle badge
            c.setFillColor(colors.HexColor("#00E5FF"))
            c.setFont("Helvetica-Bold", 24)
            c.drawString(90, y - 35, num)

            # Step Title
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 20)
            c.drawString(145, y - 35, step_title)

            # Step Description
            c.setFillColor(colors.HexColor("#94A3B8"))
            c.setFont("Helvetica", 16)
            desc_lines = self._wrap_text(step_desc, max_chars=50)
            dy = y - 70
            for dline in desc_lines:
                c.drawString(145, dy, dline)
                dy -= 24

            y -= 175

    def _render_summary_slide(self, c: canvas.Canvas, slide: Dict[str, Any], author: str):
        """Renders Slide 5: Takeaway, Checklist, and Call-to-Action."""
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 34)
        c.drawString(60, PAGE_HEIGHT - 130, "The Bottom Line")

        # Takeaway box
        box_y = PAGE_HEIGHT - 380
        self._draw_card(c, 60, box_y, PAGE_WIDTH - 120, 205, border_color="#10B981", bg_color="#0D201A")

        c.setFillColor(colors.HexColor("#10B981"))
        c.setFont("Helvetica-Bold", 18)
        c.drawString(90, box_y + 160, "💡 CORE TAKEAWAY:")

        c.setFillColor(colors.HexColor("#ECFDF5"))
        c.setFont("Helvetica", 20)
        takeaway_lines = self._wrap_text(slide.get("takeaway", "Real security is not adding more complexity. It is removing stale permissions and enforcing deterministic guardrails."), max_chars=44)
        ty = box_y + 115
        for tline in takeaway_lines:
            c.drawString(90, ty, tline)
            ty -= 32

        # Follow & Save Card
        cta_y = 160
        self._draw_card(c, 60, cta_y, PAGE_WIDTH - 120, 310, border_color="#00E5FF", bg_color="#111827")

        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 26)
        c.drawString(90, cta_y + 245, "Found this breakdown valuable?")

        c.setFillColor(colors.HexColor("#94A3B8"))
        c.setFont("Helvetica", 18)
        c.drawString(90, cta_y + 195, "1. 🔖 Save this post for your next architecture review.")
        c.drawString(90, cta_y + 155, f"2. ➕ Follow {author} for weekly cybersecurity deep-dives.")
        c.drawString(90, cta_y + 115, "3. 💬 Share your perspective in the comments below.")

        c.setFillColor(colors.HexColor("#00E5FF"))
        c.setFont("Helvetica-Bold", 20)
        c.drawString(90, cta_y + 55, "Let's build secure systems together.")

    def _build_default_slide_content(self, topic: str, category: str) -> List[Dict[str, Any]]:
        """Provides default structured slide contents for cybersecurity topics."""
        return [
            {
                "title": f"The Practical Architecture Guide to {topic}",
                "hook": "Why legacy access reviews fail at modern scale, and how engineering teams enforce real least-privilege without slowing release velocity."
            },
            {
                "title": "The Industry Reality",
                "stat_highlight": "82% of Breaches",
                "stat_desc": "Involve compromised credentials, wildcard IAM privileges, or stale access keys.",
                "points": [
                    "Manual audit spreadsheets become outdated within 48 hours.",
                    "Engineers grant wildcard permissions to bypass release blockers.",
                    "Alert fatigue drowns out high-fidelity exposure signals."
                ]
            },
            {
                "title": "The Root Cause Pitfall",
                "pitfall_text": "Assuming your perimeter firewall or traditional SIEM protects against over-privileged internal service accounts.",
                "impact_text": "When an attacker lands inside, unpruned IAM roles allow instant privilege escalation across entire cloud tenants."
            },
            {
                "title": "The 3-Step Remediation Plan",
                "steps": [
                    ("01", "Automated Usage Auditing", "Continuously compare granted permissions against active API calls over 30 days."),
                    ("02", "Hardware Authentication", "Enforce FIDO2 security keys for production developer logins to stop AiTM token theft."),
                    ("03", "CI/CD Policy Guardrails", "Block pull requests that introduce wildcard AdministratorAccess before deployment.")
                ]
            },
            {
                "takeaway": "Real security is not adding more vendor tools. It is enforcing least privilege by default and automating the elimination of stale access."
            }
        ]
