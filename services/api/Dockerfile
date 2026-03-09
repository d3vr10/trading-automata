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
COPY services/api/requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy shared alembic (for migration runs)
COPY shared/alembic/ /app/alembic/
COPY shared/alembic.ini /app/alembic.ini

# Copy API service code
COPY services/api/ /app/

# Run Alembic migrations, then start uvicorn
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
