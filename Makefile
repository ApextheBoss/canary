.PHONY: test report dashboard demo clean

# Run tests against default providers
test:
	python runner.py --providers openai/gpt-4o,anthropic/claude-3.5-sonnet

# Show historical report
report:
	python runner.py --report

# Generate weekly report
weekly:
	python report.py

# Start web dashboard
dashboard:
	pip install fastapi uvicorn -q && python dashboard.py

# Seed demo data for local dev
demo:
	python seed_demo.py

# Clean generated files
clean:
	rm -f drift.db daily-report.txt
	rm -rf __pycache__
