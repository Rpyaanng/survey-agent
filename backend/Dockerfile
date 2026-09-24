FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN adduser --disabled-password --gecos "" app && chown -R app:app /app
USER app

ENV APP_ENV=production PORT=5000
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/health" || exit 1

# Apply migrations, then serve. gthread workers suit the IO-bound AI and webhook calls.
CMD ["sh", "-c", "flask --app wsgi db upgrade && exec gunicorn wsgi:app --bind 0.0.0.0:${PORT} --worker-class gthread --workers ${WEB_CONCURRENCY:-2} --threads 8 --timeout 120 --access-logfile -"]
