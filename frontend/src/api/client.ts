import { API_BASE_URL, USE_MOCKS, USER_ID } from "./config";
import type {
  BodyProfile,
  DefaultBody,
  Background,
  Item,
  Slot,
  Outfit,
  OutfitState,
  Job,
  ApiError,
} from "./types";
let ready: Promise<void> | undefined;
async function mocksReady() {
  if (USE_MOCKS && typeof window !== "undefined") {
    ready ??= import("../mocks/browser").then((m) => m.startMocks());
    await ready;
  }
}
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  await mocksReady();
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    let message = "The request could not be completed.";
    try {
      message = ((await response.json()) as ApiError).error.message;
    } catch {
      // Body was not an ApiError; keep the generic message.
    }
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}
const user = `/users/${USER_ID}`;
const json = (method: string, data: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(data),
});
async function list<T>(path: string): Promise<T[]> {
  const result = await request<T[] | { items: T[]; next_cursor: string | null }>(path);
  return Array.isArray(result) ? result : result.items;
}
export const api = {
  profile: () => request<{ body: BodyProfile | null }>(`${user}/profile`),
  saveBody: (data: FormData) => request<BodyProfile>(`${user}/body`, { method: "PUT", body: data }),
  deleteBody: () => request<void>(`${user}/body`, { method: "DELETE" }),
  bodies: () => list<DefaultBody>("/bodies/defaults"),
  backgrounds: () => list<Background>(`${user}/backgrounds`),
  addBackground: (data: FormData) =>
    request<Background>(`${user}/backgrounds`, { method: "POST", body: data }),
  items: (slot?: Slot) => list<Item>(`${user}/items${slot ? `?slot=${slot}` : ""}`),
  addItem: (data: FormData) => request<Item>(`${user}/items`, { method: "POST", body: data }),
  updateItem: (id: string, data: Partial<Pick<Item, "name" | "slot" | "measurements">>) =>
    request<Item>(`${user}/items/${id}`, json("PATCH", data)),
  deleteItem: (id: string) => request<void>(`${user}/items/${id}`, { method: "DELETE" }),
  outfits: () => list<Outfit>(`${user}/outfits`),
  outfit: (id: string) => request<Outfit>(`${user}/outfits/${id}`),
  createOutfit: (state: OutfitState, name?: string) =>
    request<Outfit>(`${user}/outfits`, json("POST", { state, name })),
  updateOutfit: (id: string, data: Partial<OutfitState> & { name?: string; favorite?: boolean }) =>
    request<Outfit>(`${user}/outfits/${id}`, json("PATCH", data)),
  editOutfit: (id: string, message: string) =>
    request<{ outfit: Outfit; change_summary: string }>(
      `${user}/outfits/${id}/edit`,
      json("POST", { message }),
    ),
  deleteOutfit: (id: string) => request<void>(`${user}/outfits/${id}`, { method: "DELETE" }),
  generate: (id: string) =>
    request<{ job_id: string }>(`${user}/outfits/${id}/generate`, { method: "POST" }),
  job: (id: string) => request<Job>(`/jobs/${id}`),
  jobs: (id: string) => list<Job>(`${user}/outfits/${id}/jobs`),
};
