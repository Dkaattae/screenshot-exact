import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// The client starts MSW in the browser. Tests stub fetch instead, so skip the worker.
vi.mock('@/mocks/browser', () => ({ startMocks: async () => {} }));

import { api } from '@/api/client';
import { API_BASE_URL } from '@/api/config';

const fetchMock = vi.fn();
const reply = (body: unknown, status = 200) =>
  Promise.resolve(new Response(body === null ? null : JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }));

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

describe('api client', () => {
  it('scopes user paths under /users/me', async () => {
    fetchMock.mockReturnValue(reply({ body: null }));
    await api.profile();
    expect(fetchMock).toHaveBeenCalledWith(`${API_BASE_URL}/users/me/profile`, undefined);
  });

  it('keeps job and default-body paths outside the user scope', async () => {
    fetchMock.mockImplementation(() => reply([]));
    await api.bodies();
    fetchMock.mockImplementation(() => reply({ id: 'j1' }));
    await api.job('j1');
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([`${API_BASE_URL}/bodies/defaults`, `${API_BASE_URL}/jobs/j1`]);
  });

  it('adds the slot filter only when one is given', async () => {
    fetchMock.mockImplementation(() => reply([]));
    await api.items('outer');
    await api.items();
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      `${API_BASE_URL}/users/me/items?slot=outer`,
      `${API_BASE_URL}/users/me/items`,
    ]);
  });

  it('sends JSON bodies for outfit edits', async () => {
    fetchMock.mockReturnValue(reply({ outfit: {}, change_summary: 'Shirt tucked in.' }));
    const result = await api.editOutfit('o1', 'tuck the shirt');
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${API_BASE_URL}/users/me/outfits/o1/edit`);
    expect(init.method).toBe('POST');
    expect(init.headers).toEqual({ 'Content-Type': 'application/json' });
    expect(JSON.parse(init.body)).toEqual({ message: 'tuck the shirt' });
    expect(result.change_summary).toBe('Shirt tucked in.');
  });

  it('accepts a paginated list response as well as a plain array', async () => {
    fetchMock.mockReturnValueOnce(reply([{ id: 'a' }])).mockReturnValueOnce(reply({ items: [{ id: 'b' }], next_cursor: null }));
    expect(await api.outfits()).toEqual([{ id: 'a' }]);
    expect(await api.outfits()).toEqual([{ id: 'b' }]);
  });

  it('returns undefined for 204 responses', async () => {
    fetchMock.mockReturnValue(reply(null, 204));
    await expect(api.deleteItem('i1')).resolves.toBeUndefined();
  });

  it('accepts 202 from generate', async () => {
    fetchMock.mockReturnValue(reply({ job_id: 'j1' }, 202));
    await expect(api.generate('o1')).resolves.toEqual({ job_id: 'j1' });
  });

  it('throws the ApiError message from a failed request', async () => {
    fetchMock.mockReturnValue(reply({ error: { code: 'NOT_FOUND', message: 'Outfit not found.' } }, 404));
    await expect(api.outfit('missing')).rejects.toThrow('Outfit not found.');
  });

  it('falls back to a generic message when the error body is not JSON', async () => {
    fetchMock.mockReturnValue(Promise.resolve(new Response('Bad gateway', { status: 502 })));
    await expect(api.outfit('o1')).rejects.toThrow('The request could not be completed.');
  });
});
