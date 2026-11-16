# Screenshot Exact

Implement exactly the screenshot and nothing else

## Layout

- `frontend/`: React + TanStack Start app (Vite), with an MSW mock API
- `backend/`: FastAPI service that implements the contract (see [`backend/README.md`](backend/README.md))
- `openapi.yaml`: the API contract the mock implements and the backend serves
- `Dockerfile`, `compose.yaml`: one app image (backend serving the built frontend) plus Postgres

## Run everything in Docker

```sh
docker compose up --build
```

Open http://localhost:8000. The API is at `/api` (docs at http://localhost:8000/api/docs),
and data lives in Postgres (`db` service, also reachable on `localhost:5433` as
`tryon`/`tryon`). Uploaded images go to the `files` volume. `docker compose down -v` wipes
both.

The image builds the frontend with the mock API on (`VITE_USE_MOCKS: "true"` in
`compose.yaml`), because the frontend has no sign-in screen yet and the real API answers
401 without a token. Set it to `"false"` to point the page at the backend.

## Frontend development

```sh
cd frontend
npm i
npm run dev
```
