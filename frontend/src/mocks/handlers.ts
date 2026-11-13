import { http, HttpResponse } from "msw";
import type {
  BodyProfile,
  DefaultBody,
  Background,
  Item,
  Outfit,
  OutfitState,
  Job,
} from "../api/types";
import { API_BASE_URL, MOCK_FAILURE_RATE, USER_ID } from "../api/config";
import { editState, reusedLayers, validation, VIEWS } from "../api/rules";
import { generateView } from "./generation";
import i0 from "@/assets/item-0.jpg";
import i1 from "@/assets/item-1.jpg";
import i2 from "@/assets/item-2.jpg";
import i3 from "@/assets/item-3.jpg";
import i4 from "@/assets/item-4.jpg";
import i5 from "@/assets/item-5.jpg";
import i6 from "@/assets/item-6.jpg";
import i7 from "@/assets/item-7.jpg";
import front from "@/assets/body-front.jpg";
import side from "@/assets/body-side.jpg";
import back from "@/assets/body-back.jpg";
const now = () => new Date().toISOString();
const id = () => crypto.randomUUID();
const path = (p: string) => `${API_BASE_URL}${p}`;
const user = "/users/:user_id";
let body: BodyProfile | null = null;
const bodies: DefaultBody[] = [
  { id: id(), name: "Default A", images: { front, side, back } },
  { id: id(), name: "Default B", images: { front, side, back } },
];
const bg = (color: string) => {
  const c = document.createElement("canvas");
  c.width = 600;
  c.height = 800;
  const x = c.getContext("2d");
  if (x) {
    x.fillStyle = color;
    x.fillRect(0, 0, 600, 800);
  }
  return c.toDataURL("image/jpeg");
};
const backgrounds: Background[] = [];
const items: Item[] = [
  ["Cotton poplin shirt", "top", i0],
  ["Everyday crew tee", "top", i1],
  ["Straight-leg denim", "bottom", i2],
  ["Tailored trousers", "bottom", i3],
  ["The everyday midi", "one_piece", i4],
  ["Classic trench coat", "outer", i5],
  ["Leather biker jacket", "outer", i6],
  ["Everyday shoulder bag", "accessory", i7],
].map(([name, slot, url], i) => ({
  id: id(),
  user_id: USER_ID,
  name,
  slot: slot as Item["slot"],
  front_url: url,
  back_url: i === 6 ? null : url,
  measurements: {},
  created_at: now(),
}));
const outfits: Outfit[] = [];
const jobs: Job[] = [];
const snapshots = new Map<string, OutfitState>();
const error = (message: string, status = 400) =>
  HttpResponse.json(
    { error: { code: status === 404 ? "NOT_FOUND" : "VALIDATION_ERROR", message } },
    { status },
  );
const obj = (data: FormData, key: string) => {
  const file = data.get(key);
  return file instanceof File ? URL.createObjectURL(file) : null;
};
const measurements = (data: FormData) =>
  JSON.parse(String(data.get("measurements") || "{}")) as Record<string, number | null>;
const pending = () => ({ status: "queued" as const, url: null, inferred_item_ids: [] });
function startJob(outfit: Outfit) {
  const previous = jobs.find((j) => j.outfit_id === outfit.id && j.status === "done");
  const state = structuredClone(outfit.state);
  const job: Job = {
    id: id(),
    outfit_id: outfit.id,
    outfit_version: outfit.version,
    status: "queued",
    views: { front: pending(), side: pending(), back: pending() },
    layers: reusedLayers(previous ? snapshots.get(previous.id) : undefined, state),
    timings_ms: { total: null },
    cost_usd: null,
    error: null,
    created_at: now(),
  };
  jobs.unshift(job);
  snapshots.set(job.id, state);
  const start = Date.now();
  setTimeout(() => {
    job.status = "running";
    VIEWS.forEach((v) => (job.views[v].status = "running"));
    let elapsed = 0;
    VIEWS.forEach((v, index) => {
      elapsed += 2000 + Math.random() * 4000;
      setTimeout(() => {
        if (job.status === "failed") return;
        if (index === VIEWS.length - 1 && Math.random() < MOCK_FAILURE_RATE) {
          job.status = "failed";
          job.error = "The mock generation could not finish. Please try again.";
          job.views[v].status = "failed";
          job.timings_ms.total = Date.now() - start;
          return;
        }
        job.views[v] = { status: "done", ...generateView(v, state, items) };
        if (VIEWS.every((v) => job.views[v].status === "done")) {
          job.status = "done";
          job.timings_ms.total = Date.now() - start;
        }
      }, elapsed);
    });
  }, 1000);
  return job;
}
export const handlers = [
  http.get(path(`${user}/profile`), () => HttpResponse.json({ body })),
  http.get(path("/bodies/defaults"), () => HttpResponse.json(bodies)),
  http.put(path(`${user}/body`), async ({ request }) => {
    const data = await request.formData();
    const f = obj(data, "front"),
      s = obj(data, "side"),
      b = obj(data, "back");
    if (!f || !s || !b || data.get("consent") !== "true")
      return error("All three photos and your consent are required.");
    body = {
      id: body?.id || id(),
      user_id: USER_ID,
      height_cm: data.get("height_cm") ? Number(data.get("height_cm")) : null,
      images: { front: f, side: s, back: b },
      measurements: measurements(data),
      consent_at: now(),
      updated_at: now(),
    };
    return HttpResponse.json(body);
  }),
  http.delete(path(`${user}/body`), () => {
    body = null;
    return new HttpResponse(null, { status: 204 });
  }),
  http.get(path(`${user}/backgrounds`), () => {
    if (!backgrounds.length)
      backgrounds.push(
        ...[
          ["Soft studio", "#eef0ed"],
          ["Warm neutral", "#e7e1d9"],
          ["Cool grey", "#d7dbdf"],
        ].map(([name, color]) => ({ id: id(), name, url: bg(color), is_preset: true })),
      );
    return HttpResponse.json(backgrounds);
  }),
  http.post(path(`${user}/backgrounds`), async ({ request }) => {
    const data = await request.formData();
    const url = obj(data, "file");
    if (!url) return error("Choose a background photo.");
    const b: Background = {
      id: id(),
      name: String(data.get("name") || "My background"),
      url,
      is_preset: false,
    };
    backgrounds.push(b);
    return HttpResponse.json(b, { status: 201 });
  }),
  http.get(path(`${user}/items`), ({ request }) => {
    const slot = new URL(request.url).searchParams.get("slot");
    return HttpResponse.json(items.filter((i) => !slot || i.slot === slot));
  }),
  http.post(path(`${user}/items`), async ({ request }) => {
    const data = await request.formData();
    const url = obj(data, "front");
    if (!url || !data.get("name")) return error("A name and front photo are required.");
    const item: Item = {
      id: id(),
      user_id: USER_ID,
      name: String(data.get("name")),
      slot: String(data.get("slot")) as Item["slot"],
      front_url: url,
      back_url: obj(data, "back"),
      measurements: measurements(data),
      created_at: now(),
    };
    items.push(item);
    return HttpResponse.json(item, { status: 201 });
  }),
  http.patch(path(`${user}/items/:item_id`), async ({ request, params }) => {
    const item = items.find((i) => i.id === params.item_id);
    if (!item) return error("Item not found.", 404);
    Object.assign(item, await request.json());
    return HttpResponse.json(item);
  }),
  http.delete(path(`${user}/items/:item_id`), ({ params }) => {
    const index = items.findIndex((i) => i.id === params.item_id);
    if (index < 0) return error("Item not found.", 404);
    items.splice(index, 1);
    return new HttpResponse(null, { status: 204 });
  }),
  http.get(path(`${user}/outfits`), () => HttpResponse.json(outfits)),
  http.post(path(`${user}/outfits`), async ({ request }) => {
    const data = (await request.json()) as { state: OutfitState; name?: string };
    const invalid = validation(data.state);
    if (invalid.length) return error(invalid.join(" "));
    const outfit: Outfit = {
      id: id(),
      user_id: USER_ID,
      name: data.name || null,
      favorite: false,
      state: data.state,
      version: 1,
      created_at: now(),
      updated_at: now(),
    };
    outfits.unshift(outfit);
    return HttpResponse.json(outfit, { status: 201 });
  }),
  http.get(path(`${user}/outfits/:outfit_id`), ({ params }) => {
    const o = outfits.find((o) => o.id === params.outfit_id);
    return o ? HttpResponse.json(o) : error("Outfit not found.", 404);
  }),
  http.patch(path(`${user}/outfits/:outfit_id`), async ({ params, request }) => {
    const o = outfits.find((o) => o.id === params.outfit_id);
    if (!o) return error("Outfit not found.", 404);
    const { name, favorite, ...patch } = (await request.json()) as Partial<OutfitState> & {
      name?: string;
      favorite?: boolean;
    };
    if (name !== undefined) o.name = name;
    if (favorite !== undefined) o.favorite = favorite;
    if (Object.keys(patch).length) {
      const state = { ...o.state, ...patch };
      const invalid = validation(state);
      if (invalid.length) return error(invalid.join(" "));
      o.state = state;
      o.version++;
    }
    o.updated_at = now();
    return HttpResponse.json(o);
  }),
  http.post(path(`${user}/outfits/:outfit_id/edit`), async ({ params, request }) => {
    const o = outfits.find((o) => o.id === params.outfit_id);
    if (!o) return error("Outfit not found.", 404);
    const { message } = (await request.json()) as { message: string };
    const result = editState(o.state, message);
    if (JSON.stringify(o.state) !== JSON.stringify(result.state)) {
      o.state = result.state;
      o.version++;
      o.updated_at = now();
    }
    return HttpResponse.json({ outfit: o, change_summary: result.change_summary });
  }),
  http.delete(path(`${user}/outfits/:outfit_id`), ({ params }) => {
    const index = outfits.findIndex((o) => o.id === params.outfit_id);
    if (index < 0) return error("Outfit not found.", 404);
    outfits.splice(index, 1);
    return new HttpResponse(null, { status: 204 });
  }),
  http.post(path(`${user}/outfits/:outfit_id/generate`), ({ params }) => {
    const o = outfits.find((o) => o.id === params.outfit_id);
    if (!o) return error("Outfit not found.", 404);
    return HttpResponse.json({ job_id: startJob(o).id }, { status: 202 });
  }),
  http.get(path(`${user}/outfits/:outfit_id/jobs`), ({ params }) =>
    HttpResponse.json(jobs.filter((j) => j.outfit_id === params.outfit_id)),
  ),
  http.get(path("/jobs/:job_id"), ({ params }) => {
    const job = jobs.find((j) => j.id === params.job_id);
    return job ? HttpResponse.json(job) : error("Generation not found.", 404);
  }),
];
