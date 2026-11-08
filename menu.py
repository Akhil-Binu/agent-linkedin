#!/usr/bin/env python3
"""
LinkedBot Interactive Menu Launcher
Lists all primary features [1] to [6] for convenient execution without remembering CLI flags.
"""

import sys
import os
import webbrowser
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from main import LinkedBotAgent, RICH_AVAILABLE

if RICH_AVAILABLE:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    console = Console()
else:
    console = None

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def print_banner():
    title = (
        "╔══════════════════════════════════════════════════════════════╗\n"
        "║          🤖 LINKEDBOT - AUTONOMOUS LINKEDIN AGENT           ║\n"
        "║            Interactive Feature Menu: Choose [1-6]           ║\n"
        "╚══════════════════════════════════════════════════════════════╝"
    )
    if RICH_AVAILABLE:
        console.print(Panel(title, style="bold cyan", expand=False))
    else:
        print(title)

def display_menu():
    print("\nSelect a feature to execute:")
    print("  [1] 🔎 Targeted Search & Engagement (Latest #Cybersecurity Posts, 15 Comments & 20 Likes)")
    print("  [2] 🚀 General Feed Engagement Loop (Must-Rule: 15 Comments & 20 Likes)")
    print("  [3] 🤝 Warm Connection Requests (Personalized Outreach to Commented Authors)")
    print("  [4] 🔄 2-Way Reply Tracker (Continue Dialogues on Active Threads)")
    print("  [5] 📑 AI Carousel Generator (Design 5-Slide PDF Document for LinkedIn)")
    print("  [6] 🌐 Launch Web Command Center Dashboard (http://127.0.0.1:8000)")
    print("  --------------------------------------------------------------")
    print("  [7] 📊 View Analytics & Activity History")
    print("  [8] 🛡️ View Rate Limit & Queue Status")
    print("  [9] 🔐 Real LinkedIn 1-Time Interactive Login")
    print("  [0] ❌ Exit")
    print()

def ask_choice() -> str:
    try:
        return input("👉 Enter choice [0-9]: ").strip()
    except (KeyboardInterrupt, EOFError):
        return "0"

def ask_mode() -> str:
    val = input("Run with Real LinkedIn Browser? [Y/n] (default: Y): ").strip().lower()
    return "REAL" if val != "n" else "MOCK"

def run_menu():
    while True:
        print_banner()
        display_menu()
        choice = ask_choice()

        if choice == "1":
            print("\n--- [1] TARGETED SEARCH & ENGAGEMENT ---")
            query = input("Enter search query or hashtag (default: '#cybersecurity'): ").strip()
            if not query:
                query = "#cybersecurity"
            
            connect_val = input("Send warm connection request after commenting? [y/N]: ").strip().lower()
            do_connect = (connect_val == "y")
            
            mode = ask_mode()
            print(f"\n🚀 Initializing LinkedBot in {mode} mode for query '{query}'...")
            bot = LinkedBotAgent(override_mode=mode)
            try:
                bot.run_engagement_cycle(
                    target_comments=15,
                    target_likes=20,
                    search_query=query,
                    sort_by="date_posted",
                    auto_connect=do_connect
                )
            finally:
                bot.close()
            input("\nPress Enter to return to menu...")

        elif choice == "2":
            print("\n--- [2] GENERAL FEED ENGAGEMENT LOOP (MUST-RULE) ---")
            print("Target: Minimum 15 Comments & 20 Likes on relevant posts.")
            mode = ask_mode()
            bot = LinkedBotAgent(override_mode=mode)
            try:
                bot.run_engagement_cycle(target_comments=15, target_likes=20)
            finally:
                bot.close()
            input("\nPress Enter to return to menu...")

        elif choice == "3":
            print("\n--- [3] WARM CONNECTION REQUEST OUTREACH ---")
            query = input("Enter topic or hashtag to discover authors (default: 'cloud security'): ").strip()
            if not query:
                query = "cloud security"
            mode = ask_mode()
            bot = LinkedBotAgent(override_mode=mode)
            try:
                print(f"Executing scan and sending warm connections for '{query}'...")
                bot.run_engagement_cycle(
                    target_comments=5,
                    target_likes=10,
                    search_query=query,
                    sort_by="date_posted",
                    auto_connect=True
                )
            finally:
                bot.close()
            input("\nPress Enter to return to menu...")

        elif choice == "4":
            print("\n--- [4] 2-WAY REPLY TRACKER & CONVERSATION FOLLOW-UPS ---")
            limit_str = input("How many recent posts to check for replies? (default: 10): ").strip()
            limit = int(limit_str) if limit_str.isdigit() else 10
            mode = ask_mode()
            bot = LinkedBotAgent(override_mode=mode)
            try:
                bot.check_replies_and_follow_up(limit=limit)
            finally:
                bot.close()
            input("\nPress Enter to return to menu...")

        elif choice == "5":
            print("\n--- [5] AI CAROUSEL (PDF SLIDE) GENERATOR ---")
            print("1. Generate from pre-vetted Content Bank (e.g. 'cb_iam_01')")
            print("2. Generate from custom topic")
            sub_c = input("Choose (1 or 2): ").strip()

            bot = LinkedBotAgent(override_mode="MOCK")
            try:
                if sub_c == "1":
                    bank_id = input("Enter Content Bank ID (default: 'cb_iam_01'): ").strip() or "cb_iam_01"
                    pub_val = input("Publish directly as a document post to LinkedIn? [y/N]: ").strip().lower()
                    if pub_val == "y":
                        bot.close()
                        bot = LinkedBotAgent(override_mode="REAL")
                    bot.generate_carousel(from_bank_id=bank_id, publish=(pub_val == "y"))
                else:
                    topic = input("Enter custom topic (e.g. 'Zero Trust Kubernetes'): ").strip()
                    if not topic:
                        topic = "Zero Trust Kubernetes Architecture"
                    pub_val = input("Publish directly as a document post to LinkedIn? [y/N]: ").strip().lower()
                    if pub_val == "y":
                        bot.close()
                        bot = LinkedBotAgent(override_mode="REAL")
                    bot.generate_carousel(topic=topic, publish=(pub_val == "y"))
            finally:
                bot.close()
            input("\nPress Enter to return to menu...")

        elif choice == "6":
            print("\n--- [6] WEB COMMAND CENTER DASHBOARD ---")
            print("Launching FastAPI Web Command Center at http://127.0.0.1:8000 ...")
            try:
                webbrowser.open("http://127.0.0.1:8000")
            except Exception:
                pass
            import uvicorn
            uvicorn.run("web.server:app", host="127.0.0.1", port=8000, reload=False)
            break

        elif choice == "7":
            print("\n--- [7] ANALYTICS & METRICS ---")
            bot = LinkedBotAgent(override_mode="MOCK")
            try:
                bot.print_analytics()
            finally:
                bot.close()
            input("\nPress Enter to return to menu...")

        elif choice == "8":
            print("\n--- [8] RATE LIMIT & SYSTEM STATUS ---")
            bot = LinkedBotAgent(override_mode="MOCK")
            try:
                bot.print_status()
            finally:
                bot.close()
            input("\nPress Enter to return to menu...")

        elif choice == "9":
            print("\n--- [9] REAL LINKEDIN INTERACTIVE LOGIN ---")
            bot = LinkedBotAgent(override_mode="REAL")
            try:
                bot.interactive_login()
            finally:
                bot.close()
            input("\nPress Enter to return to menu...")

        elif choice == "0":
            print("\n👋 Exiting LinkedBot. Happy networking!\n")
            break
        else:
            print("⚠️ Invalid choice. Please enter a number between 0 and 9.")
            input("Press Enter to continue...")

if __name__ == "__main__":
    run_menu()
