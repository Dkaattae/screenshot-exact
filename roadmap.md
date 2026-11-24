# Virtual try-on shell
- [ ] Typed client and complete in-memory MSW contract
- [ ] Wardrobe, profile, builder, results, saved outfits, comparison
- [ ] Image preparation, validation, asynchronous polling and debug
- [ ] Rule tests and desktop/mobile end-to-end verification

# Generation pipeline (decided 2026-11-24)

## Inputs

| Input | Source | Views |
|---|---|---|
| **Human model** | Generated from a prompt built from the user's measurements. No user photos. | front, side, back |
| **Scene** | Generated from a prompt. | one image, used behind every view |
| **Clothes** | Uploaded by the user: front required, back optional. Missing views generated. | front, side, back |

- Generate the human model and scene once, save them, and reuse them across outfits. The user can
  regenerate until they like the result.
- Every generated image stores its recipe next to it: `{model, version, prompt, seed, params}`.
  The saved image is the source of truth. A seed only reproduces an image on the same model
  version, so regenerating from the recipe is not guaranteed to give the same image.
- Clothes views are generated (and possibly enhanced) once, at upload, not per outfit. Keep the
  original upload.

## Outfit job

```
human (3 views) + clothes (layer order: base → outer → accessory) + scene
        │
        ▼  render step: clothes on the model (method TBD, see experiments)
3 stills: front, side, back
        │
        ▼  combine step: image-to-video from the 3 stills
6 s turnaround video (MP4, no sound)
        │
        ▼  derived, not stored as source
collage (front big, side + back stacked), built from the 3 stills
```

- The **render step** is one function, `render(human, clothes, scene) → 3 stills`. Whether it
  makes one call or one call per layer stays hidden inside it until the experiment decides.
- The **video** starts only after all 3 stills are done. If it fails, the stills are still the result.
- Save as **MP4** and play with `<video autoplay loop muted playsinline>`. No GIF, no audio.
- The **collage** has a fixed layout for now. Users arranging it themselves comes later.
- Layer caching (`reused_layers`) waits until layering wins the experiment.

## Open experiments (Nebius)

- [ ] **Clothes on the model**: does it keep the garment details (collar, tuck, length, prints)?
- [ ] **One call vs one call per layer** (base → outer → accessory): which is better?
- [ ] **3 views of the same person**: does seed + prompt stay consistent, or do side/back need
      the front as an image reference?
- [ ] **Missing clothes views**: how good is a generated side/back from the front photo alone?
      Do uploads need enhancing (background removal, straightening)?
- [ ] **Image-to-video turnaround**: does it keep the clothes the same while turning, and match the 3 stills?

## Code changes

### Remove
- [ ] User body photos: `BodyProfile.front_key/side_key/back_key`, `consent_at`, the
      photo upload in `PUT /users/{id}/body` (`backend/app/routers/profile.py`) and the upload
      and consent UI in `frontend/src/features/profile.tsx`.
- [ ] Uploaded backgrounds (`POST /users/{id}/backgrounds`, `backend/app/routers/backgrounds.py`).
      Presets can stay as generated, seeded scenes.
- [ ] `DefaultBody` photo keys become generated humans, or drop default bodies entirely.

### Add / change (backend)
- [ ] `models.py`: `HumanModel` (user_id, measurements, front/side/back keys, recipe, status);
      `Scene` (user_id, prompt, image key, recipe, status) replacing `Background`;
      `Item.side_key` + generated-view flags + recipe; `Job` gets `stills` {front, side, back},
      `video_key` and `video_status`, and drops `layers` for now.
- [ ] `generation.py`: `generate_human(measurements)`, `generate_scene(prompt)`,
      `complete_item_views(item)`, `render(human, clothes, scene) → 3 stills`,
      `make_video(stills) → mp4`. One Nebius client behind them. The API key stays on the server.
- [ ] `jobs.py`: replace the per-view loop in `_render` with render → stills → video. Video
      failure leaves the job's stills usable.
- [ ] New jobs for human, scene and item-view generation (same queued/running/done/failed shape).
- [ ] Run jobs in a worker that pulls `queued` jobs from Postgres, not `BackgroundTasks`, and mark
      stuck jobs failed.
- [x] `storage.py`: S3-compatible object storage (e.g. Nebius Object Storage), so generated
      files persist and Nebius can read inputs by presigned URL. Allow `video/mp4`.
- [ ] `rules.py`: `BodyRef` points at a `HumanModel`; validation checks it is `done`.
- [x] `collage.py`: build the collage from the 3 stills with Pillow (no AI).

### Add / change (contract + frontend)
- [ ] `openapi.yaml`: human model endpoints (create from measurements, regenerate, get), scene
      endpoints (create from prompt, regenerate, list), job response with `stills`, `video_url`,
      `video_status`, `collage_url`.
- [ ] `frontend/src/api/types.ts`, `client.ts`, `mocks/handlers.ts`, `mocks/generation.ts` to match.
- [ ] `features/profile.tsx`: measurements form → generate human → preview 3 views → regenerate.
- [ ] Scene picker: prompt → generate → pick (in `features/builder.tsx`).
- [ ] `features/results.tsx`: video player plus the 3 stills and the collage; video "generating"
      state after the stills appear.
- [ ] Tests: `test_profile.py`, `test_jobs.py`, `test_api_behavior.py`, `test_rules.py`,
      `test_contract.py`, and frontend `generation.test.ts`.
