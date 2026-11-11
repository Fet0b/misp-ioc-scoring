FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN groupadd --system app && useradd --system --gid app --home-dir /app app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
USER app

CMD ["python", "-m", "misp_ioc_scoring.entrypoints.collector"]
