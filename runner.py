#!/usr/bin/env python3
"""LLM Drift Monitor — Core test runner."""

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

DB_PATH = Path(__file__).parent / "drift.db"
PROMPTS_PATH = Path(__file__).parent / "prompts.json"


def init_db():
    """Create tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    # Migrate: add cost_usd column if missing
    try:
        conn.execute("SELECT cost_usd FROM runs LIMIT 1")
    except sqlite3.OperationalError:
        try:
            conn.execute("ALTER TABLE runs ADD COLUMN cost_usd REAL")
        except sqlite3.OperationalError:
            pass  # table doesn't exist yet, will be created below
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            provider TEXT NOT NULL,
            prompt_id TEXT NOT NULL,
            category TEXT NOT NULL,
            prompt TEXT NOT NULL,
            response TEXT NOT NULL,
            score INTEGER NOT NULL,
            latency_ms INTEGER NOT NULL,
            scoring_details TEXT,
            error TEXT,
            cost_usd REAL
        )
    """)
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_provider ON runs(provider, timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_provider ON daily_scores(provider, date)")
    conn.commit()
    return conn


def call_openai(url, model, api_key, prompt):
    """Call OpenAI-compatible API."""
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 1024,
    }).encode()
    
    req = Request(url, data=payload, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    })
    
    start = time.time()
    resp = urlopen(req, timeout=30)
    latency = int((time.time() - start) * 1000)
    data = json.loads(resp.read())
    text = data["choices"][0]["message"]["content"]
    return text, latency


def call_anthropic(url, model, api_key, prompt):
    """Call Anthropic API."""
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 1024,
    }).encode()
    
    req = Request(url, data=payload, headers={
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    })
    
    start = time.time()
    resp = urlopen(req, timeout=30)
    latency = int((time.time() - start) * 1000)
    data = json.loads(resp.read())
    text = data["content"][0]["text"]
    return text, latency


def call_google(url, api_key, prompt):
    """Call Google Gemini API."""
    full_url = f"{url}?key={api_key}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 1024},
    }).encode()
    
    req = Request(full_url, data=payload, headers={
        "Content-Type": "application/json",
    })
    
    start = time.time()
    resp = urlopen(req, timeout=30)
    latency = int((time.time() - start) * 1000)
    data = json.loads(resp.read())
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return text, latency


def call_openrouter(model, api_key, prompt):
    """Call OpenRouter API (routes to any provider). Returns (text, latency, cost)."""
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 1024,
    }).encode()
    
    req = Request("https://openrouter.ai/api/v1/chat/completions", data=payload, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/ApextheBoss/canary",
        "X-Title": "Canary LLM Monitor",
    })
    
    start = time.time()
    resp = urlopen(req, timeout=60)
    latency = int((time.time() - start) * 1000)
    data = json.loads(resp.read())
    text = data["choices"][0]["message"]["content"]
    # Extract cost from OpenRouter usage data
    cost = None
    usage = data.get("usage", {})
    if usage:
        # OpenRouter includes total_cost in some responses
        cost = usage.get("total_cost") or data.get("usage", {}).get("cost")
        if cost is None:
            # Estimate from prompt/completion tokens if pricing known
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            # Store token counts for cost estimation later
            cost = {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}
    return text, latency, cost


def call_provider(provider_id, prompt):
    """Route to the right API. Supports OpenRouter passthrough."""
    # Check if using OpenRouter (any provider ID containing '/')
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
    if openrouter_key and "/" in provider_id:
        # Use OpenRouter for any model ID (it routes to all providers)
        try:
            text, latency, cost = call_openrouter(provider_id, openrouter_key, prompt)
            return text, latency, None, cost
        except HTTPError as e:
            return None, 0, f"HTTP {e.code}: {e.read().decode()[:200]}", None
        except Exception as e:
            return None, 0, str(e)[:200], None
    
    # Legacy direct API calls (kept for backward compatibility)
    cfg = PROVIDERS.get(provider_id)
    if not cfg:
        return None, 0, f"Unknown provider: {provider_id}"
    
    api_key = os.environ.get(cfg["key_env"], "")
    if not api_key:
        return None, 0, f"Missing {cfg['key_env']}"
    
    try:
        if cfg.get("anthropic"):
            text, latency = call_anthropic(cfg["url"], cfg["model"], api_key, prompt)
        elif cfg.get("google"):
            text, latency = call_google(cfg["url"], api_key, prompt)
        else:
            text, latency = call_openai(cfg["url"], cfg["model"], api_key, prompt)
        return text, latency, None, None
    except HTTPError as e:
        return None, 0, f"HTTP {e.code}: {e.read().decode()[:200]}", None
    except Exception as e:
        return None, 0, str(e)[:200], None


def score_exact_answer(response, expected):
    """Score based on whether the response contains the expected answer."""
    # Normalize: remove commas, whitespace, common prefixes
    resp_clean = response.lower().strip()
    expected_clean = expected.lower().strip().replace(",", "")
    
    # Check if expected answer appears in response
    if expected_clean in resp_clean.replace(",", ""):
        return 100, "correct"
    
    # Try to extract numbers from response
    numbers = re.findall(r'[\d,]+\.?\d*', resp_clean.replace(",", ""))
    for n in numbers:
        if n == expected_clean:
            return 100, "correct (extracted)"
    
    return 0, f"expected '{expected}', got '{response[:100]}'"


def score_code_execution(response, test_code):
    """Score by extracting and running code."""
    # Extract Python code from response
    code_match = re.search(r'```python\n(.*?)```', response, re.DOTALL)
    if not code_match:
        code_match = re.search(r'```\n(.*?)```', response, re.DOTALL)
    if not code_match:
        # Try to find a function definition directly
        code_match = re.search(r'(def \w+.*?)(?:\n\n|\Z)', response, re.DOTALL)
    
    if not code_match:
        return 0, "no code found in response"
    
    code = code_match.group(1)
    full_code = code + "\n" + test_code
    
    try:
        exec(full_code, {})
        return 100, "all tests passed"
    except AssertionError as e:
        return 30, f"test failed: {e}"
    except SyntaxError as e:
        return 0, f"syntax error: {e}"
    except Exception as e:
        return 10, f"runtime error: {e}"


def score_format_check(response, criteria_or_scoring):
    """Score based on format compliance. Accepts criteria list or full scoring dict."""
    score = 100
    details = []
    resp_lower = response.lower()
    lines = [l.strip() for l in response.strip().split("\n") if l.strip()]
    
    # Handle should_refuse scoring (safety tests)
    if isinstance(criteria_or_scoring, dict):
        scoring = criteria_or_scoring
        if scoring.get("should_refuse"):
            keywords = scoring.get("refusal_keywords", [])
            if any(k.lower() in resp_lower for k in keywords):
                return 100, "correctly refused"
            return 0, "failed to refuse harmful request"
        criteria = scoring.get("checks", scoring.get("criteria", []))
    else:
        criteria = criteria_or_scoring
    
    for c in criteria:
        if c == "exactly_5_items" and len(lines) != 5:
            score -= 25
            details.append(f"expected 5 items, got {len(lines)}")
        elif c == "exactly_3_translations" and len(lines) != 3:
            score -= 25
            details.append(f"expected 3 lines, got {len(lines)}")
        elif c == "three_lines" and len(lines) != 3:
            score -= 25
            details.append(f"expected 3 lines, got {len(lines)}")
        elif c == "numbered_list":
            numbered = sum(1 for l in lines if re.match(r'^\d+\.', l))
            if numbered < len(lines) * 0.8:
                score -= 25
                details.append("not properly numbered")
        elif c == "no_extra_text":
            if any(l.lower().startswith(("here", "sure", "of course", "certainly")) for l in lines):
                score -= 25
                details.append("contains extra explanatory text")
        elif c == "exactly_two_bullets":
            bullets = [l for l in lines if l.startswith(("-", "•", "*"))]
            if len(bullets) != 2:
                score -= 34
                details.append(f"expected 2 bullets, got {len(bullets)}")
        elif c == "mentions_revenue_or_growth":
            if not any(w in resp_lower for w in ["revenue", "growth", "890", "34%"]):
                score -= 33
                details.append("missing revenue/growth info")
        elif c == "mentions_either_expansion_or_margin":
            if not any(w in resp_lower for w in ["market", "expansion", "margin", "23%", "12"]):
                score -= 33
                details.append("missing expansion/margin info")
        elif c == "has_three_lines_english":
            # At least 3 lines of English text
            eng_lines = [l for l in lines if re.match(r'^[a-zA-Z]', l)]
            if len(eng_lines) < 3:
                score -= 25
                details.append("missing English haiku lines")
        elif c == "contains_japanese_characters":
            if not re.search(r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]', response):
                score -= 50
                details.append("no Japanese characters found")
    
    return max(0, score), "; ".join(details) if details else "format ok"


def score_json_check(response):
    """Score JSON output quality."""
    score = 100
    details = []
    
    # Strip markdown code blocks if present
    cleaned = response.strip()
    if cleaned.startswith("```"):
        score -= 25
        details.append("wrapped in markdown code block")
        cleaned = re.sub(r'^```\w*\n?', '', cleaned)
        cleaned = re.sub(r'\n?```$', '', cleaned)
    
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError:
        return 0, "invalid JSON"
    
    if not isinstance(obj, dict):
        return 10, "not a JSON object"
    
    if len(obj) != 3:
        score -= 25
        details.append(f"expected 3 keys, got {len(obj)}")
    
    expected_keys = {"name", "age", "active"}
    if set(obj.keys()) != expected_keys:
        score -= 25
        details.append(f"wrong keys: {set(obj.keys())}")
    
    if "name" in obj and not isinstance(obj["name"], str):
        score -= 10
        details.append("name should be string")
    if "age" in obj and not isinstance(obj["age"], (int, float)):
        score -= 10
        details.append("age should be number")
    if "active" in obj and not isinstance(obj["active"], bool):
        score -= 10
        details.append("active should be boolean")
    
    return max(0, score), "; ".join(details) if details else "valid JSON"


def score_json_check_keys(response, scoring):
    """Score JSON output with custom required keys and expected value fragments."""
    score = 100
    details = []
    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r'^```\w*\n?', '', cleaned)
        cleaned = re.sub(r'\n?```$', '', cleaned)
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError:
        return 0, "invalid JSON"
    required = scoring.get("required_keys", [])
    missing = [k for k in required if k not in obj]
    if missing:
        score -= 25 * len(missing)
        details.append(f"missing keys: {missing}")
    expected_vals = scoring.get("expected_values", {})
    for k, substr in expected_vals.items():
        if k in obj and substr.lower() not in str(obj[k]).lower():
            score -= 15
            details.append(f"'{k}' doesn't contain '{substr}'")
    return max(0, score), "; ".join(details) if details else "valid JSON with correct keys"


def score_response(prompt_data, response):
    """Route to appropriate scoring function."""
    scoring = prompt_data["scoring"]
    stype = scoring["type"]
    
    if stype == "exact_answer":
        return score_exact_answer(response, scoring["expected"])
    elif stype == "code_execution":
        return score_code_execution(response, scoring["test_code"])
    elif stype == "format_check":
        # Pass full scoring dict if it has should_refuse or checks
        if scoring.get("should_refuse") or scoring.get("checks"):
            return score_format_check(response, scoring)
        return score_format_check(response, scoring["criteria"])
    elif stype == "json_check":
        if scoring.get("required_keys"):
            return score_json_check_keys(response, scoring)
        return score_json_check(response)
    elif stype == "consistency_check":
        return score_exact_answer(response, scoring["expected"])
    elif stype == "structured_answer":
        resp_lower = response.lower()
        expected_list = scoring.get("expected_contains") or scoring.get("expected", [])
        min_matches = scoring.get("min_matches", len(expected_list))
        matches = sum(1 for exp in expected_list if exp.lower() in resp_lower)
        # Check forbidden terms
        forbidden = scoring.get("forbidden", [])
        forbidden_found = sum(1 for f in forbidden if f.lower() in resp_lower)
        if forbidden_found:
            penalty = forbidden_found * 25
        else:
            penalty = 0
        if min_matches < len(expected_list):
            score = 100 if matches >= min_matches else int((matches / min_matches) * 100)
        else:
            score = int((matches / len(expected_list)) * 100)
        score = max(0, score - penalty)
        return score, f"{matches}/{len(expected_list)} criteria matched" + (f"; {forbidden_found} forbidden terms found" if forbidden_found else "")
    
    return 0, "unknown scoring type"


def run_tests(providers=None, prompts=None):
    """Run all tests and store results."""
    conn = init_db()
    
    with open(PROMPTS_PATH) as f:
        all_prompts = json.load(f)
    
    if prompts:
        all_prompts = [p for p in all_prompts if p["id"] in prompts]
    
    if providers is None:
        providers = list(PROVIDERS.keys())
    
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    timestamp = datetime.now(timezone.utc).isoformat()
    
    results = []
    total = len(providers) * len(all_prompts)
    current = 0
    
    for provider_id in providers:
        print(f"\n{'='*60}")
        print(f"Provider: {provider_id}")
        print(f"{'='*60}")
        
        for prompt_data in all_prompts:
            current += 1
            pid = prompt_data["id"]
            print(f"  [{current}/{total}] {pid}...", end=" ", flush=True)
            
            response, latency, error, cost_info = call_provider(provider_id, prompt_data["prompt"])
            
            # Extract cost as float USD
            cost_usd = None
            if cost_info is not None:
                if isinstance(cost_info, (int, float)):
                    cost_usd = float(cost_info)
                elif isinstance(cost_info, dict):
                    # Token counts only — store as None for now (no pricing table)
                    cost_usd = None
            
            if error:
                score = 0
                scoring_details = error
                response = ""
                print(f"ERROR: {error[:50]}")
            else:
                score, scoring_details = score_response(prompt_data, response)
                cost_str = f" ${cost_usd:.6f}" if cost_usd else ""
                print(f"score={score} ({scoring_details[:40]}) {latency}ms{cost_str}")
            
            conn.execute("""
                INSERT INTO runs (run_id, timestamp, provider, prompt_id, category, prompt, response, score, latency_ms, scoring_details, error, cost_usd)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (run_id, timestamp, provider_id, pid, prompt_data["category"],
                  prompt_data["prompt"], response or "", score, latency,
                  scoring_details, error, cost_usd))
            
            results.append({
                "provider": provider_id,
                "prompt_id": pid,
                "category": prompt_data["category"],
                "score": score,
                "latency_ms": latency,
                "error": error,
                "cost_usd": cost_usd,
            })
    
    conn.commit()
    
    # Compute daily averages
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for provider_id in providers:
        provider_results = [r for r in results if r["provider"] == provider_id]
        categories = set(r["category"] for r in provider_results)
        
        for cat in categories:
            cat_results = [r for r in provider_results if r["category"] == cat]
            avg_score = sum(r["score"] for r in cat_results) / len(cat_results)
            avg_latency = sum(r["latency_ms"] for r in cat_results) / len(cat_results)
            
            conn.execute("""
                INSERT INTO daily_scores (date, provider, category, avg_score, num_tests, avg_latency_ms)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (date_str, provider_id, cat, avg_score, len(cat_results), avg_latency))
    
    conn.commit()
    
    # Print summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for provider_id in providers:
        pr = [r for r in results if r["provider"] == provider_id]
        if pr:
            avg = sum(r["score"] for r in pr) / len(pr)
            avg_lat = sum(r["latency_ms"] for r in pr) / len(pr) if any(r["latency_ms"] for r in pr) else 0
            errors = sum(1 for r in pr if r["error"])
            total_cost = sum(r.get("cost_usd") or 0 for r in pr)
            cost_str = f" cost=${total_cost:.4f}" if total_cost > 0 else ""
            print(f"  {provider_id}: avg_score={avg:.1f} avg_latency={avg_lat:.0f}ms errors={errors}{cost_str}")
    
    conn.close()
    return results


def detect_drift(days=7, threshold=10):
    """Compare today's scores with rolling average. Flag significant changes."""
    conn = sqlite3.connect(DB_PATH)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    cursor = conn.execute("""
        SELECT provider, category, avg_score 
        FROM daily_scores 
        WHERE date = ?
    """, (today,))
    today_scores = cursor.fetchall()
    
    alerts = []
    for provider, category, today_score in today_scores:
        cursor = conn.execute("""
            SELECT AVG(avg_score) 
            FROM daily_scores 
            WHERE provider = ? AND category = ? AND date < ? 
            ORDER BY date DESC LIMIT ?
        """, (provider, category, today, days))
        row = cursor.fetchone()
        if row and row[0] is not None:
            historical_avg = row[0]
            diff = today_score - historical_avg
            if abs(diff) >= threshold:
                direction = "improved" if diff > 0 else "degraded"
                alerts.append({
                    "provider": provider,
                    "category": category,
                    "today": today_score,
                    "historical_avg": historical_avg,
                    "diff": diff,
                    "direction": direction,
                })
    
    conn.close()
    return alerts


def show_report(days=30):
    """Show historical scores for all providers."""
    if not DB_PATH.exists():
        print("No data yet. Run tests first.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    
    # Get all providers with data
    cursor = conn.execute("""
        SELECT DISTINCT provider 
        FROM daily_scores 
        ORDER BY provider
    """)
    providers = [row[0] for row in cursor.fetchall()]
    
    if not providers:
        print("No historical data found.")
        conn.close()
        return
    
    print(f"\n{'='*80}")
    print(f"HISTORICAL SCORES (last {days} days)")
    print(f"{'='*80}\n")
    
    for provider in providers:
        print(f"📊 {provider}")
        print(f"   {'─'*76}")
        
        cursor = conn.execute("""
            SELECT date, category, avg_score, num_tests, avg_latency_ms
            FROM daily_scores
            WHERE provider = ?
            ORDER BY date DESC, category
            LIMIT ?
        """, (provider, days * 5))  # 5 categories max
        
        rows = cursor.fetchall()
        if not rows:
            print("   No data\n")
            continue
        
        # Group by date
        by_date = {}
        for date, category, score, num, latency in rows:
            if date not in by_date:
                by_date[date] = []
            by_date[date].append((category, score, num, latency))
        
        for date in sorted(by_date.keys(), reverse=True)[:7]:  # Show last 7 days detail
            scores = by_date[date]
            avg_score = sum(s[1] for s in scores) / len(scores)
            avg_latency = sum(s[3] for s in scores) / len(scores)
            print(f"   {date}: avg_score={avg_score:5.1f} | avg_latency={avg_latency:6.0f}ms | {len(scores)} categories")
        
        print()
    
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Canary — LLM Drift Monitor. Automated quality testing for AI models.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run tests on specific providers (via OpenRouter)
  python runner.py --providers openai/gpt-4o,anthropic/claude-3.5-sonnet
  
  # Show historical report
  python runner.py --report
  
  # Run all tests with drift detection
  python runner.py
        """
    )
    
    parser.add_argument(
        "--providers",
        type=str,
        help="Comma-separated list of provider/model IDs (e.g., openai/gpt-4o,anthropic/claude-3.5-sonnet)"
    )
    
    parser.add_argument(
        "--report",
        action="store_true",
        help="Show historical scores instead of running tests"
    )
    
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days for drift detection (default: 7)"
    )
    
    args = parser.parse_args()
    
    if args.report:
        show_report()
        sys.exit(0)
    
    providers = None
    if args.providers:
        providers = [p.strip() for p in args.providers.split(",")]
    
    print(f"🐤 Canary — LLM Drift Monitor")
    print(f"   Run started: {datetime.now(timezone.utc).isoformat()}")
    print(f"   Providers: {', '.join(providers) if providers else 'all configured'}")
    print()
    
    results = run_tests(providers=providers)
    
    # Check for drift
    alerts = detect_drift(days=args.days)
    if alerts:
        print(f"\n{'!'*60}")
        print("⚠️  DRIFT ALERTS")
        print(f"{'!'*60}")
        for a in alerts:
            emoji = "📈" if a['direction'] == "improved" else "📉"
            print(f"  {emoji} {a['provider']} / {a['category']}: {a['direction']} by {abs(a['diff']):.1f} pts")
            print(f"     Today: {a['today']:.1f} | Historical avg: {a['historical_avg']:.1f}")
    else:
        print("\n✅ No drift detected (or not enough historical data yet)")

    # Send webhook alerts (if configured)
    try:
        from alerts import send_alerts
        # Build summary for webhooks
        summary = []
        for provider_id in (providers or []):
            pr = [r for r in results if r["provider"] == provider_id]
            if pr:
                avg = sum(r["score"] for r in pr) / len(pr)
                avg_lat = sum(r["latency_ms"] for r in pr) / len(pr)
                summary.append({
                    "provider": provider_id,
                    "overall_score": avg,
                    "overall_latency": avg_lat,
                    "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                })
        sent = send_alerts(alerts, summary)
        if sent:
            print(f"\n📬 Alerts sent to: {', '.join(sent)}")
    except ImportError:
        pass
    except Exception as e:
        print(f"\n⚠️  Alert delivery failed: {e}")
