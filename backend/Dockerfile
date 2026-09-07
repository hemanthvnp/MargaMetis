FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY route_optimizer/ /app/route_optimizer/
COPY backend/         /app/backend/

RUN mkdir -p /app/backend/graph_cache /app/backend/cache /app/logs

WORKDIR /app/backend

EXPOSE 5000

HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
    CMD curl -f http://localhost:5000/api/health || exit 1

CMD gunicorn -w 1 -b 0.0.0.0:${PORT:-5000} --timeout 300 wsgi:app
