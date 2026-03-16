FROM python:3.13-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY services/trading-engine/requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy shared alembic
COPY shared/alembic/ /app/alembic/
COPY shared/alembic.ini /app/alembic.ini

# Copy trading engine code
COPY services/trading-engine/ /app/

# Install the package
RUN pip install -e .

# Create logs directory
RUN mkdir -p logs

# Fix CRLF line endings (Windows Git checkout) and make executable
RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8081/healthz')" || exit 1

ENTRYPOINT ["./entrypoint.sh"]
