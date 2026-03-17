# Changelog

## Unreleased

### Added
- ⚙️ `canary.yaml` config file support — set default providers and drift thresholds without CLI flags
- `canary.example.yaml` with all available options
- `--config` CLI flag for custom config file path
- `--dry-run` and `--prompts` flags for easier onboarding
- 🏆 Leaderboard page + `/leaderboard` API endpoint
- 🔒 `.env.example` + `SECURITY.md` for OSS launch polish

## v0.1.0 — 2026-03-16

**First tagged release! 🎉**

### Added
- 🆚 `--compare` CLI command for head-to-head provider comparison
- `/api/compare` dashboard endpoint
- Tagged release v0.1.0

All notable changes to Canary will be documented in this file.

## [0.1.0] — 2026-03-15

### 🎉 Initial Release

**Core**
- 32 test prompts across 8 categories: code, reasoning, math, instruction following, consistency, safety, multilingual, RAG
- Deterministic scoring: code execution, exact answers, regex, JSON schema validation
- Drift detection with configurable threshold (default: 10 points)
- SQLite historical tracking (auto-created `drift.db`)
- Zero-dependency core runner (Python stdlib only)

**Multi-Provider**
- OpenRouter integration — one API key, 100+ models
- Legacy direct API support for OpenAI and Anthropic
- Cost tracking per provider per run

**Dashboard**
- FastAPI web UI with Chart.js charts
- Score cards, drift alerts, 30-day trend lines, category comparisons
- JSON API endpoints: `/api/summary`, `/api/history`, `/api/drift`, `/api/runs/latest`

**Alerts**
- Webhook support: Discord, Slack, generic JSON POST
- Automatic alerts on drift detection after each run

**Automation**
- GitHub Actions workflow for daily tests at midnight UTC
- Weekly quality report generator with optional webhook delivery
- Auto-commit results to repo

**Developer Experience**
- CLI with `--providers`, `--report`, `--days` flags
- Demo data seeder for local development
- `pyproject.toml` for pip-installable package
