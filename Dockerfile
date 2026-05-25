FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates git && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN uv pip install --system --no-cache "nanobot-ai==0.2.0" -r /app/requirements.txt
RUN uv pip uninstall --system python-telegram-bot || true

RUN mkdir -p /data/.nanobot

COPY server.py /app/server.py
COPY templates/ /app/templates/
COPY telegram/ /app/telegram/
COPY nanobot_railway_patches/ /app/nanobot_railway_patches/
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

ENV HOME=/data
ENV NANOBOT_AGENTS__DEFAULTS__WORKSPACE=/data/.nanobot/workspace
ENV PYTHONPATH=/app:/app/nanobot_railway_patches

EXPOSE 8080

CMD ["/app/start.sh"]
