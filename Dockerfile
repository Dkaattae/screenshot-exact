# One image: FastAPI serves the API at /api and the built frontend at /.

# --- Frontend: static single-page build ---
FROM oven/bun:1.3 AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/bun.lock frontend/bunfig.toml ./
RUN bun install --frozen-lockfile
COPY frontend/ ./
# true: the page uses the in-browser mock API. false: it calls the backend at /api (which
# answers 401 until the frontend has a sign-in screen).
ARG VITE_USE_MOCKS=true
ENV SPA_BUILD=1 \
    VITE_API_BASE_URL=/api \
    VITE_USE_MOCKS=${VITE_USE_MOCKS}
RUN bun run build

# --- Backend ---
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PATH=/app/.venv/bin:$PATH
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev
COPY backend/app ./app
COPY --from=frontend /frontend/dist/client ./static

RUN useradd --system --uid 1000 app && mkdir -p /app/data/files && chown -R app /app/data
USER app

ENV TRYON_FRONTEND_DIR=/app/static \
    TRYON_STORAGE_DIR=/app/data/files \
    TRYON_PUBLIC_BASE_URL=http://localhost:8000/api
EXPOSE 8000
CMD ["uvicorn", "app.main:create_site", "--factory", "--host", "0.0.0.0", "--port", "8000"]
