FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates git && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN uv pip install --system --no-cache "nanobot-ai==0.2.0" "python-telegram-bot[socks] @ git+https://github.com/muhammad-zainal-muttaqin/python-telegram-bot-v10.git@6fdab3a58d438cf998e0bde6b77f44d37bfef058" -r /app/requirements.txt

RUN mkdir -p /data/.nanobot

COPY server.py /app/server.py
COPY templates/ /app/templates/
COPY nanobot_railway_patches/ /app/nanobot_railway_patches/
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

ENV HOME=/data
ENV NANOBOT_AGENTS__DEFAULTS__WORKSPACE=/data/.nanobot/workspace
ENV PYTHONPATH=/app/nanobot_railway_patches

EXPOSE 8080

CMD ["/app/start.sh"]
