# Contributing to Canary

Thanks for your interest in improving LLM quality monitoring! 

## Quick Start

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/amazing-scoring`)
3. Make your changes
4. Test locally: `python runner.py --providers openai/gpt-4o`
5. Commit with clear messages
6. Push and open a PR

## What We Need

### 🎯 High Priority

- **More test prompts** — especially edge cases where models fail inconsistently
- **Better scoring functions** — more nuanced quality measurement
- **Provider integrations** — direct API support (we use OpenRouter, but fallbacks are good)
- **Dashboard** — simple web UI to visualize trends

### 💡 Ideas Welcome

- Cost tracking per provider/model
- Safety/toxicity tests
- Multilingual quality tests
- RAG accuracy tests
- Latency percentile tracking
- Automated weekly reports

## Code Style

Keep it simple:
- Use Python stdlib when possible (avoid heavy dependencies)
- Docstrings for non-obvious functions
- Type hints appreciated but not required
- Tests should be deterministic (no vibes-based scoring)

## Adding Test Prompts

Edit `prompts.json`:

```json
{
  "id": "unique-id-01",
  "category": "code|reasoning|math|instruction_following|consistency",
  "prompt": "Your test prompt here",
  "scoring": {
    "type": "exact_answer|code_execution|format_check|json_check|structured_answer",
    "expected": "...",
    "test_code": "...",
    "criteria": [...]
  }
}
```

**Good test prompts:**
- Have objective, measurable success criteria
- Test common failure modes
- Are resistant to overfitting (don't appear in training data)
- Surface real quality differences between models

**Avoid:**
- Subjective "quality" judgments
- Tests that require human evaluation
- Prompts that are too easy (100% pass rate tells us nothing)

## Adding Scoring Functions

Implement in `runner.py`:

```python
def score_your_new_type(response, criteria):
    """Docstring explaining what this scores."""
    score = 100  # Start at perfect
    details = []
    
    # Your scoring logic here
    # Deduct points for failures
    # Track what went wrong
    
    return max(0, score), "; ".join(details)
```

Then add to `score_response()` routing.

## Questions?

Open an issue! I'm responsive.

---

Built with ☕ and frustration at opaque model updates.
