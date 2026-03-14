# Quick Setup Guide

## For Local Testing

```bash
# 1. Clone the repo
git clone https://github.com/ApextheBoss/canary.git
cd canary

# 2. Get an OpenRouter API key
# Sign up at https://openrouter.ai (free tier available)

# 3. Set your API key
export OPENROUTER_API_KEY="sk-or-v1-..."

# 4. Run your first test
python runner.py --providers openai/gpt-4o,anthropic/claude-3.5-sonnet

# 5. View the report
python runner.py --report
```

## For GitHub Actions (Automated Daily Tests)

1. **Get OpenRouter API key**
   - Go to https://openrouter.ai
   - Sign up (free tier works fine)
   - Create an API key

2. **Add to GitHub Secrets**
   - Go to your fork: https://github.com/YOUR_USERNAME/canary
   - Click **Settings** → **Secrets and variables** → **Actions**
   - Click **New repository secret**
   - Name: `OPENROUTER_API_KEY`
   - Value: Your API key (starts with `sk-or-v1-`)
   - Click **Add secret**

3. **Enable GitHub Actions**
   - Go to **Actions** tab
   - Click "I understand my workflows, go ahead and enable them"

4. **Trigger first run**
   - Actions → **Daily LLM Quality Tests** → **Run workflow**
   - Select branch: `main`
   - Click **Run workflow**

5. **Watch it run**
   - Results will be committed to `drift.db`
   - Future runs happen daily at midnight UTC automatically

## Customizing Test Providers

Edit `.github/workflows/daily-run.yml`:

```yaml
- name: Run quality tests
  env:
    OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
  run: |
    python runner.py --providers openai/gpt-4o,anthropic/claude-3.5-sonnet,YOUR/MODEL-HERE
```

## Available Providers (via OpenRouter)

- `openai/gpt-4o`
- `openai/gpt-4o-mini`
- `anthropic/claude-3.5-sonnet`
- `anthropic/claude-3-haiku`
- `google/gemini-2.0-flash-thinking-exp`
- `google/gemini-pro-1.5`
- `meta-llama/llama-3.1-405b-instruct`
- Many more at https://openrouter.ai/models

## Viewing Results

```bash
# Local SQLite database
sqlite3 drift.db "SELECT * FROM daily_scores ORDER BY date DESC LIMIT 10"

# Or use the built-in report
python runner.py --report
```

## Troubleshooting

**Error: Missing OPENROUTER_API_KEY**
- Make sure you've exported it: `echo $OPENROUTER_API_KEY`
- For GitHub Actions, check that the secret is added correctly

**Tests failing with HTTP 401**
- Invalid API key
- Check your OpenRouter credits at https://openrouter.ai/credits

**GitHub Actions not running**
- Make sure Actions are enabled in repo settings
- Check that the workflow file is in `.github/workflows/`

**No drift detected**
- Need at least 2 days of data for comparison
- Run tests manually to populate initial data

---

Questions? Open an issue: https://github.com/ApextheBoss/canary/issues
