import { describe, expect, it } from 'vitest';
import type { Item, OutfitState } from '@/api/types';
import { generateAllViews, generateView, inferItemView, outfitItemIds, uploadedPhoto } from '@/mocks/generation';

const item = (id: string, slot: Item['slot'], back_url: string | null = `${id}-back.jpg`): Item => ({
  id,
  user_id: 'me',
  slot,
  name: `${id} name`,
  front_url: `${id}-front.jpg`,
  back_url,
  measurements: {},
  created_at: '2026-01-01T00:00:00Z',
});

const top = item('top', 'top');
const jeans = item('jeans', 'bottom', null);
const jacket = item('jacket', 'outer');
const dress = item('dress', 'one_piece');
const items = [top, jeans, jacket, dress];

const state: OutfitState = {
  body: { kind: 'default', id: 'body' },
  background_id: 'bg',
  base: { mode: 'top_bottom', top_id: 'top', bottom_id: 'jeans', tucked: false },
  outer: { item_id: 'jacket', open: false },
  accessory: null,
  style_notes: {},
};

const svgText = (url: string) => decodeURIComponent(url.split(',')[1]);

describe('uploadedPhoto', () => {
  it('uses the front photo for the front view', () => expect(uploadedPhoto(top, 'front')).toBe('top-front.jpg'));
  it('uses the back photo for the back view', () => expect(uploadedPhoto(top, 'back')).toBe('top-back.jpg'));
  it('returns null for a missing back photo', () => expect(uploadedPhoto(jeans, 'back')).toBeNull());
  it('returns null for the side view, which items never have', () => expect(uploadedPhoto(top, 'side')).toBeNull());
});

describe('outfitItemIds', () => {
  it('lists top, bottom, outer and accessory in top mode', () =>
    expect(outfitItemIds({ ...state, accessory: { item_id: 'bag' } })).toEqual(['top', 'jeans', 'jacket', 'bag']));
  it('lists only the one-piece as the base in one-piece mode', () =>
    expect(outfitItemIds({ ...state, base: { mode: 'one_piece', one_piece_id: 'dress' }, outer: null })).toEqual(['dress']));
  it('skips a bottom that is not chosen yet', () =>
    expect(outfitItemIds({ ...state, base: { mode: 'top_bottom', top_id: 'top', bottom_id: null, tucked: false }, outer: null })).toEqual(['top']));
});

describe('generateView', () => {
  it('infers nothing on the front view when every item has a front photo', () =>
    expect(generateView('front', state, items).inferred_item_ids).toEqual([]));

  it('infers the back of an item with no back photo', () =>
    expect(generateView('back', state, items).inferred_item_ids).toEqual(['jeans']));

  it('infers the side of every item', () =>
    expect(generateView('side', state, items).inferred_item_ids).toEqual(['top', 'jeans', 'jacket']));

  it('returns an image URL that names the view and the items', () => {
    const { url } = generateView('front', state, items);
    expect(url).toMatch(/^data:image\/svg\+xml/);
    expect(svgText(url)).toContain('Front view');
    expect(svgText(url)).toContain('top name');
    expect(svgText(url)).toContain('Outer closed');
  });

  it('ignores item ids that are not in the wardrobe', () =>
    expect(generateView('side', { ...state, accessory: { item_id: 'deleted' } }, items).inferred_item_ids).not.toContain('deleted'));
});

describe('generateAllViews', () => {
  it('always returns front, side and back', () => {
    const views = generateAllViews(state, items);
    expect(Object.keys(views).sort()).toEqual(['back', 'front', 'side']);
    for (const view of Object.values(views)) expect(view.url).toMatch(/^data:image\/svg\+xml/);
  });
});

describe('inferItemView', () => {
  it('escapes item names so the placeholder stays valid SVG', () =>
    expect(svgText(inferItemView({ ...top, name: 'Tee <&> "x"' }, 'side'))).toContain('Tee &lt;&amp;&gt; &quot;x&quot;'));
});
