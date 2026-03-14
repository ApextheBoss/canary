#!/usr/bin/env python3
"""Canary Dashboard — FastAPI web UI for LLM drift monitoring."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

DB_PATH = Path(__file__).parent / "drift.db"

app = FastAPI(title="Canary — LLM Drift Monitor")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── API endpoints ──────────────────────────────────────────


@app.get("/api/providers")
def api_providers():
    """List all providers with data."""
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT provider FROM daily_scores ORDER BY provider").fetchall()
    conn.close()
    return [r["provider"] for r in rows]


@app.get("/api/history")
def api_history(days: int = 30):
    """Daily scores for all providers, last N days."""
    conn = get_db()
    rows = conn.execute("""
        SELECT date, provider, category, avg_score, num_tests, avg_latency_ms
        FROM daily_scores
        WHERE date >= date('now', ?)
        ORDER BY date, provider, category
    """, (f"-{days} days",)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/summary")
def api_summary():
    """Latest run summary per provider."""
    conn = get_db()
    rows = conn.execute("""
        SELECT provider,
               AVG(avg_score) as overall_score,
               AVG(avg_latency_ms) as overall_latency,
               date
        FROM daily_scores
        WHERE date = (SELECT MAX(date) FROM daily_scores)
        GROUP BY provider
        ORDER BY overall_score DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/drift")
def api_drift(days: int = 7, threshold: float = 10):
    """Drift alerts: categories where score changed significantly."""
    conn = get_db()
    today = conn.execute("SELECT MAX(date) FROM daily_scores").fetchone()[0]
    if not today:
        conn.close()
        return []

    today_scores = conn.execute(
        "SELECT provider, category, avg_score FROM daily_scores WHERE date = ?", (today,)
    ).fetchall()

    alerts = []
    for row in today_scores:
        hist = conn.execute("""
            SELECT AVG(avg_score) FROM daily_scores
            WHERE provider = ? AND category = ? AND date < ?
            ORDER BY date DESC LIMIT ?
        """, (row["provider"], row["category"], today, days)).fetchone()
        if hist and hist[0] is not None:
            diff = row["avg_score"] - hist[0]
            if abs(diff) >= threshold:
                alerts.append({
                    "provider": row["provider"],
                    "category": row["category"],
                    "today": row["avg_score"],
                    "historical_avg": round(hist[0], 1),
                    "diff": round(diff, 1),
                    "direction": "improved" if diff > 0 else "degraded",
                })
    conn.close()
    return alerts


@app.get("/api/runs/latest")
def api_latest_runs(limit: int = 50):
    """Latest individual test results."""
    conn = get_db()
    rows = conn.execute("""
        SELECT run_id, timestamp, provider, prompt_id, category, score, latency_ms, scoring_details, error
        FROM runs ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/costs")
def api_costs(days: int = 30):
    """Cost per provider per day (aggregated from runs with cost_usd)."""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT date(timestamp) as date, provider,
                   SUM(cost_usd) as total_cost,
                   COUNT(*) as num_calls
            FROM runs
            WHERE cost_usd IS NOT NULL
              AND date(timestamp) >= date('now', ?)
            GROUP BY date(timestamp), provider
            ORDER BY date, provider
        """, (f"-{days} days",)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        conn.close()
        return []


# ── HTML Dashboard ─────────────────────────────────────────


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>🐤 Canary — LLM Drift Monitor</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: #0d1117; color: #e6edf3; padding: 20px; }
  h1 { font-size: 1.8rem; margin-bottom: 4px; }
  .subtitle { color: #8b949e; margin-bottom: 24px; font-size: 0.95rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; }
  .card h3 { font-size: 0.85rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }
  .card .value { font-size: 2rem; font-weight: 700; }
  .good { color: #3fb950; }
  .warn { color: #d29922; }
  .bad { color: #f85149; }
  .chart-container { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 24px; }
  .chart-container h2 { font-size: 1.1rem; margin-bottom: 16px; }
  canvas { max-height: 350px; }
  table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
  th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #21262d; }
  th { color: #8b949e; font-weight: 600; font-size: 0.8rem; text-transform: uppercase; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
  .badge-good { background: #0d3520; color: #3fb950; }
  .badge-warn { background: #3d2e00; color: #d29922; }
  .badge-bad { background: #3d1214; color: #f85149; }
  .alerts { margin-bottom: 24px; }
  .alert { background: #3d1214; border: 1px solid #f85149; border-radius: 8px; padding: 14px 18px; margin-bottom: 8px; }
  .alert.improved { background: #0d3520; border-color: #3fb950; }
  .alert .title { font-weight: 600; margin-bottom: 4px; }
  .alert .detail { font-size: 0.85rem; color: #8b949e; }
  .empty { text-align: center; color: #8b949e; padding: 40px; }
  .loading { text-align: center; padding: 60px; color: #8b949e; }
  #app { max-width: 1100px; margin: 0 auto; }
</style>
</head>
<body>
<div id="app">
  <h1>🐤 Canary</h1>
  <p class="subtitle">LLM Drift Monitor — Know when your AI provider silently degrades</p>
  <div id="content" class="loading">Loading dashboard…</div>
</div>
<script>
const COLORS = [
  '#58a6ff','#3fb950','#d29922','#f85149','#bc8cff','#79c0ff','#56d364','#e3b341','#ff7b72','#d2a8ff'
];

function scoreBadge(score) {
  if (score >= 85) return `<span class="badge badge-good">${score.toFixed(1)}</span>`;
  if (score >= 60) return `<span class="badge badge-warn">${score.toFixed(1)}</span>`;
  return `<span class="badge badge-bad">${score.toFixed(1)}</span>`;
}

function scoreClass(score) {
  if (score >= 85) return 'good';
  if (score >= 60) return 'warn';
  return 'bad';
}

async function load() {
  const [summary, history, drift, costs] = await Promise.all([
    fetch('/api/summary').then(r=>r.json()),
    fetch('/api/history?days=30').then(r=>r.json()),
    fetch('/api/drift').then(r=>r.json()),
    fetch('/api/costs?days=30').then(r=>r.json()),
  ]);

  if (!summary.length && !history.length) {
    document.getElementById('content').innerHTML = `
      <div class="empty">
        <h2>No data yet</h2>
        <p style="margin-top:12px">Run <code>python runner.py --providers openai/gpt-4o</code> to generate your first test data.</p>
      </div>`;
    return;
  }

  let html = '';

  // Summary cards
  html += '<div class="grid">';
  for (const s of summary) {
    html += `<div class="card">
      <h3>${s.provider}</h3>
      <div class="value ${scoreClass(s.overall_score)}">${s.overall_score.toFixed(1)}</div>
      <div style="color:#8b949e;font-size:0.85rem;margin-top:4px">${s.overall_latency.toFixed(0)}ms avg · ${s.date}</div>
    </div>`;
  }
  html += '</div>';

  // Drift alerts
  if (drift.length) {
    html += '<div class="alerts">';
    for (const a of drift) {
      const cls = a.direction === 'improved' ? 'improved' : '';
      const emoji = a.direction === 'improved' ? '📈' : '📉';
      html += `<div class="alert ${cls}">
        <div class="title">${emoji} ${a.provider} / ${a.category}: ${a.direction} by ${Math.abs(a.diff).toFixed(1)} pts</div>
        <div class="detail">Today: ${a.today.toFixed(1)} | Historical avg: ${a.historical_avg}</div>
      </div>`;
    }
    html += '</div>';
  }

  // Historical chart
  // Group history by date+provider → overall avg
  const byDateProvider = {};
  const providers = [...new Set(history.map(h=>h.provider))];
  const dates = [...new Set(history.map(h=>h.date))].sort();

  for (const h of history) {
    const key = `${h.date}|${h.provider}`;
    if (!byDateProvider[key]) byDateProvider[key] = [];
    byDateProvider[key].push(h.avg_score);
  }

  html += `<div class="chart-container"><h2>Score History (30 days)</h2><canvas id="historyChart"></canvas></div>`;

  // Category breakdown chart
  html += `<div class="chart-container"><h2>Latest Scores by Category</h2><canvas id="categoryChart"></canvas></div>`;

  // Cost tracking section
  if (costs && costs.length) {
    const costByProvider = {};
    for (const c of costs) {
      if (!costByProvider[c.provider]) costByProvider[c.provider] = 0;
      costByProvider[c.provider] += c.total_cost;
    }
    html += '<div class="chart-container"><h2>💰 Cost Tracking (30 days)</h2><table>';
    html += '<thead><tr><th>Provider</th><th>Total Cost</th><th>API Calls</th><th>Avg $/call</th></tr></thead><tbody>';
    const totalCalls = {};
    for (const c of costs) {
      totalCalls[c.provider] = (totalCalls[c.provider] || 0) + c.num_calls;
    }
    for (const [p, cost] of Object.entries(costByProvider).sort((a,b) => b[1]-a[1])) {
      const calls = totalCalls[p] || 1;
      html += `<tr><td>${p}</td><td>$${cost.toFixed(4)}</td><td>${calls}</td><td>$${(cost/calls).toFixed(6)}</td></tr>`;
    }
    html += '</tbody></table></div>';
  }

  // Recent runs table
  html += `<div class="chart-container"><h2>Latest Summary</h2><table>
    <thead><tr><th>Provider</th><th>Score</th><th>Latency</th><th>Date</th></tr></thead><tbody>`;
  for (const s of summary) {
    html += `<tr><td>${s.provider}</td><td>${scoreBadge(s.overall_score)}</td><td>${s.overall_latency.toFixed(0)}ms</td><td>${s.date}</td></tr>`;
  }
  html += '</tbody></table></div>';

  document.getElementById('content').innerHTML = html;

  // Render history chart
  const datasets = providers.map((p, i) => ({
    label: p,
    data: dates.map(d => {
      const vals = byDateProvider[`${d}|${p}`];
      return vals ? vals.reduce((a,b)=>a+b,0)/vals.length : null;
    }),
    borderColor: COLORS[i % COLORS.length],
    backgroundColor: COLORS[i % COLORS.length] + '22',
    tension: 0.3,
    fill: false,
    spanGaps: true,
  }));

  new Chart(document.getElementById('historyChart'), {
    type: 'line',
    data: { labels: dates, datasets },
    options: {
      responsive: true,
      scales: {
        y: { min: 0, max: 100, grid: { color: '#21262d' }, ticks: { color: '#8b949e' } },
        x: { grid: { color: '#21262d' }, ticks: { color: '#8b949e', maxTicksLimit: 10 } }
      },
      plugins: { legend: { labels: { color: '#e6edf3' } } }
    }
  });

  // Category chart — latest date only
  const latestDate = dates[dates.length - 1];
  const latestData = history.filter(h => h.date === latestDate);
  const categories = [...new Set(latestData.map(h => h.category))].sort();

  const catDatasets = providers.map((p, i) => ({
    label: p,
    data: categories.map(c => {
      const match = latestData.find(h => h.provider === p && h.category === c);
      return match ? match.avg_score : null;
    }),
    backgroundColor: COLORS[i % COLORS.length] + 'cc',
    borderColor: COLORS[i % COLORS.length],
    borderWidth: 1,
  }));

  new Chart(document.getElementById('categoryChart'), {
    type: 'bar',
    data: { labels: categories, datasets: catDatasets },
    options: {
      responsive: true,
      scales: {
        y: { min: 0, max: 100, grid: { color: '#21262d' }, ticks: { color: '#8b949e' } },
        x: { grid: { color: '#21262d' }, ticks: { color: '#8b949e' } }
      },
      plugins: { legend: { labels: { color: '#e6edf3' } } }
    }
  });
}

load();
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return DASHBOARD_HTML


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
