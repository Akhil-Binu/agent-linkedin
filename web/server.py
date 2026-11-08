import os
import json
import time
from typing import Optional, Dict, Any, List
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from config.settings import load_config
from core.rate_limiter import RateLimiter
from core.evaluator import PostEvaluator
from core.generator import ContentGenerator
from core.hitl import HITLManager, HITLItem
from core.analytics import AnalyticsTracker
from core.content_bank import ContentBank
from connectors.linkedin_client import get_linkedin_connector

app = FastAPI(title="LinkedBot Command Center", version="2.0")

# Agent instances
config = load_config()
rate_limiter = RateLimiter(config.safety.rate_limits)
evaluator = PostEvaluator(config)
generator = ContentGenerator(config)
hitl = HITLManager(config)
analytics = AnalyticsTracker()
content_bank = ContentBank()
connector = get_linkedin_connector(config.linkedin_mode)

class EditItemPayload(BaseModel):
    content: str

class GeneratePostPayload(BaseModel):
    topic: str
    stage_to_hitl: bool = True

@app.get("/api/status")
def get_status():
    summary = rate_limiter.get_status_summary()
    pending = len(hitl.list_pending())
    metrics = analytics.get_summary_metrics()
    return {
        "domain": config.domain.title(),
        "mode": config.linkedin_mode,
        "llm_provider": config.llm_provider,
        "pending_hitl": pending,
        "in_backoff": summary["in_backoff"],
        "seconds_until_resume": summary["seconds_until_resume"],
        "actions_24h": summary["actions_24h"],
        "metrics": metrics
    }

@app.get("/api/queue")
def get_queue():
    pending = hitl.list_pending()
    return [p.model_dump() for p in pending]

@app.post("/api/queue/{item_id}/approve")
def approve_item(item_id: str):
    pending = {i.id: i for i in hitl.list_pending()}
    if item_id not in pending:
        raise HTTPException(status_code=404, detail="Item not found")

    item = pending[item_id]
    if item.action_type == "comment" and item.target_id:
        connector.comment_post(item.target_id, item.draft_content)
        rate_limiter.record_action("comments")
        analytics.record_action("comments", item.target_id, item.draft_content, item.confidence_score, channel="web_approved")
    elif item.action_type == "post":
        connector.create_post(item.draft_content)
        rate_limiter.record_action("posts")
        analytics.record_action("posts", None, item.draft_content, item.confidence_score, channel="web_approved")

    hitl.update_item_status(item_id, "approved")
    return {"status": "success", "message": f"Approved and dispatched {item_id}"}

@app.post("/api/queue/{item_id}/reject")
def reject_item(item_id: str):
    success = hitl.update_item_status(item_id, "rejected")
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    analytics.record_action("hitl", item_id, "Rejected by user", 0.0, status="rejected", channel="web")
    return {"status": "success", "message": f"Rejected {item_id}"}

@app.post("/api/queue/{item_id}/edit")
def edit_item(item_id: str, payload: EditItemPayload):
    success = hitl.update_item_status(item_id, "pending", edited_content=payload.content)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "success", "message": f"Updated {item_id}"}

@app.get("/api/bank")
def get_bank():
    return content_bank.get_all()

@app.post("/api/bank/{post_id}/stage")
def stage_bank_post(post_id: str):
    bank_post = content_bank.get_by_id(post_id)
    if not bank_post:
        raise HTTPException(status_code=404, detail="Bank post not found")

    item = HITLItem(
        action_type="post",
        draft_content=bank_post.get("content", "").strip(),
        confidence_score=95.0,
        reason=f"Content Bank: {bank_post.get('topic')}"
    )
    hitl.enqueue(item)
    return {"status": "success", "item_id": item.id}

@app.post("/api/post/generate")
def generate_custom_post(payload: GeneratePostPayload):
    draft, confidence, violations = generator.generate_post(payload.topic)
    item_id = None
    if payload.stage_to_hitl:
        item = HITLItem(
            action_type="post",
            draft_content=draft,
            confidence_score=confidence,
            violations=violations,
            reason=f"Custom topic: {payload.topic}"
        )
        hitl.enqueue(item)
        item_id = item.id

    return {
        "topic": payload.topic,
        "draft": draft,
        "confidence": confidence,
        "violations": violations,
        "staged_id": item_id
    }

def _run_scan_task():
    feed = connector.get_feed(keywords=config.target_keywords)
    for post in feed:
        post_id = post.get("post_id", "unknown")
        author = post.get("author", {})
        content = post.get("content", "")

        eval_res = evaluator.analyze_post(post_id, content, author)
        analytics.record_evaluation(
            post_id=post_id, author=author, snippet=content,
            relevance=eval_res.relevance_score, sentiment=eval_res.sentiment,
            credibility=eval_res.author_credibility, should_like=eval_res.should_like,
            should_comment=eval_res.should_comment, confidence=eval_res.confidence_score
        )

        if eval_res.should_like:
            allowed, _ = rate_limiter.can_perform("likes")
            if allowed:
                res = connector.like_post(post_id)
                if res.get("status") == "success":
                    rate_limiter.record_action("likes")
                    analytics.record_action("likes", post_id, "Liked high-signal post", eval_res.confidence_score)

        if eval_res.should_comment:
            comment, confidence, violations = generator.generate_comment(content, author, eval_res.suggested_angle)
            if confidence < config.hitl_threshold or violations:
                hitl.enqueue(HITLItem(
                    action_type="comment",
                    target_id=post_id,
                    target_author=author.get("name"),
                    original_content=content[:200],
                    draft_content=comment,
                    confidence_score=confidence,
                    violations=violations,
                    reason="Low confidence or tone review needed"
                ))
            else:
                allowed, _ = rate_limiter.can_perform("comments")
                if allowed:
                    res = connector.comment_post(post_id, comment)
                    if res.get("status") == "success":
                        rate_limiter.record_action("comments")
                        analytics.record_action("comments", post_id, comment, confidence)

@app.post("/api/run")
def trigger_run(background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_scan_task)
    return {"status": "started", "message": "Autonomous engagement cycle initiated in background."}

@app.get("/", response_class=HTMLResponse)
def index_page():
    return HTML_CONTENT

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LinkedBot Control Center | Cybersecurity AI Agent</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            brand: { 50: '#f0fdf4', 500: '#10b981', 600: '#059669', 700: '#047857', 900: '#064e3b' }
          }
        }
      }
    }
  </script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex flex-col">

  <!-- Header -->
  <header class="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <div class="w-9 h-9 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold text-lg">
          <i class="fa-solid fa-shield-halved"></i>
        </div>
        <div>
          <span class="font-bold text-lg tracking-tight bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">LinkedBot</span>
          <span class="text-xs px-2 py-0.5 ml-2 rounded-full bg-slate-800 text-slate-400 border border-slate-700">Cybersecurity B2B</span>
        </div>
      </div>
      <div class="flex items-center space-x-4">
        <button onclick="triggerScan()" class="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-sm flex items-center space-x-2 transition shadow-lg shadow-emerald-900/30">
          <i class="fa-solid fa-bolt"></i>
          <span>Run Scan Now</span>
        </button>
        <span id="cooldown-badge" class="hidden px-2.5 py-1 text-xs font-semibold rounded-md bg-amber-500/20 text-amber-400 border border-amber-500/30">
          Rate-Limit Cooldown
        </span>
      </div>
    </div>
  </header>

  <!-- Main Container -->
  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full space-y-8">

    <!-- Top KPI Cards -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
      <div class="bg-slate-900 border border-slate-800 p-5 rounded-xl shadow-sm">
        <div class="text-slate-400 text-xs font-medium uppercase tracking-wider">Pending Review</div>
        <div id="stat-pending" class="text-3xl font-extrabold text-amber-400 mt-2">0</div>
        <div class="text-xs text-slate-500 mt-1">Comments & Posts awaiting HITL</div>
      </div>
      <div class="bg-slate-900 border border-slate-800 p-5 rounded-xl shadow-sm">
        <div class="text-slate-400 text-xs font-medium uppercase tracking-wider">Evaluation Confidence</div>
        <div id="stat-confidence" class="text-3xl font-extrabold text-emerald-400 mt-2">--%</div>
        <div class="text-xs text-slate-500 mt-1">Average quality threshold</div>
      </div>
      <div class="bg-slate-900 border border-slate-800 p-5 rounded-xl shadow-sm">
        <div class="text-slate-400 text-xs font-medium uppercase tracking-wider">Total Engagements</div>
        <div id="stat-engagements" class="text-3xl font-extrabold text-cyan-400 mt-2">0</div>
        <div class="text-xs text-slate-500 mt-1">Likes & value comments executed</div>
      </div>
      <div class="bg-slate-900 border border-slate-800 p-5 rounded-xl shadow-sm">
        <div class="text-slate-400 text-xs font-medium uppercase tracking-wider">Connector Mode</div>
        <div id="stat-mode" class="text-3xl font-extrabold text-indigo-400 mt-2">MOCK</div>
        <div class="text-xs text-slate-500 mt-1">Environment operational mode</div>
      </div>
    </div>

    <!-- Navigation Tabs -->
    <div class="border-b border-slate-800">
      <nav class="flex space-x-8">
        <button onclick="switchTab('queue')" id="tab-queue" class="tab-btn py-3 border-b-2 border-emerald-500 text-emerald-400 font-medium text-sm flex items-center space-x-2">
          <i class="fa-solid fa-list-check"></i>
          <span>Approval Queue</span>
          <span id="badge-queue-count" class="ml-1.5 px-2 py-0.2 bg-slate-800 text-xs rounded-full">0</span>
        </button>
        <button onclick="switchTab('bank')" id="tab-bank" class="tab-btn py-3 border-b-2 border-transparent text-slate-400 hover:text-slate-200 font-medium text-sm flex items-center space-x-2">
          <i class="fa-solid fa-book-bookmark"></i>
          <span>Content Bank</span>
        </button>
        <button onclick="switchTab('studio')" id="tab-studio" class="tab-btn py-3 border-b-2 border-transparent text-slate-400 hover:text-slate-200 font-medium text-sm flex items-center space-x-2">
          <i class="fa-solid fa-pen-nib"></i>
          <span>Post Studio</span>
        </button>
        <button onclick="switchTab('analytics')" id="tab-analytics" class="tab-btn py-3 border-b-2 border-transparent text-slate-400 hover:text-slate-200 font-medium text-sm flex items-center space-x-2">
          <i class="fa-solid fa-chart-line"></i>
          <span>Analytics & History</span>
        </button>
      </nav>
    </div>

    <!-- Section 1: Approval Queue -->
    <div id="section-queue" class="space-y-4">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold text-slate-200">Human-In-The-Loop Drafts</h2>
        <span class="text-xs text-slate-400">Items with confidence &lt; 85% or posts flagged for review</span>
      </div>
      <div id="queue-container" class="space-y-4">
        <!-- Rendered items -->
      </div>
    </div>

    <!-- Section 2: Content Bank -->
    <div id="section-bank" class="hidden space-y-4">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold text-slate-200">Curated Cybersecurity Content Bank</h2>
        <span class="text-xs text-slate-400">Pre-vetted, practitioner-level frameworks</span>
      </div>
      <div id="bank-container" class="grid grid-cols-1 md:grid-cols-2 gap-5">
        <!-- Bank cards -->
      </div>
    </div>

    <!-- Section 3: Post Studio -->
    <div id="section-studio" class="hidden space-y-6 max-w-3xl">
      <div class="bg-slate-900 border border-slate-800 p-6 rounded-xl space-y-4">
        <h3 class="text-base font-semibold text-slate-200">Generate Thought Leadership Post</h3>
        <p class="text-xs text-slate-400">Builds a grounded, 0-slop post adhering to <code class="text-emerald-400">Hook &rarr; Insight &rarr; Example &rarr; Takeaway</code>.</p>
        
        <div>
          <label class="block text-xs font-medium text-slate-300 mb-1.5">Cybersecurity Topic or Dilemma</label>
          <input type="text" id="studio-topic" placeholder="e.g. Why SOC 2 does not equal security in production" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3.5 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-emerald-500">
        </div>

        <button onclick="generateCustomPost()" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium transition flex items-center space-x-2">
          <i class="fa-solid fa-sparkles"></i>
          <span>Generate & Stage to Review</span>
        </button>

        <div id="studio-result" class="hidden mt-6 p-4 rounded-lg bg-slate-950 border border-slate-800 space-y-3">
          <div class="flex items-center justify-between text-xs text-slate-400">
            <span id="studio-result-score" class="font-semibold text-emerald-400"></span>
            <span id="studio-result-staged" class="text-amber-400"></span>
          </div>
          <pre id="studio-result-text" class="whitespace-pre-wrap font-sans text-sm text-slate-200"></pre>
        </div>
      </div>
    </div>

    <!-- Section 4: Analytics -->
    <div id="section-analytics" class="hidden space-y-6">
      <div class="bg-slate-900 border border-slate-800 p-6 rounded-xl space-y-4">
        <h3 class="text-base font-semibold text-slate-200">Recent Activity Stream</h3>
        <div class="overflow-x-auto">
          <table class="w-full text-left text-sm text-slate-400">
            <thead class="text-xs uppercase bg-slate-950/50 text-slate-500 border-b border-slate-800">
              <tr>
                <th class="py-3 px-4">Time</th>
                <th class="py-3 px-4">Action</th>
                <th class="py-3 px-4">Snippet / Target</th>
              </tr>
            </thead>
            <tbody id="analytics-tbody" class="divide-y divide-slate-800 font-mono text-xs">
              <!-- Logs -->
            </tbody>
          </table>
        </div>
      </div>
    </div>

  </main>

  <script>
    let activeTab = 'queue';

    function switchTab(tab) {
      activeTab = tab;
      ['queue', 'bank', 'studio', 'analytics'].forEach(t => {
        document.getElementById(`section-${t}`).classList.add('hidden');
        document.getElementById(`tab-${t}`).className = 'tab-btn py-3 border-b-2 border-transparent text-slate-400 hover:text-slate-200 font-medium text-sm flex items-center space-x-2';
      });
      document.getElementById(`section-${tab}`).classList.remove('hidden');
      document.getElementById(`tab-${tab}`).className = 'tab-btn py-3 border-b-2 border-emerald-500 text-emerald-400 font-medium text-sm flex items-center space-x-2';

      if (tab === 'queue') loadQueue();
      if (tab === 'bank') loadBank();
      if (tab === 'analytics') loadStatus();
    }

    async function loadStatus() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();
        document.getElementById('stat-pending').innerText = data.pending_hitl;
        document.getElementById('badge-queue-count').innerText = data.pending_hitl;
        document.getElementById('stat-confidence').innerText = data.metrics.avg_confidence + '%';
        document.getElementById('stat-engagements').innerText = data.metrics.total_likes + data.metrics.total_comments;
        document.getElementById('stat-mode').innerText = data.mode;

        if (data.in_backoff) {
          document.getElementById('cooldown-badge').classList.remove('hidden');
        } else {
          document.getElementById('cooldown-badge').classList.add('hidden');
        }

        // Render analytics table
        const tbody = document.getElementById('analytics-tbody');
        tbody.innerHTML = '';
        data.metrics.recent_actions.forEach(a => {
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td class="py-2.5 px-4 text-slate-500">${a.time}</td>
            <td class="py-2.5 px-4 font-bold ${a.type === 'likes' ? 'text-cyan-400' : 'text-emerald-400'}">${a.type.toUpperCase()}</td>
            <td class="py-2.5 px-4 text-slate-300 font-sans">${a.snippet}</td>
          `;
          tbody.appendChild(tr);
        });
      } catch (e) {
        console.error(e);
      }
    }

    async function loadQueue() {
      try {
        const res = await fetch('/api/queue');
        const items = await res.json();
        const container = document.getElementById('queue-container');
        container.innerHTML = '';

        if (items.length === 0) {
          container.innerHTML = `
            <div class="p-8 text-center bg-slate-900 border border-slate-800 rounded-xl">
              <i class="fa-solid fa-circle-check text-emerald-400 text-3xl mb-2"></i>
              <p class="text-sm text-slate-300 font-medium">Approval Queue is Clean!</p>
              <p class="text-xs text-slate-500 mt-1">No drafts waiting for manual review.</p>
            </div>
          `;
          return;
        }

        items.forEach(item => {
          const card = document.createElement('div');
          card.className = 'bg-slate-900 border border-slate-800 p-5 rounded-xl space-y-3';
          card.innerHTML = `
            <div class="flex items-center justify-between">
              <div class="flex items-center space-x-2">
                <span class="px-2 py-0.5 rounded text-xs font-bold uppercase bg-slate-800 ${item.action_type === 'comment' ? 'text-emerald-400' : 'text-cyan-400'} border border-slate-700">${item.action_type}</span>
                <span class="text-xs text-slate-400">ID: ${item.id}</span>
              </div>
              <span class="text-xs font-semibold px-2 py-0.5 rounded ${item.confidence_score >= 85 ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' : 'bg-amber-950 text-amber-400 border border-amber-800'}">
                ${item.confidence_score}% Confidence
              </span>
            </div>

            ${item.target_author ? `<div class="text-xs text-slate-400 font-medium">Target Author: <span class="text-slate-200">${item.target_author}</span></div>` : ''}
            ${item.original_content ? `<blockquote class="text-xs italic text-slate-400 border-l-2 border-slate-700 pl-3 py-1">"${item.original_content}..."</blockquote>` : ''}

            <div>
              <label class="block text-xs font-medium text-slate-400 mb-1">Proposed Draft Content:</label>
              <textarea id="draft-text-${item.id}" rows="3" class="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-sm text-slate-100 focus:outline-none focus:border-emerald-500">${item.draft_content}</textarea>
            </div>

            <div class="flex items-center justify-between pt-2 border-t border-slate-800/80">
              <span class="text-xs text-slate-500">${item.reason}</span>
              <div class="flex space-x-2">
                <button onclick="rejectItem('${item.id}')" class="px-3 py-1.5 rounded-lg bg-red-950/60 hover:bg-red-900/80 text-red-400 border border-red-800/50 text-xs font-medium transition">
                  Reject
                </button>
                <button onclick="approveItem('${item.id}')" class="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium transition shadow-md shadow-emerald-950">
                  Approve & Dispatch
                </button>
              </div>
            </div>
          `;
          container.appendChild(card);
        });
      } catch (e) {
        console.error(e);
      }
    }

    async function approveItem(id) {
      const textarea = document.getElementById(`draft-text-${id}`);
      if (textarea) {
        await fetch(`/api/queue/${id}/edit`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ content: textarea.value })
        });
      }
      await fetch(`/api/queue/${id}/approve`, { method: 'POST' });
      loadQueue();
      loadStatus();
    }

    async function rejectItem(id) {
      await fetch(`/api/queue/${id}/reject`, { method: 'POST' });
      loadQueue();
      loadStatus();
    }

    async function loadBank() {
      try {
        const res = await fetch('/api/bank');
        const posts = await res.json();
        const container = document.getElementById('bank-container');
        container.innerHTML = '';

        posts.forEach(p => {
          const card = document.createElement('div');
          card.className = 'bg-slate-900 border border-slate-800 p-5 rounded-xl flex flex-col justify-between space-y-4';
          card.innerHTML = `
            <div>
              <div class="flex items-center justify-between mb-2">
                <span class="text-xs font-bold text-emerald-400 uppercase tracking-wider">${p.sub_domain}</span>
                <span class="text-xs font-mono text-slate-500">${p.id}</span>
              </div>
              <h4 class="font-bold text-sm text-slate-100 mb-2">${p.topic}</h4>
              <p class="text-xs text-slate-400 leading-relaxed whitespace-pre-wrap">${p.content.trim()}</p>
            </div>
            <div class="flex items-center justify-between pt-3 border-t border-slate-800">
              <span class="text-[10px] text-slate-500">${p.key_metrics.join(' • ')}</span>
              <button onclick="stageBankPost('${p.id}')" class="px-3 py-1 bg-slate-800 hover:bg-emerald-600 text-slate-200 hover:text-white rounded text-xs font-medium transition">
                Stage to Review
              </button>
            </div>
          `;
          container.appendChild(card);
        });
      } catch (e) {
        console.error(e);
      }
    }

    async function stageBankPost(id) {
      await fetch(`/api/bank/${id}/stage`, { method: 'POST' });
      alert(`Bank post ${id} staged to approval queue!`);
      loadStatus();
    }

    async function generateCustomPost() {
      const topic = document.getElementById('studio-topic').value;
      if (!topic) return alert('Please enter a topic');

      const res = await fetch('/api/post/generate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ topic: topic, stage_to_hitl: true })
      });
      const data = await res.json();

      document.getElementById('studio-result').classList.remove('hidden');
      document.getElementById('studio-result-score').innerText = `Tone Score: ${data.confidence}% (Anti-Slop Passed)`;
      document.getElementById('studio-result-staged').innerText = `Queued as [${data.staged_id}]`;
      document.getElementById('studio-result-text').innerText = data.draft;
      loadStatus();
    }

    async function triggerScan() {
      await fetch('/api/run', { method: 'POST' });
      alert('Autonomous engagement loop initiated in background!');
      setTimeout(() => {
        loadQueue();
        loadStatus();
      }, 1500);
    }

    // Initial load
    loadStatus();
    loadQueue();
  </script>
</body>
</html>
"""
