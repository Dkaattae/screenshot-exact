# Backend

FastAPI service that implements [`../openapi.yaml`](../openapi.yaml).

## Run

```sh
cd backend
uv sync
uv run uvicorn app.main:create_app --factory --reload
```

The API runs on http://localhost:8000, and interactive docs are at `/docs`. Uploaded
files go to `backend/data/files`. The database is `TRYON_DATABASE_URL`: Postgres in
Docker (`docker compose up db` from the repo root, then the URL in `.env.example`), or
SQLite at `backend/data/app.db` when unset. Settings are listed in `.env.example`.

`app.main:create_site` serves the API at `/api` and, with `TRYON_FRONTEND_DIR` set, the
built frontend at `/` (any path that isn't a file gets `_shell.html`, so client routes
like `/wardrobe` load). This is what the Docker image runs; see the root README.

To point the frontend at it, set `VITE_USE_MOCKS=false` and
`VITE_API_BASE_URL=http://localhost:8000`. The frontend has no sign-in screen yet, so
until it does, requests from the frontend will get 401.

## Test

```sh
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

`tests/test_contract.py` fails if the served endpoints or success status codes drift
from `openapi.yaml`.

Tests use a throwaway SQLite file by default. To run them against Postgres, point
`TRYON_TEST_DATABASE_URL` at a database used only for tests, since every table is dropped
after each test:

```sh
docker compose exec db psql -U tryon -c 'create database tryon_test'
TRYON_TEST_DATABASE_URL=postgresql+psycopg://tryon:tryon@localhost:5433/tryon_test uv run pytest
```

## What's here

- **Auth** (`app/security.py`): email and password, hashed with Argon2. Sign-in
  returns a JWT access token (HS256, 7 days by default). In `/users/{user_id}/` paths,
  `user_id` is `me` or your own id; another user's data is 403 or 404.
- **Storage** (`app/storage.py`): files on local disk. The database stores keys, and
  responses carry signed URLs that expire after an hour. Uploads must be JPEG, PNG or
  WebP, at most 15 MB, and the file's leading bytes must match its type.
- **Seed data** (`app/seed.py`): 2 default bodies and 3 preset backgrounds, created on
  first start.

## Not implemented yet

- **Image generation** (`app/generation.py`): `infer_item_view` and `render_try_on`
  raise `GenerationNotImplemented`, so every job ends as `failed` with "Image
  generation is not implemented yet." The rest of the job (views, inferred items,
  layer reuse, history) already works. Jobs run in-process after the response
  (FastAPI background tasks); move them to a queue once generation is real.
- **Free-text edits** (`app/rules.py` `edit_state`): keyword matching, same as the
  frontend mock, standing in for the LLM parser.
- **Migrations**: tables are created on startup. Add Alembic before the schema changes
  under real data.
- **Accounts**: no password reset, email verification, refresh tokens or rate limiting
  on sign-in.
