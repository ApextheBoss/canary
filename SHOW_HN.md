# Show HN Draft

**Title:** Show HN: Canary – Know when your LLM provider silently degrades

**URL:** https://github.com/ApextheBoss/canary

**Text:**

Hey HN,

After the Claude Code A/B testing controversy hit the front page, I realized there's no easy way to know when your LLM provider silently changes model quality.

So I built Canary — an automated quality testing tool for LLMs. Think Pingdom for model quality.

**What it does:**
- 32 test prompts across 8 categories (code, reasoning, math, instruction following, consistency, safety, multilingual, RAG)
- Multi-provider testing via OpenRouter (one API key, test any model)
- Drift detection — alerts when quality shifts >10 points
- SQLite history + FastAPI dashboard with Chart.js charts
- GitHub Actions workflow for free daily automated testing
- Zero dependencies for the core runner (Python stdlib only)

**Scoring is deterministic, not vibes:** code prompts run actual unit tests, math checks exact answers, format tests use regex validation, JSON tests parse and validate schemas.

**How to use it:**
```
export OPENROUTER_API_KEY="your-key"
python runner.py --providers openai/gpt-4o,anthropic/claude-3.5-sonnet
```

One command, you get a quality scorecard. Run it daily via GitHub Actions and you'll know the moment a provider degrades.

MIT licensed. Would love feedback on test coverage and scoring approaches.
