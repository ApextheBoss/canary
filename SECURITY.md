# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT open a public issue**
2. Email: security@canary-llm.dev (or open a private security advisory on GitHub)
3. Include steps to reproduce

We'll respond within 48 hours and aim to fix critical issues within 7 days.

## Scope

Canary runs LLM prompts and stores results locally in SQLite. Security considerations:

- **API keys**: Never commit API keys. Use environment variables or `.env` files (gitignored).
- **Code execution**: The `code_execution` scoring type runs extracted code in a subprocess. This is sandboxed to the local machine — don't run untrusted prompts.json files.
- **Dashboard**: The FastAPI dashboard binds to localhost by default. If exposed publicly, add authentication.
- **drift.db**: Contains LLM responses. May include sensitive content depending on your prompts.

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 0.1.x   | ✅        |
