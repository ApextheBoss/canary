# 🚀 Launch Checklist - Canary

## ✅ Phase 1 Complete

All initial deliverables shipped:

1. ✅ **OpenRouter support** — Single API, routes to all providers (OpenAI, Anthropic, Google, etc.)
2. ✅ **CLI interface** — `--providers`, `--report`, `--days` flags
3. ✅ **GitHub Actions workflow** — Daily automated testing + auto-commit results
4. ✅ **Professional README** — Clear value prop, installation, usage, examples
5. ✅ **requirements.txt** — (Empty! Pure stdlib)
6. ✅ **MIT LICENSE** — Open source
7. ✅ **GitHub repo created** — https://github.com/ApextheBoss/canary (PUBLIC)
8. ✅ **Code pushed** — All files committed and live

## 📍 Current Status

**Repo:** https://github.com/ApextheBoss/canary  
**Status:** LIVE, PUBLIC  
**Topics:** llm, ai, monitoring, quality-assurance, drift-detection, openai, anthropic, openrouter

## 🎯 Next Steps (Launch Day)

### Immediate (within hours)

1. **Set up GitHub repo secrets**
   - Add `OPENROUTER_API_KEY` to enable automated tests
   - Settings → Secrets and variables → Actions → New repository secret

2. **Manually trigger first workflow run**
   - Actions → Daily LLM Quality Tests → Run workflow
   - This will populate initial data in drift.db

3. **Social launch**
   - HN post: "Show HN: Canary – Know when your LLM provider silently degrades"
   - Tweet thread highlighting the Claude Code A/B controversy timing
   - Post in r/LocalLLaMA, r/MachineLearning

### Within 24h

4. **Monitor engagement**
   - Respond to GitHub issues/PRs
   - Answer HN comments
   - Track stars/forks

5. **First blog post**
   - "Weekly LLM Quality Report - Week 1"
   - Share actual test results from drift.db
   - Show which providers are most consistent

### Within 1 week

6. **Dashboard (Phase 2)**
   - Simple FastAPI endpoint: `GET /api/scores?provider=openai/gpt-4o&days=30`
   - Single-page HTML dashboard with Chart.js
   - Deploy to Vercel/Render (free tier)

7. **Webhook alerts**
   - Discord/Slack integration for drift alerts
   - Email notifications (SendGrid free tier)

## 🎨 HN Launch Post Template

```
Show HN: Canary – Know when your LLM provider silently degrades

https://github.com/ApextheBoss/canary

Built this in response to the Claude Code A/B testing drama that's been 
trending here. If we can't trust providers to tell us when they're 
experimenting, we'll test them ourselves.

Canary runs 20 standardized quality tests daily against LLMs (via OpenRouter):
- Code generation with actual unit tests
- Reasoning puzzles with known answers
- Math, instruction-following, consistency checks
- Deterministic scoring (not vibes)
- Drift detection + historical tracking

Uses only Python stdlib. GitHub Actions runs tests daily for free.

Open to feedback! Planning to publish weekly quality reports showing which 
models are actually getting better/worse over time.
```

## 📊 Success Metrics

**Week 1 goals:**
- [ ] 100+ stars on GitHub
- [ ] Front page of HN for >2 hours
- [ ] 3+ contributors/PRs
- [ ] Published first "Weekly LLM Quality Report"

**Month 1 goals:**
- [ ] 500+ stars
- [ ] Dashboard live
- [ ] Automated weekly reports
- [ ] Mentioned in AI newsletters

## 🔧 Technical Debt to Address

- Add more comprehensive error handling in OpenRouter calls
- Implement retry logic with exponential backoff
- Add rate limiting awareness
- Consider caching responses for consistency tests
- Add provider cost tracking

## 💡 Future Features

- Multi-language support (test prompts in Spanish, Chinese, etc.)
- Safety/toxicity tests
- RAG accuracy benchmarks
- Latency percentile tracking (p50, p95, p99)
- Cost-per-quality metrics
- Provider uptime monitoring

---

**Status:** Ready to ship 🚀  
**Timing:** Perfect (Claude drama still hot on HN)  
**Risk:** Low (worst case: nobody cares, we learned something)  
**Upside:** High (fills real need, good timing, viral potential)

Let's go.
