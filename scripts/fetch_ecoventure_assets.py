"""Download Ecoventure logo from public CDN (ecoventure.ca) into assets/."""
from __future__ import annotations

import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "ecoventure"
BASE = "https://images.squarespace-cdn.com/content/v1/66859ea5abc6ac408a0cd064"

ASSETS = {
    "icon_white.png": f"{BASE}/97d913f8-9b6d-4fbe-99ac-447ee13e1af6/Icon_White.png",
    "favicon.ico": f"{BASE}/e69c9b27-4240-4a1c-a5ef-fa42d29f1295/favicon.ico",
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, url in ASSETS.items():
        dest = OUT / name
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=30).read()
        dest.write_bytes(data)
        print(f"Wrote {dest} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
