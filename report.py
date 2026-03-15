#!/usr/bin/env python3
"""Canary — Weekly Quality Report Generator.

Generates a Markdown report summarizing LLM quality trends over the past week.
Can output to stdout, file, or post to webhook.

Usage:
    python report.py                    # Print to stdout
    python report.py -o report.md       # Save to file
    python report.py --days 14          # Custom period
    python report.py --webhook          # Post to configured webhooks
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

DB_PATH = Path(__file__).parent / "drift.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def generate_report(days: int = 7) -> str:
    conn = get_db()

    # Date range
    latest = conn.execute("SELECT MAX(date) FROM daily_scores").fetchone()[0]
    if not latest:
        return "# 🐤 Canary Report\n\nNo data available. Run `python runner.py` first.\n"

    earliest = conn.execute(
        "SELECT MIN(date) FROM daily_scores WHERE date >= date(?, ?)",
        (latest, f"-{days} days"),
    ).fetchone()[0]

    lines = [
        f"# 🐤 Canary — Quality Report",
        f"",
        f"**Period:** {earliest or '?'} → {latest} ({days} days)",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"",
        f"---",
        f"",
    ]

    # ── Overall scores (latest) ──
    summary = conn.execute("""
        SELECT provider,
               ROUND(AVG(avg_score), 1) as score,
               ROUND(AVG(avg_latency_ms), 0) as latency
        FROM daily_scores WHERE date = ?
        GROUP BY provider ORDER BY score DESC
    """, (latest,)).fetchall()

    lines.append("## 📊 Latest Scores\n")
    lines.append("| Provider | Score | Latency |")
    lines.append("|----------|------:|--------:|")
    for s in summary:
        icon = "🟢" if s["score"] >= 85 else ("🟡" if s["score"] >= 60 else "🔴")
        lines.append(f"| {icon} {s['provider']} | {s['score']} | {int(s['latency'])}ms |")
    lines.append("")

    # ── Trends (start vs end of period) ──
    start_scores = conn.execute("""
        SELECT provider, ROUND(AVG(avg_score), 1) as score
        FROM daily_scores WHERE date = ?
        GROUP BY provider
    """, (earliest,)).fetchall()
    start_map = {r["provider"]: r["score"] for r in start_scores}

    end_scores = conn.execute("""
        SELECT provider, ROUND(AVG(avg_score), 1) as score
        FROM daily_scores WHERE date = ?
        GROUP BY provider
    """, (latest,)).fetchall()

    if start_map and len(end_scores) > 0:
        lines.append("## 📈 Trends\n")
        lines.append("| Provider | Start | End | Change |")
        lines.append("|----------|------:|----:|-------:|")
        for e in end_scores:
            start = start_map.get(e["provider"])
            if start is not None:
                diff = e["score"] - start
                arrow = "↑" if diff > 0 else ("↓" if diff < 0 else "→")
                sign = "+" if diff > 0 else ""
                lines.append(f"| {e['provider']} | {start} | {e['score']} | {arrow} {sign}{diff:.1f} |")
        lines.append("")

    # ── Drift alerts ──
    alerts = []
    today_scores = conn.execute(
        "SELECT provider, category, avg_score FROM daily_scores WHERE date = ?", (latest,)
    ).fetchall()

    for row in today_scores:
        hist = conn.execute("""
            SELECT AVG(avg_score) FROM daily_scores
            WHERE provider = ? AND category = ? AND date < ? AND date >= date(?, ?)
        """, (row["provider"], row["category"], latest, latest, f"-{days} days")).fetchone()
        if hist and hist[0] is not None:
            diff = row["avg_score"] - hist[0]
            if abs(diff) >= 10:
                alerts.append({
                    "provider": row["provider"],
                    "category": row["category"],
                    "today": row["avg_score"],
                    "avg": round(hist[0], 1),
                    "diff": round(diff, 1),
                })

    if alerts:
        lines.append("## ⚠️ Drift Alerts\n")
        for a in alerts:
            emoji = "📈" if a["diff"] > 0 else "📉"
            direction = "improved" if a["diff"] > 0 else "degraded"
            lines.append(f"- {emoji} **{a['provider']}** / {a['category']}: {direction} by {abs(a['diff'])} pts (now {a['today']}, was {a['avg']})")
        lines.append("")
    else:
        lines.append("## ✅ No Drift Alerts\n")
        lines.append("All providers are within normal ranges.\n")

    # ── Category breakdown (latest) ──
    categories = conn.execute("""
        SELECT provider, category, avg_score
        FROM daily_scores WHERE date = ?
        ORDER BY provider, category
    """, (latest,)).fetchall()

    if categories:
        lines.append("## 🏷️ Category Breakdown (Latest)\n")
        providers_seen = {}
        for c in categories:
            if c["provider"] not in providers_seen:
                providers_seen[c["provider"]] = []
            providers_seen[c["provider"]].append(c)

        for provider, cats in providers_seen.items():
            lines.append(f"**{provider}**")
            for c in cats:
                bar_len = int(c["avg_score"] / 5)
                bar = "█" * bar_len + "░" * (20 - bar_len)
                lines.append(f"  {c['category']:20s} {bar} {c['avg_score']:.1f}")
            lines.append("")

    # ── Cost summary ──
    try:
        costs = conn.execute("""
            SELECT provider,
                   ROUND(SUM(cost_usd), 4) as total,
                   COUNT(*) as calls
            FROM runs
            WHERE cost_usd IS NOT NULL
              AND date(timestamp) >= date(?, ?)
            GROUP BY provider ORDER BY total DESC
        """, (latest, f"-{days} days")).fetchall()

        if costs:
            lines.append("## 💰 Cost Summary\n")
            lines.append("| Provider | Total | Calls | Avg/Call |")
            lines.append("|----------|------:|------:|--------:|")
            grand_total = 0
            for c in costs:
                avg = c["total"] / c["calls"] if c["calls"] else 0
                lines.append(f"| {c['provider']} | ${c['total']:.4f} | {c['calls']} | ${avg:.6f} |")
                grand_total += c["total"]
            lines.append(f"| **Total** | **${grand_total:.4f}** | | |")
            lines.append("")
    except Exception:
        pass

    # ── Test volume ──
    volume = conn.execute("""
        SELECT COUNT(*) as total, COUNT(DISTINCT date) as days_with_data
        FROM daily_scores
        WHERE date >= date(?, ?)
    """, (latest, f"-{days} days")).fetchone()

    lines.append("---\n")
    lines.append(f"*{volume['total']} data points across {volume['days_with_data']} days · Generated by [Canary](https://github.com/ApextheBoss/canary)*\n")

    conn.close()
    return "\n".join(lines)


def post_to_webhook(report: str):
    """Post report to configured webhooks."""
    sent = False

    discord_url = os.environ.get("CANARY_DISCORD_WEBHOOK")
    if discord_url:
        # Discord has 2000 char limit, truncate if needed
        content = report[:1990]
        payload = json.dumps({"content": f"```md\n{content}\n```"}).encode()
        req = Request(discord_url, data=payload, headers={"Content-Type": "application/json"})
        urlopen(req, timeout=10)
        print("✅ Posted to Discord")
        sent = True

    slack_url = os.environ.get("CANARY_SLACK_WEBHOOK")
    if slack_url:
        payload = json.dumps({"text": f"```\n{report}\n```"}).encode()
        req = Request(slack_url, data=payload, headers={"Content-Type": "application/json"})
        urlopen(req, timeout=10)
        print("✅ Posted to Slack")
        sent = True

    generic_url = os.environ.get("CANARY_WEBHOOK")
    if generic_url:
        payload = json.dumps({"type": "weekly_report", "report": report}).encode()
        req = Request(generic_url, data=payload, headers={"Content-Type": "application/json"})
        urlopen(req, timeout=10)
        print("✅ Posted to webhook")
        sent = True

    if not sent:
        print("⚠️  No webhook URLs configured. Set CANARY_DISCORD_WEBHOOK, CANARY_SLACK_WEBHOOK, or CANARY_WEBHOOK.")


def main():
    parser = argparse.ArgumentParser(description="Canary — Weekly Quality Report")
    parser.add_argument("--days", type=int, default=7, help="Report period in days (default: 7)")
    parser.add_argument("-o", "--output", type=str, help="Output file path")
    parser.add_argument("--webhook", action="store_true", help="Post report to configured webhooks")
    args = parser.parse_args()

    report = generate_report(args.days)

    if args.output:
        Path(args.output).write_text(report)
        print(f"📝 Report saved to {args.output}")
    elif not args.webhook:
        print(report)

    if args.webhook:
        post_to_webhook(report)


if __name__ == "__main__":
    main()
