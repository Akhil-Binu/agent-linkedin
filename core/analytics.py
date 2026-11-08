import sqlite3
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "analytics.db"

class AnalyticsTracker:
    """
    SQLite-backed event logger and metrics engine for LinkedBot.
    Records post evaluations, like actions, comment dispatches,
    HITL decisions, and tone quality scores.
    """
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            # Table for post evaluations
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS post_evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id TEXT,
                    author_name TEXT,
                    author_headline TEXT,
                    content_snippet TEXT,
                    relevance_score REAL,
                    sentiment TEXT,
                    author_credibility TEXT,
                    should_like INTEGER,
                    should_comment INTEGER,
                    confidence_score REAL,
                    timestamp REAL
                )
            """)
            # Table for executed actions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS action_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_type TEXT,
                    target_id TEXT,
                    content TEXT,
                    confidence_score REAL,
                    status TEXT,
                    channel TEXT,
                    timestamp REAL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def record_evaluation(self, post_id: str, author: Dict[str, Any], snippet: str,
                          relevance: float, sentiment: str, credibility: str,
                          should_like: bool, should_comment: bool, confidence: float):
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO post_evaluations (
                    post_id, author_name, author_headline, content_snippet,
                    relevance_score, sentiment, author_credibility,
                    should_like, should_comment, confidence_score, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                post_id,
                author.get("name", "Unknown"),
                author.get("headline", ""),
                snippet[:250],
                relevance,
                sentiment,
                credibility,
                1 if should_like else 0,
                1 if should_comment else 0,
                confidence,
                time.time()
            ))
            conn.commit()
        finally:
            conn.close()

    def record_action(self, action_type: str, target_id: Optional[str],
                      content: str, confidence: float, status: str = "success", channel: str = "direct"):
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO action_history (
                    action_type, target_id, content, confidence_score, status, channel, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                action_type,
                target_id or "",
                content[:500],
                confidence,
                status,
                channel,
                time.time()
            ))
            conn.commit()
        finally:
            conn.close()

    def get_summary_metrics(self) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            # Total posts evaluated
            cursor.execute("SELECT COUNT(*) FROM post_evaluations")
            total_scanned = cursor.fetchone()[0]

            # Average confidence
            cursor.execute("SELECT AVG(confidence_score) FROM post_evaluations")
            avg_conf = cursor.fetchone()[0] or 0.0

            # Actions breakdown
            cursor.execute("""
                SELECT action_type, COUNT(*)
                FROM action_history
                WHERE status = 'success'
                GROUP BY action_type
            """)
            actions = dict(cursor.fetchall())

            # Recent actions
            cursor.execute("""
                SELECT action_type, target_id, content, timestamp
                FROM action_history
                ORDER BY timestamp DESC
                LIMIT 5
            """)
            recent = cursor.fetchall()

            return {
                "total_scanned": total_scanned,
                "avg_confidence": round(avg_conf, 1),
                "total_likes": actions.get("likes", 0),
                "total_comments": actions.get("comments", 0),
                "total_posts": actions.get("posts", 0),
                "recent_actions": [
                    {
                        "type": r[0],
                        "target": r[1],
                        "snippet": r[2][:60],
                        "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r[3]))
                    }
                    for r in recent
                ]
            }
        finally:
            conn.close()

    def get_recent_commented_posts(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Returns recently commented posts for 2-way thread reply tracking."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT target_id, content, confidence_score, timestamp
                FROM action_history
                WHERE action_type = 'comments' AND status = 'success'
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
