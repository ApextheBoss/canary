FROM python:3.12-slim

WORKDIR /app

# Install minimal deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Seed demo data if no DB exists
RUN python seed_demo.py

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["python", "dashboard.py"]
