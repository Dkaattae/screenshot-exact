// Try-on generation. inferItemView and renderTryOn are DUMMIES that return
// placeholder SVG images. The real backend will replace them with model calls.
// Every job produces all three views. When the user has not uploaded a photo of
// an item for a view (items have no side photo, and the back photo is optional),
// that view of the item is generated first.
import type { Item, OutfitState, View } from "../api/types";
import { VIEWS } from "../api/rules";

export interface ViewOutput {
  url: string;
  /** Items whose photo for this view was generated rather than uploaded. */
  inferred_item_ids: string[];
}

interface Piece {
  item: Item;
  photo: string;
}

/** The photo the user uploaded for this view, or null when there is none. */
export function uploadedPhoto(item: Item, view: View): string | null {
  if (view === "front") return item.front_url;
  if (view === "back") return item.back_url;
  return null;
}

/** DUMMY: stands in for the model that infers an unseen view of an item. */
export function inferItemView(item: Item, view: View): string {
  return placeholder([`Inferred ${view}`, item.name]);
}

/** DUMMY: stands in for the model that renders the outfit on the body. */
export function renderTryOn(view: View, state: OutfitState, pieces: Piece[]): string {
  const lines = [
    `${view.charAt(0).toUpperCase()}${view.slice(1)} view`,
    "Mock try-on",
    ...pieces.map((p) => p.item.name),
  ];
  if (state.base.mode === "top_bottom" && state.base.tucked) lines.push("Tucked");
  if (state.outer) lines.push(state.outer.open ? "Outer open" : "Outer closed");
  return placeholder(lines);
}

/** Item ids worn in the outfit, base first. */
export function outfitItemIds(state: OutfitState): string[] {
  const base =
    state.base.mode === "one_piece"
      ? [state.base.one_piece_id]
      : [state.base.top_id, state.base.bottom_id];
  return [...base, state.outer?.item_id, state.accessory?.item_id].filter(
    (id): id is string => !!id,
  );
}

export function generateView(view: View, state: OutfitState, items: Item[]): ViewOutput {
  const inferred: string[] = [];
  const pieces = outfitItemIds(state)
    .map((id) => items.find((item) => item.id === id))
    .filter((item): item is Item => !!item)
    .map((item) => {
      const photo = uploadedPhoto(item, view);
      if (photo) return { item, photo };
      inferred.push(item.id);
      return { item, photo: inferItemView(item, view) };
    });
  return { url: renderTryOn(view, state, pieces), inferred_item_ids: inferred };
}

export function generateAllViews(state: OutfitState, items: Item[]): Record<View, ViewOutput> {
  return Object.fromEntries(
    VIEWS.map((view) => [view, generateView(view, state, items)]),
  ) as Record<View, ViewOutput>;
}

const escapeXml = (text: string) =>
  text.replace(
    /[&<>"]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] as string,
  );

function placeholder(lines: string[]): string {
  const text = lines
    .map(
      (line, i) =>
        `<text x="320" y="${180 + i * 46}" text-anchor="middle" font-family="sans-serif" font-size="${i === 0 ? 28 : 16}" fill="#25362e">${escapeXml(line)}</text>`,
    )
    .join("");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="850"><rect width="640" height="850" fill="#eef0ed"/>${text}</svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}
