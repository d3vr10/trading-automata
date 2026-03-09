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

# Make entrypoint script executable
RUN chmod +x entrypoint.sh

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import os; os.path.exists('logs/trading-automata.log') or exit(1)"

ENTRYPOINT ["./entrypoint.sh"]
