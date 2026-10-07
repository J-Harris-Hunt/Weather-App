import os
from pathlib import Path
from contextlib import asynccontextmanager
import requests
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Support both standalone flet_fastapi and flet.fastapi module layouts
import flet.fastapi as flet_fastapi

import main

# Base filesystem directories
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
ASSETLINKS_PATH = ASSETS_DIR / "assetlinks.json"
MANIFEST_PATH = ASSETS_DIR / "manifest.json"


def auto_detect_location(client_ip: str = None):
    """
    Resolves geographic location via IP address.
    Returns the exact 4-element tuple expected by main.py:
    (search_query, latitude, longitude, display_label)
    """
    # Cloud hosting data center locations to guard against when Render IP is evaluated
    CLOUD_HUBS = ["Ashburn", "Boardman", "Council Bluffs", "Boydton"]

    try:
        url = f"https://ipapi.co/{client_ip}/json/" if client_ip else "https://ipapi.co/json/"
        resp = requests.get(
            url,
            timeout=3.5,
            headers={"User-Agent": "ThickMooseWeather/1.0 (thickmooselabs@gmail.com)"}
        )

        if resp.status_code == 200:
            data = resp.json()
            city = data.get("city") or "Wilmington"
            region = data.get("region_code") or "NC"
            postal = data.get("postal") or "28412"
            lat = float(data.get("latitude", 34.18))
            lon = float(data.get("longitude", -77.92))

            # If resolved to a cloud provider data center without an active client IP, fall back cleanly
            if city in CLOUD_HUBS and not client_ip:
                return ("28412", 34.18, -77.92, "Wilmington, NC")

            # search_query uses postal if present for NOAA resolution
            search_query = postal if postal else f"{city}, {region}"
            # display_label excludes misleading ISP switching hub ZIP codes
            display_label = f"{city}, {region}"

            return (search_query, lat, lon, display_label)
    except Exception as err:
        print(f"IP auto-detect resolution error: {err}")

    # Standard default baseline
    return ("28412", 34.18, -77.92, "Wilmington, NC")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages the Flet application manager lifecycle."""
    await flet_fastapi.app_manager.start()
    yield
    await flet_fastapi.app_manager.shutdown()


app = FastAPI(title="Thick Moose Weather Server", lifespan=lifespan)

# ---------------------------------------------------------------------------
# Google Play TWA & PWA Routes (Must be declared before root Flet mount)
# ---------------------------------------------------------------------------

@app.get("/.well-known/assetlinks.json", response_class=FileResponse)
async def serve_assetlinks():
    """Serves Digital Asset Links for TWA verification on Google Play."""
    if ASSETLINKS_PATH.exists():
        return FileResponse(
            path=str(ASSETLINKS_PATH),
            media_type="application/json"
        )
    return JSONResponse(status_code=404, content={"error": "assetlinks.json not found"})


@app.get("/manifest.json", response_class=FileResponse)
async def serve_manifest():
    """Serves PWA manifest file."""
    if MANIFEST_PATH.exists():
        return FileResponse(
            path=str(MANIFEST_PATH),
            media_type="application/manifest+json"
        )
    return JSONResponse(status_code=404, content={"error": "manifest.json not found"})


@app.get("/api/auto-locate")
async def api_auto_locate(request: Request):
    """
    Optional API endpoint to extract real client IP via proxy headers
    and return resolved coordinate tuple.
    """
    forwarded = request.headers.get("x-forwarded-for")
    client_ip = forwarded.split(",")[0].strip() if forwarded else request.client.host
    query, lat, lon, label = auto_detect_location(client_ip)
    return {
        "search_query": query,
        "latitude": lat,
        "longitude": lon,
        "display_label": label
    }


# Mount static assets directory
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

# ---------------------------------------------------------------------------
# Flet Root Application Mount (Must remain at the very end of route definitions)
# ---------------------------------------------------------------------------
app.mount("/", flet_fastapi.app(main.main))


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8550))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)