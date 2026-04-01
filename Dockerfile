# ----------- Base Image -----------
FROM python:3.11-slim

# ----------- Environment -----------
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ----------- Work Directory -----------
WORKDIR /app

# ----------- Install Runtime Dependencies ONLY -----------
# Use libpq5 instead of libpq-dev (smaller, no compiler needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# ----------- Install Python Dependencies (cache optimized) -----------
COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ----------- Copy Application Code -----------
COPY . .
RUN chmod +x /app/entrypoint.sh

# ----------- Security: Run as Non-root User -----------
RUN useradd --create-home --shell /bin/bash appuser && \
    mkdir -p /app/staticfiles && \
    chown -R appuser:appuser /app
USER appuser

# ----------- Expose Port -----------
EXPOSE 8000

# ----------- Start Server -----------
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "atrack.asgi:application"]
