FROM python:3.12-slim

# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies needed for Playwright and runtime networking
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies and Playwright Chromium with browser dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

# Copy application source code
COPY . .

# Ensure data directory exists for persistent state/analytics
RUN mkdir -p /app/data

# Default entrypoint and non-destructive command
ENTRYPOINT ["python", "main.py"]
CMD ["status"]
