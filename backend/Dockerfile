FROM python:3.13-slim AS runtime

ARG PIP_VERSION=26.2.1

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install current Debian security updates.
RUN apt-get update \
    && apt-get upgrade --yes \
    && rm -rf /var/lib/apt/lists/*

# Create an unprivileged application user.
RUN groupadd --system app \
    && useradd --system --gid app --home /app app

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt

# Use the current pip release to install dependencies, then remove pip and
# its vendored packages because package installation is unnecessary at runtime.
RUN python -m pip install \
    --no-cache-dir \
    --upgrade "pip==${PIP_VERSION}" \
    && python -m pip install \
    --no-cache-dir \
    --requirement requirements.txt \
    && python -m pip uninstall \
    --yes pip

COPY backend/app.py ./
COPY backend/migrate.py ./
COPY database/migrations ./migrations

USER app

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

CMD ["gunicorn", "--bind=0.0.0.0:8080", "--workers=2", "--threads=4", "--worker-tmp-dir=/dev/shm", "--access-logfile=-", "--error-logfile=-", "app:app"]
