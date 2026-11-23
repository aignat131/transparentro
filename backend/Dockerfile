FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml ./
# instalăm dependențele înainte de cod, pentru cache de build
RUN mkdir -p tro && touch tro/__init__.py && pip install -e ".[dev]" && rm -rf tro

COPY . .
RUN pip install -e ".[dev]" --no-deps

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn tro.api.main:app --host 0.0.0.0 --port 8000"]
