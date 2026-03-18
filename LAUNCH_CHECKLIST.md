# Launch Checklist

## Pre-Launch (Done ✅)
- [x] Core runner with 32 prompts, 8 categories
- [x] OpenRouter multi-provider support
- [x] Drift detection with configurable thresholds
- [x] SQLite historical tracking
- [x] FastAPI dashboard with Chart.js
- [x] Dynamic SVG badges
- [x] CSV export + auto-refresh
- [x] Leaderboard page
- [x] GitHub Actions (daily runs, weekly reports, CI)
- [x] Docker support
- [x] Webhook alerts (Discord, Slack, generic)
- [x] CLI: --compare, --dry-run, --prompts, --config
- [x] canary.yaml config file
- [x] Test suite (22 tests)
- [x] CONTRIBUTING.md, SECURITY.md, LICENSE (MIT)
- [x] .env.example
- [x] Show HN draft (SHOW_HN.md)
- [x] README with examples, architecture, quick start
- [x] v0.1.0 tagged

## Launch Day TODO
- [x] Verify GitHub repo is public
- [x] Add repo description + topics on GitHub (llm, testing, drift-detection, quality, monitoring)
- [ ] Post Show HN
- [ ] Tweet/social announcement
- [ ] Consider adding a demo GIF/screenshot to README (run seed_demo.py + screenshot dashboard)
- [x] Set up GitHub Discussions for community feedback

## Post-Launch Ideas
- [ ] PyPI package (`pip install canary-llm`)
- [ ] Hosted demo dashboard (free tier on Railway/Fly)
- [ ] More providers: Cohere, Mistral direct API
- [ ] Custom prompt upload (YAML/JSON file)
- [ ] Scheduled email reports
- [ ] Compare across model versions (gpt-4o vs gpt-4o-mini)
- [ ] Benchmark database — crowdsourced scores from community runs
