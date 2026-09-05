FROM python:3.12-slim

RUN groupadd --gid 1000 app && useradd --uid 1000 --gid app --create-home app

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend ./backend
COPY main.py ./main.py

RUN mkdir -p /app/data && chown -R app:app /app
USER app

EXPOSE 8001

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
    CMD uv run python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/')" || exit 1

CMD ["uv", "run", "python", "-m", "backend.main"]
