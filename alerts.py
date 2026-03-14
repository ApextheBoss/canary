#!/usr/bin/env python3
"""Canary Alerts — Send drift notifications via webhooks."""

import json
import os
from urllib.request import Request, urlopen


def send_discord(webhook_url: str, alerts: list, summary: list):
    """Send drift alerts to a Discord channel via webhook."""
    if not alerts and not summary:
        return

    embeds = []

    # Summary embed
    if summary:
        fields = []
        for s in summary:
            score = s.get("overall_score", 0)
            emoji = "🟢" if score >= 85 else "🟡" if score >= 60 else "🔴"
            fields.append({
                "name": f"{emoji} {s['provider']}",
                "value": f"Score: **{score:.1f}** | Latency: {s.get('overall_latency', 0):.0f}ms",
                "inline": True,
            })
        embeds.append({
            "title": "🐤 Canary — Daily Quality Report",
            "color": 0x58A6FF,
            "fields": fields,
            "footer": {"text": f"Date: {summary[0].get('date', 'unknown')}"},
        })

    # Drift alerts embed
    if alerts:
        desc_lines = []
        for a in alerts:
            emoji = "📈" if a["direction"] == "improved" else "📉"
            desc_lines.append(
                f"{emoji} **{a['provider']}** / {a['category']}: "
                f"{a['direction']} by {abs(a['diff']):.1f} pts "
                f"(today: {a['today']:.1f}, avg: {a['historical_avg']})"
            )
        embeds.append({
            "title": "⚠️ Drift Alerts",
            "description": "\n".join(desc_lines),
            "color": 0xF85149 if any(a["direction"] == "degraded" for a in alerts) else 0x3FB950,
        })

    payload = json.dumps({"embeds": embeds}).encode()
    req = Request(webhook_url, data=payload, headers={"Content-Type": "application/json"})
    urlopen(req, timeout=10)


def send_slack(webhook_url: str, alerts: list, summary: list):
    """Send drift alerts to a Slack channel via webhook."""
    blocks = []

    if summary:
        lines = ["*🐤 Canary — Daily Quality Report*\n"]
        for s in summary:
            score = s.get("overall_score", 0)
            emoji = "🟢" if score >= 85 else "🟡" if score >= 60 else "🔴"
            lines.append(f"{emoji} *{s['provider']}*: {score:.1f} ({s.get('overall_latency', 0):.0f}ms)")
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}})

    if alerts:
        lines = ["*⚠️ Drift Alerts*\n"]
        for a in alerts:
            emoji = "📈" if a["direction"] == "improved" else "📉"
            lines.append(
                f"{emoji} *{a['provider']}* / {a['category']}: "
                f"{a['direction']} by {abs(a['diff']):.1f} pts"
            )
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}})

    if not blocks:
        return

    payload = json.dumps({"blocks": blocks}).encode()
    req = Request(webhook_url, data=payload, headers={"Content-Type": "application/json"})
    urlopen(req, timeout=10)


def send_generic(webhook_url: str, alerts: list, summary: list):
    """Send a generic JSON POST with alert data."""
    payload = json.dumps({
        "source": "canary",
        "summary": summary,
        "alerts": alerts,
    }).encode()
    req = Request(webhook_url, data=payload, headers={"Content-Type": "application/json"})
    urlopen(req, timeout=10)


def send_alerts(alerts: list, summary: list = None):
    """Send alerts to all configured webhook destinations.
    
    Environment variables:
      CANARY_DISCORD_WEBHOOK  — Discord webhook URL
      CANARY_SLACK_WEBHOOK    — Slack webhook URL
      CANARY_WEBHOOK          — Generic JSON webhook URL
    """
    summary = summary or []
    sent = []

    discord_url = os.environ.get("CANARY_DISCORD_WEBHOOK")
    if discord_url:
        try:
            send_discord(discord_url, alerts, summary)
            sent.append("discord")
        except Exception as e:
            print(f"⚠️  Discord webhook failed: {e}")

    slack_url = os.environ.get("CANARY_SLACK_WEBHOOK")
    if slack_url:
        try:
            send_slack(slack_url, alerts, summary)
            sent.append("slack")
        except Exception as e:
            print(f"⚠️  Slack webhook failed: {e}")

    generic_url = os.environ.get("CANARY_WEBHOOK")
    if generic_url:
        try:
            send_generic(generic_url, alerts, summary)
            sent.append("generic")
        except Exception as e:
            print(f"⚠️  Generic webhook failed: {e}")

    return sent
