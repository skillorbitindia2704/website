# Multi-stage production build for Skill Orbit India
# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Final minimal production runner
FROM python:3.11-slim AS runner

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed python dependencies from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application files
COPY . .

# Create directory for SQLite database instance and rotating logs
RUN mkdir -p instance logs static/uploads/resumes && \
    chmod -R 755 instance logs static/uploads

# Create a non-privileged system user for process isolation
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /sbin/nologin -c "Skill Orbit App User" appuser && \
    chown -R appuser:appgroup /app

USER appuser

# Configure environment variables
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1
ENV PORT=5000

EXPOSE 5000

# Start Flask application using secure Gunicorn production server
CMD ["gunicorn", "--config", "gunicorn.conf.py", "wsgi:app"]
