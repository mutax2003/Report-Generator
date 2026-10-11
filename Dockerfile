# ESA Report Generator — Streamlit UI
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system esa \
    && useradd --system --gid esa --create-home --home-dir /home/esa esa

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY docker-entrypoint.sh /docker-entrypoint.sh
# Pre-create writable state dirs so new named volumes inherit esa ownership.
RUN chmod +x /docker-entrypoint.sh \
    && mkdir -p /app/.esa_audit /app/.esa_tenants \
    && chown -R esa:esa /app

# Run as the unprivileged esa user (never root at runtime).
USER esa

EXPOSE 8501

ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV ESA_JSON_LOG=1

HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health')" || exit 1

# Entrypoint runs as esa; it only drops privileges itself if started with --user root.
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
