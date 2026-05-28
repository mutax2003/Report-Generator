# Alberta landscape imagery (fallback)

**Primary UI photos:** `samples/*.jpg` and `samples/*.webp` with captions in `samples/imagery_manifest.json`.

This folder is optional fallback if you run:

| File | Theme |
|------|--------|
| `rockies_lake.jpg` | Rocky Mountains |
| `prairie_sky.jpg` | Prairie sky |
| `boreal_stream.jpg` | Boreal forest |
| `wetland_reeds.jpg` | Wetland / forest mist |
| `prairie_wheat.jpg` | Prairie cropland (optional) |

**License:** [Unsplash License](https://unsplash.com/license) — free use; attribution in app captions.

**Refresh images:**

```powershell
python scripts\fetch_alberta_imagery.py
```

`manifest.json` stores captions shown in the UI.
