FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --home-dir /app app
COPY pyproject.toml README.md ./
RUN python -c "import tomllib,subprocess; subprocess.check_call(['pip','install','--no-cache-dir',*tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']])"
COPY src ./src
RUN pip install --no-cache-dir --no-deps .
COPY alembic.ini ./
COPY migrations ./migrations
COPY tools ./tools
USER app

CMD ["python", "-m", "misp_ioc_scoring.entrypoints.collector"]
