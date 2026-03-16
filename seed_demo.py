#!/usr/bin/env python3
"""Seed drift.db with realistic demo data for dashboard development."""

import random
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "drift.db"

PROVIDERS = [
    "openai/gpt-4o",
    "anthropic/claude-3.5-sonnet",
    "google/gemini-2.0-flash-thinking-exp",
]

CATEGORIES = ["code", "reasoning", "math", "instruction_following", "consistency", "safety", "multilingual", "rag"]

# Base scores per provider (some better at certain things)
BASE_SCORES = {
    "openai/gpt-4o": {"code": 92, "reasoning": 90, "math": 88, "instruction_following": 95, "consistency": 91, "safety": 97, "multilingual": 86, "rag": 90},
    "anthropic/claude-3.5-sonnet": {"code": 95, "reasoning": 94, "math": 90, "instruction_following": 93, "consistency": 96, "safety": 99, "multilingual": 91, "rag": 93},
    "google/gemini-2.0-flash-thinking-exp": {"code": 85, "reasoning": 88, "math": 92, "instruction_following": 80, "consistency": 82, "safety": 90, "multilingual": 88, "rag": 85},
}

BASE_LATENCY = {
    "openai/gpt-4o": 800,
    "anthropic/claude-3.5-sonnet": 1100,
    "google/gemini-2.0-flash-thinking-exp": 600,
}


def seed():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            provider TEXT NOT NULL,
            category TEXT NOT NULL,
            avg_score REAL NOT NULL,
            num_tests INTEGER NOT NULL,
            avg_latency_ms REAL NOT NULL
        )
    """)
    # Clear old demo data
    conn.execute("DELETE FROM daily_scores")
    conn.commit()

    now = datetime.now(timezone.utc)
    days = 21

    for d in range(days):
        date = (now - timedelta(days=days - 1 - d)).strftime("%Y-%m-%d")
        for provider in PROVIDERS:
            for cat in CATEGORIES:
                base = BASE_SCORES[provider][cat]
                # Add some drift: GPT-4o reasoning degrades over time
                drift = 0
                if provider == "openai/gpt-4o" and cat == "reasoning" and d > 14:
                    drift = -(d - 14) * 2.5  # drops ~2.5 pts/day after day 14
                
                score = max(0, min(100, base + random.gauss(0, 3) + drift))
                latency = max(100, BASE_LATENCY[provider] + random.gauss(0, 100))

                conn.execute("""
                    INSERT INTO daily_scores (date, provider, category, avg_score, num_tests, avg_latency_ms)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (date, provider, cat, round(score, 1), 4, round(latency, 0)))

    conn.commit()
    conn.close()
    print(f"✅ Seeded {days} days × {len(PROVIDERS)} providers × {len(CATEGORIES)} categories = {days * len(PROVIDERS) * len(CATEGORIES)} rows")


if __name__ == "__main__":
    seed()
