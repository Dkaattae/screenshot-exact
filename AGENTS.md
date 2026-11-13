## App architecture
- Keep the fixed TanStack Router file-based shell; the requested React Router navigation is implemented with the native router to preserve hosting compatibility.
- All browser HTTP calls go through frontend/src/api/client.ts and use shared types; MSW supplies the in-memory mock contract so a real API can replace it without page changes.
- Keep mock startup and canvas/image preparation browser-only; query hooks load the mock API after hydration because a service worker cannot intercept server-side requests.
- Keep the global job watcher in the shared shell so navigation never interrupts polling; mock data is intentionally session-memory only.
- `openapi.yaml` (repo root) is the API contract. Keep `frontend/src/api/types.ts`, `client.ts` and the MSW handlers in line with it.
