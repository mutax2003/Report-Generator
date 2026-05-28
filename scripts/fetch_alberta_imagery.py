"""Download Alberta-themed landscape photos into assets/alberta/ (Unsplash License)."""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "alberta"

# Curated Unsplash photos — Alberta / prairie / Rockies / industry / wetlands theme.
# License: https://unsplash.com/license (free use with attribution appreciated).
SOURCES = [
    {
        "file": "rockies_lake.jpg",
        "url": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?auto=format&fit=crop&w=1200&q=80",
        "caption": "Rocky Mountains, Alberta",
        "credit": "Photo: Unsplash",
    },
    {
        "file": "prairie_sky.jpg",
        "url": "https://images.unsplash.com/photo-1465146633011-14f8e0781093?auto=format&fit=crop&w=1200&q=80",
        "caption": "Prairie sky, western Canada",
        "credit": "Photo: Unsplash",
    },
    {
        "file": "boreal_stream.jpg",
        "url": "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=1200&q=80",
        "caption": "Boreal forest and stream",
        "credit": "Photo: Unsplash",
    },
    {
        "file": "wetland_reeds.jpg",
        "url": "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?auto=format&fit=crop&w=1200&q=80",
        "caption": "Mist over wetland and forest",
        "credit": "Photo: Unsplash",
    },
    {
        "file": "prairie_wheat.jpg",
        "url": "https://images.unsplash.com/photo-1625246333195-78d9c38ad449?auto=format&fit=crop&w=1200&q=80",
        "caption": "Prairie cropland, Alberta basin",
        "credit": "Photo: Unsplash",
    },
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, str]] = []
    for i, item in enumerate(SOURCES):
        if i:
            time.sleep(1.5)
        dest = OUT / item["file"]
        req = urllib.request.Request(
            item["url"],
            headers={"User-Agent": "ESA-Report-Generator/1.0 (Ecoventure internal)"},
        )
        try:
            data = urllib.request.urlopen(req, timeout=90).read()
            if len(data) < 5000:
                print(f"SKIP {item['file']}: response too small")
                continue
            dest.write_bytes(data)
            print(f"OK {dest.name} ({len(data) // 1024} KB)")
            manifest.append(
                {
                    "file": item["file"],
                    "caption": item["caption"],
                    "credit": item["credit"],
                    "source_url": item["url"],
                }
            )
        except Exception as exc:
            print(f"SKIP {item['file']}: {exc}")
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {len(manifest)} image(s) to {OUT}")


if __name__ == "__main__":
    main()
