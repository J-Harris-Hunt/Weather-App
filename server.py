import os
import html
import json
import logging
import threading
import time
import requests
import math
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
import flet as ft
import flet.fastapi as flet_fastapi
from pathlib import Path
from fastapi.responses import FileResponse, JSONResponse
import main

try:
    import astro  # astro.py lives next to this file; the site still works if it is missing
except Exception:
    astro = None

load_dotenv()

logger = logging.getLogger("thickmoose")

# ---------------------------------------------------------------------------
# Small shared helpers: a tiny in-memory cache so repeated lookups (every user,
# every refresh) don't hammer free public APIs, and thread pools so independent
# lookups run side by side instead of one after another.
# ---------------------------------------------------------------------------
_CACHE = {}
_CACHE_LOCK = threading.Lock()
_POOL = ThreadPoolExecutor(max_workers=16)          # one weather request's independent lookups
_SPORTS_POOL = ThreadPoolExecutor(max_workers=8)    # leaf work for sports (kept separate to avoid pool deadlock)


def cached_get(url, ttl, timeout=3.5, headers=None, as_text=False):
    """GET a URL and return JSON (or text). Results are reused for `ttl` seconds.
    Raises on network errors / non-200 so callers can show an honest 'unavailable'."""
    key = (url, as_text)
    now = time.time()
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    data = resp.text if as_text else resp.json()
    with _CACHE_LOCK:
        if len(_CACHE) > 400:
            for k in [k for k, v in _CACHE.items() if now - v[0] > 3600]:
                _CACHE.pop(k, None)
            if len(_CACHE) > 400:
                _CACHE.clear()
        _CACHE[key] = (now, data)
    return data


def _result(future, default=None, label=""):
    """Get a background result without letting one failed lookup break everything else."""
    try:
        return future.result()
    except Exception as exc:
        logger.warning("Lookup failed (%s): %s", label or "unnamed", exc)
        return default


def _num(value, default):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else default


def _r1(value):
    return round(value, 1) if isinstance(value, (int, float)) else None

TEAM_STADIUM_MAP = {
    # Regional College
    "nc state": {"name": "NC State Wolfpack (NCAA)", "venue": "Carter-Finley Stadium (Raleigh, NC)", "lat": 35.7954, "lon": -78.7103, "indoor": False},
    "wolfpack": {"name": "NC State Wolfpack (NCAA)", "venue": "Carter-Finley Stadium (Raleigh, NC)", "lat": 35.7954, "lon": -78.7103, "indoor": False},
    "unc": {"name": "UNC Tar Heels (NCAA)", "venue": "Kenan Memorial Stadium (Chapel Hill, NC)", "lat": 35.9070, "lon": -79.0479, "indoor": False},
    "tar heels": {"name": "UNC Tar Heels (NCAA)", "venue": "Kenan Memorial Stadium (Chapel Hill, NC)", "lat": 35.9070, "lon": -79.0479, "indoor": False},
    "duke": {"name": "Duke Blue Devils (NCAA)", "venue": "Wallace Wade Stadium (Durham, NC)", "lat": 35.9953, "lon": -78.9418, "indoor": False},
    "wake forest": {"name": "Wake Forest Demon Deacons (NCAA)", "venue": "Allegacy Stadium (Winston-Salem, NC)", "lat": 36.1306, "lon": -80.2547, "indoor": False},
    "ecu": {"name": "ECU Pirates (NCAA)", "venue": "Dowdy-Ficklen Stadium (Greenville, NC)", "lat": 35.5964, "lon": -77.3653, "indoor": False},
    "app state": {"name": "App State Mountaineers (NCAA)", "venue": "Kidd Brewer Stadium (Boone, NC)", "lat": 36.2114, "lon": -81.6853, "indoor": False},
    "clemson": {"name": "Clemson Tigers (NCAA)", "venue": "Memorial Stadium (Clemson, SC)", "lat": 34.6788, "lon": -82.8432, "indoor": False},
    "georgia": {"name": "Georgia Bulldogs (NCAA)", "venue": "Sanford Stadium (Athens, GA)", "lat": 33.9498, "lon": -83.3734, "indoor": False},
    "tennessee": {"name": "Tennessee Volunteers (NCAA)", "venue": "Neyland Stadium (Knoxville, TN)", "lat": 35.9550, "lon": -83.9250, "indoor": False},

    # Pro Franchises
    "panthers": {"name": "Carolina Panthers (NFL)", "venue": "Bank of America Stadium (Charlotte, NC)", "lat": 35.2258, "lon": -80.8528, "indoor": False},
    "carolina panthers": {"name": "Carolina Panthers (NFL)", "venue": "Bank of America Stadium (Charlotte, NC)", "lat": 35.2258, "lon": -80.8528, "indoor": False},
    "georgia state panthers": {"name": "Georgia State Panthers (NCAA)", "venue": "Center Parc Stadium (Atlanta, GA)", "lat": 33.7353, "lon": -84.3894, "indoor": False},
    "braves": {"name": "Atlanta Braves (MLB)", "venue": "Truist Park (Atlanta, GA)", "lat": 33.8908, "lon": -84.4678, "indoor": False},
    "hurricanes": {"name": "Carolina Hurricanes (NHL)", "venue": "Lenovo Center (Raleigh, NC)", "lat": 35.8033, "lon": -78.7218, "indoor": True},
    "hornets": {"name": "Charlotte Hornets (NBA)", "venue": "Spectrum Center (Charlotte, NC)", "lat": 35.2251, "lon": -80.8392, "indoor": True},
    "chiefs": {"name": "Kansas City Chiefs (NFL)", "venue": "Arrowhead Stadium (Kansas City, MO)", "lat": 39.0489, "lon": -94.4839, "indoor": False},
    "cowboys": {"name": "Dallas Cowboys (NFL)", "venue": "AT&T Stadium (Arlington, TX)", "lat": 32.7473, "lon": -97.0945, "indoor": True},
    "eagles": {"name": "Philadelphia Eagles (NFL)", "venue": "Lincoln Financial Field (Philadelphia, PA)", "lat": 39.9008, "lon": -75.1675, "indoor": False},
    "broncos": {"name": "Denver Broncos (NFL)", "venue": "Empower Field at Mile High (Denver, CO)", "lat": 39.7439, "lon": -105.0201, "indoor": False},
    "dodgers": {"name": "Los Angeles Dodgers (MLB)", "venue": "Dodger Stadium (Los Angeles, CA)", "lat": 34.0739, "lon": -118.2400, "indoor": False},
    "yankees": {"name": "New York Yankees (MLB)", "venue": "Yankee Stadium (Bronx, NY)", "lat": 40.8296, "lon": -73.9262, "indoor": False},
    "red sox": {"name": "Boston Red Sox (MLB)", "venue": "Fenway Park (Boston, MA)", "lat": 42.3467, "lon": -71.0972, "indoor": False},
}

US_STATES = {
    "al": "Alabama", "ak": "Alaska", "az": "Arizona", "ar": "Arkansas", "ca": "California",
    "co": "Colorado", "ct": "Connecticut", "de": "Delaware", "fl": "Florida", "ga": "Georgia",
    "hi": "Hawaii", "id": "Idaho", "il": "Illinois", "in": "Indiana", "ia": "Iowa",
    "ks": "Kansas", "ky": "Kentucky", "la": "Louisiana", "me": "Maine", "md": "Maryland",
    "ma": "Massachusetts", "mi": "Michigan", "mn": "Minnesota", "ms": "Mississippi", "mo": "Missouri",
    "mt": "Montana", "ne": "Nebraska", "nv": "Nevada", "nh": "New Hampshire", "nj": "New Jersey",
    "nm": "New Mexico", "ny": "New York", "nc": "North Carolina", "nd": "North Dakota", "oh": "Ohio",
    "ok": "Oklahoma", "or": "Oregon", "pa": "Pennsylvania", "ri": "Rhode Island", "sc": "South Carolina",
    "sd": "South Dakota", "tn": "Tennessee", "tx": "Texas", "ut": "Utah", "vt": "Vermont",
    "va": "Virginia", "wa": "Washington", "wv": "West Virginia", "wi": "Wisconsin", "wy": "Wyoming",
    "dc": "District of Columbia", "pr": "Puerto Rico"
}
US_STATES_REVERSE = {v.lower(): k.upper() for k, v in US_STATES.items()}

GENERIC_STOPWORDS = {
    "state", "university", "tech", "college", "city", "north", "south",
    "east", "west", "central", "eastern", "western", "southern", "northern",
    "blue", "red", "golden", "green", "black", "white", "st", "saint",
    "football", "baseball", "basketball", "hockey", "mens", "womens", "the"
}

WMO_CODE_MAP = {
    0: "Clear", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing Rime Fog",
    51: "Light Drizzle", 53: "Moderate Drizzle", 55: "Dense Drizzle",
    56: "Light Freezing Drizzle", 57: "Dense Freezing Drizzle",
    61: "Slight Rain", 63: "Moderate Rain", 65: "Heavy Rain",
    66: "Light Freezing Rain", 67: "Heavy Freezing Rain",
    71: "Slight Snow", 73: "Moderate Snow", 75: "Heavy Snow", 77: "Snow Grains",
    80: "Rain Showers", 81: "Moderate Showers", 82: "Violent Showers",
    85: "Light Snow Showers", 86: "Heavy Snow Showers",
    95: "Thunderstorm", 96: "Thunderstorm w/ Hail", 99: "Heavy Hail Storm"
}

PRECIP_CODES = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99}

WILMINGTON_FALLBACK = ("28412", 34.1378, -77.9150, "Wilmington, NC (28412)")

def auto_detect_location(client_ip: str = None):
    CLOUD_HUBS = ["Ashburn", "Boardman", "Council Bluffs", "Boydton"]
    try:
        url = f"https://ipapi.co/{client_ip}/json/" if client_ip else "https://ipapi.co/json/"
        resp = requests.get(url, timeout=3.5, headers={"User-Agent": "ThickMooseWeather/1.0"})
        if resp.status_code == 200:
            data = resp.json()
            city = data.get("city") or "Wilmington"
            region = data.get("region_code") or "NC"
            postal = data.get("postal") or "28412"
            lat = float(data.get("latitude", 34.18))
            lon = float(data.get("longitude", -77.92))

            if city in CLOUD_HUBS and not client_ip:
                return ("28412", 34.18, -77.92, "Wilmington, NC")

            search_query = postal if postal else f"{city}, {region}"
            display_label = f"{city}, {region}"
            return (search_query, lat, lon, display_label)
    except Exception:
        pass
    return ("28412", 34.18, -77.92, "Wilmington, NC")

def get_coordinates(query: str):
    clean_q = str(query).strip()
    if not clean_q:
        return None, None, None, None

    if "," in clean_q:
        parts = [p.strip() for p in clean_q.split(",")]
        try:
            lat_f = float(parts[0])
            lon_f = float(parts[1])
            loc_label = f"Location ({round(lat_f, 3)}, {round(lon_f, 3)})"
            elev_ft = fetch_elevation_ft(lat_f, lon_f)
            return lat_f, lon_f, elev_ft, loc_label
        except ValueError:
            pass

    if clean_q.isdigit() and len(clean_q) == 5:
        try:
            zr = requests.get(f"https://api.zippopotam.us/us/{clean_q}", timeout=3).json()
            places = zr.get("places", [])
            if places:
                p = places[0]
                lat_f = float(p.get("latitude"))
                lon_f = float(p.get("longitude"))
                city = p.get("place name", clean_q)
                st = p.get("state abbreviation", "")
                elev_ft = fetch_elevation_ft(lat_f, lon_f)
                return lat_f, lon_f, elev_ft, f"{city}, {st} ({clean_q})"
        except Exception:
            pass

    zip_match = re.search(r'\b\d{5}\b', clean_q)
    extracted_zip = zip_match.group(0) if zip_match else ""

    parts = [p.strip() for p in clean_q.split(",") if p.strip()]
    detected_state_abbr = ""
    detected_city = ""

    for part in parts:
        p_lower = part.lower().strip()
        if p_lower in US_STATES:
            detected_state_abbr = p_lower.upper()
        elif p_lower in US_STATES_REVERSE:
            detected_state_abbr = US_STATES_REVERSE[p_lower]
        elif not detected_city and not part.isdigit():
            detected_city = part

    candidate_queries = [clean_q]
    if detected_city and detected_state_abbr:
        if extracted_zip:
            candidate_queries.insert(0, f"{detected_city}, {detected_state_abbr} {extracted_zip}")
        candidate_queries.append(f"{detected_city}, {detected_state_abbr}")

    headers = {"User-Agent": "ThickMooseWeather/2.0 (contact@thickmooselabs.com)"}
    for q_try in candidate_queries:
        try:
            nom_url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(q_try)}&format=json&addressdetails=1&limit=1"
            r = requests.get(nom_url, headers=headers, timeout=3.5).json()
            if r and len(r) > 0:
                item = r[0]
                lat_f = float(item["lat"])
                lon_f = float(item["lon"])
                addr = item.get("address", {})

                road = addr.get("road") or addr.get("pedestrian") or ""
                house_number = addr.get("house_number", "")
                neighbourhood = addr.get("neighbourhood") or addr.get("suburb") or ""
                city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("hamlet") or addr.get("county") or detected_city or "Local Area"
                state = addr.get("state") or addr.get("province") or detected_state_abbr
                postcode = addr.get("postcode", extracted_zip)
                country = addr.get("country", "")

                label_parts = []
                if house_number and road:
                    label_parts.append(f"{house_number} {road}")
                elif road:
                    label_parts.append(road)
                elif neighbourhood:
                    label_parts.append(neighbourhood)

                if city:
                    label_parts.append(city)
                if state:
                    label_parts.append(state)
                if postcode and postcode not in label_parts:
                    label_parts.append(f"({postcode})")
                elif country and country not in ["United States", "United States of America"]:
                    label_parts.append(country)

                loc_label = ", ".join([p for p in label_parts if p]) if label_parts else item.get("display_name", clean_q)
                elev_ft = fetch_elevation_ft(lat_f, lon_f)
                return lat_f, lon_f, elev_ft, loc_label
        except Exception:
            pass

    if extracted_zip:
        try:
            zr = requests.get(f"https://api.zippopotam.us/us/{extracted_zip}", timeout=3).json()
            places = zr.get("places", [])
            if places:
                p = places[0]
                lat_f = float(p.get("latitude"))
                lon_f = float(p.get("longitude"))
                city = p.get("place name", detected_city or extracted_zip)
                st = p.get("state abbreviation", detected_state_abbr)
                elev_ft = fetch_elevation_ft(lat_f, lon_f)
                return lat_f, lon_f, elev_ft, f"{city}, {st} ({extracted_zip})"
        except Exception:
            pass

    city_candidate = detected_city or re.sub(r'[\d,]', '', clean_q).strip()
    if city_candidate:
        try:
            r = requests.get(
                f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(city_candidate)}&count=5&language=en&format=json",
                timeout=3.5
            ).json()
            res_list = r.get("results", [])
            if res_list:
                matched_target = res_list[0]
                if detected_state_abbr:
                    for item in res_list:
                        admin = (item.get("admin1") or "").lower()
                        if detected_state_abbr.lower() in admin or (US_STATES.get(detected_state_abbr.lower(), "").lower() in admin):
                            matched_target = item
                            break

                lat_f = float(matched_target["latitude"])
                lon_f = float(matched_target["longitude"])
                name = matched_target.get("name", city_candidate)
                admin1 = matched_target.get("admin1", "")
                elev_m = matched_target.get("elevation")
                elev_ft = round(elev_m * 3.28084) if elev_m is not None else fetch_elevation_ft(lat_f, lon_f)
                label = f"{name}, {admin1}" if admin1 else name
                return lat_f, lon_f, elev_ft, label
        except Exception:
            pass

    return None, None, None, None

def fetch_elevation_ft(lat: float, lon: float):
    """Elevation in feet, or None if the lookup fails (we no longer invent 50 ft)."""
    try:
        url = f"https://api.open-meteo.com/v1/elevation?latitude={round(lat, 4)}&longitude={round(lon, 4)}"
        res = cached_get(url, 7 * 86400, timeout=2.5)
        elev = res.get("elevation")
        if isinstance(elev, list) and elev and elev[0] is not None:
            return round(elev[0] * 3.28084)
    except Exception as exc:
        logger.warning("Elevation lookup failed: %s", exc)
    return None

def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 6371.0 * 2 * math.asin(min(1.0, math.sqrt(a)))


_TIDE_STATIONS_URL = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json?type=tidepredictions"


def nearest_tide_station(lat: float, lon: float, max_km: float = 60.0):
    """Nearest NOAA tide-prediction station within max_km, or None."""
    try:
        data = cached_get(_TIDE_STATIONS_URL, 86400, timeout=6)
        best, best_d = None, 1e12
        for s in data.get("stations", []):
            try:
                d = haversine_km(lat, lon, float(s["lat"]), float(s["lng"]))
            except (KeyError, TypeError, ValueError):
                continue
            if d < best_d:
                best, best_d = s, d
        if best is not None and best_d <= max_km:
            return {"id": str(best.get("id")), "name": best.get("name", "NOAA station"),
                    "state": best.get("state", ""), "distance_km": round(best_d, 1)}
    except Exception as exc:
        logger.warning("Tide station lookup failed: %s", exc)
    return None


def is_coastal_region(station) -> bool:
    """Coastal = a NOAA tide station within ~30 km (replaces the old rectangles that
    treated all of Europe/Asia/Africa and cities like Spokane or Reno as 'coastal')."""
    return bool(station and station.get("distance_km", 999) <= 30.0)


def fetch_noaa_tides(station):
    """Real NOAA high/low tide predictions for the nearest station, or None."""
    if not station:
        return None
    try:
        url = (
            "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?date=today"
            f"&station={station['id']}&product=predictions&datum=MLLW&time_zone=lst_ldt"
            "&interval=hilo&units=english&format=json"
        )
        res = cached_get(url, 1800, timeout=3.5)
        predictions = res.get("predictions") or []
        if not predictions:
            return None
        miles = round(station["distance_km"] * 0.621371)
        where = f"{station['name']}{', ' + station['state'] if station.get('state') else ''}"
        lines = [f"NOAA tide predictions — {where} (station {station['id']}, ~{miles} mi away):"]
        for p in predictions[:4]:
            t_type = "High Tide" if p.get("type") == "H" else "Low Tide"
            dt_obj = datetime.strptime(p.get("t"), "%Y-%m-%d %H:%M")
            t_str = dt_obj.strftime("%I:%M %p").lstrip("0")
            lines.append(f"• {t_str}: {t_type} ({p.get('v', '?')} ft MLLW)")
        return "\n".join(lines)
    except Exception as exc:
        logger.warning("Tide prediction lookup failed: %s", exc)
        return None


def fetch_enso():
    """Latest NOAA CPC Oceanic Niño Index (ONI), classified. Returns text, or None."""
    try:
        text = cached_get("https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt", 43200, timeout=4, as_text=True)
        rows = [ln.split() for ln in text.splitlines()]
        rows = [r for r in rows if len(r) >= 4 and r[0].isalpha() and r[1].isdigit()]
        if not rows:
            return None
        season, year, _total, anom_s = rows[-1][:4]
        anom = float(anom_s)
        if anom >= 0.5:
            phase = "El Niño"
        elif anom <= -0.5:
            phase = "La Niña"
        else:
            phase = "ENSO-neutral"
        mag = abs(anom)
        strength = "" if phase == "ENSO-neutral" else (
            "weak " if mag < 1.0 else "moderate " if mag < 1.5 else "strong " if mag < 2.0 else "very strong ")
        return (f"NOAA CPC Oceanic Niño Index for {season} {year}: {anom:+.1f}°C → {strength}{phase} conditions. "
                "(ONI is a 3-month average of Niño 3.4 sea-surface temperature anomalies, updated monthly.)")
    except Exception as exc:
        logger.warning("ENSO lookup failed: %s", exc)
        return None


def fetch_noaa_alerts(lat: float, lon: float):
    """Active NWS alerts for the point. Returns (general_text, tropical_text).
    A failed lookup says so instead of claiming 'no active alerts'."""
    headers = {"User-Agent": "ThickMooseWeather/2.0 (contact@thickmooselabs.com)"}
    unavailable = "NWS alerts are unavailable right now (the service may be busy, or this location is outside the U.S.)."
    try:
        url = f"https://api.weather.gov/alerts/active?point={round(lat, 4)},{round(lon, 4)}"
        res = cached_get(url, 120, timeout=3.5, headers=headers)
        features = res.get("features")
        if features is None:
            return unavailable, unavailable
        extreme_alerts, tropical_alerts = [], []
        for f in features:
            props = f.get("properties", {})
            event = props.get("event", "Weather Alert")
            headline = props.get("headline") or props.get("description", "")
            short_line = headline.splitlines()[0] if headline else event
            alert_entry = f"⚠️ {event}: {short_line}"
            if any(term in event.lower() for term in ["tropical", "hurricane", "surge", "gale", "cyclone"]):
                tropical_alerts.append(alert_entry)
            else:
                extreme_alerts.append(alert_entry)
        extreme_text = " | ".join(extreme_alerts) if extreme_alerts else "No active National Weather Service alerts for this location."
        tropical_text = " | ".join(tropical_alerts) if tropical_alerts else "No active tropical-storm, hurricane or storm-surge alerts from the National Weather Service for this location."
        return extreme_text, tropical_text
    except Exception as exc:
        logger.warning("NWS alerts lookup failed: %s", exc)
        return unavailable, unavailable


def fetch_live_aqi(lat: float, lon: float):
    unavailable = {"aqi": None, "value": None, "category": "Unavailable", "pm25": None, "status": "Unavailable"}
    try:
        url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current=us_aqi,pm2_5,pm10"
        res = cached_get(url, 600, timeout=3.5)
        curr_aq = res.get("current") or {}
        raw = curr_aq.get("us_aqi")
        if raw is None:
            return unavailable
        val = int(round(raw))
        if val <= 50:
            cat = "Good"
        elif val <= 100:
            cat = "Moderate"
        elif val <= 150:
            cat = "Unhealthy for Sensitive Groups"
        elif val <= 200:
            cat = "Unhealthy"
        elif val <= 300:
            cat = "Very Unhealthy"
        else:
            cat = "Hazardous"
        return {"aqi": val, "value": val, "category": cat, "pm25": curr_aq.get("pm2_5"), "status": f"{val} ({cat})"}
    except Exception as exc:
        logger.warning("AQI lookup failed: %s", exc)
        return unavailable

def dew_point_f(temp_f: float, rh: float):
    """Dew point in °F using the Magnus formula (the old shortcut was a °C rule applied to °F)."""
    try:
        rh = max(1.0, min(100.0, float(rh)))
        t_c = (temp_f - 32.0) * 5.0 / 9.0
        a, b = 17.62, 243.12
        g = math.log(rh / 100.0) + (a * t_c) / (b + t_c)
        td_c = (b * g) / (a - g)
        return round(td_c * 9.0 / 5.0 + 32.0)
    except Exception:
        return None


def clothing_advice(temp_f: float) -> str:
    if temp_f < 32:
        return "Freezing: heavy coat, hat, gloves and insulated layers."
    if temp_f < 45:
        return "Cold: winter coat or heavy jacket over a warm layer."
    if temp_f < 55:
        return "Cool: light jacket or fleece with long sleeves."
    if temp_f < 65:
        return "Mild: a sweater or light layer you can shed."
    if temp_f < 75:
        return "Comfortable: long or short sleeves, with a light layer for shade or breeze."
    if temp_f < 85:
        return "Warm: breathable short sleeves, shorts or light pants."
    if temp_f < 95:
        return "Hot: lightweight, light-colored breathable fabrics, a hat and plenty of water."
    return "Very hot: minimal breathable layers, sun protection, and limit midday exertion."


def uv_label(uv: float) -> str:
    if uv < 3:
        return "Low"
    if uv < 6:
        return "Moderate"
    if uv < 8:
        return "High"
    if uv < 11:
        return "Very High"
    return "Extreme"


def foliage_status(lat: float, elev_ft, is_coast: bool, today: datetime) -> str:
    """Date-aware autumn-foliage ESTIMATE (clearly labelled as an estimate, not an observation)."""
    if lat < 0:
        return "Autumn foliage estimate covers the Northern Hemisphere only."
    if lat < 25.0:
        return "No seasonal autumn foliage change at this latitude (evergreen / tropical canopy)."
    month = today.month
    if month in (12, 1, 2, 3):
        return "Dormant season: deciduous trees are bare. Evergreens hold their color."
    if month in (4, 5):
        return "Spring leaf-out: deciduous canopies are filling in with fresh green."
    if month in (6, 7, 8):
        return "Summer: full green canopy. Fall color has not started."
    # September-November: estimate the peak-color day from latitude, elevation and coast.
    peak_doy = 288.0 + (40.0 - lat) * 3.5          # ~Oct 15 at 40°N; later to the south, earlier to the north
    peak_doy -= 4.0 * (min(elev_ft, 6000) / 1000.0) if elev_ft else 0.0
    peak_doy += 7.0 if is_coast else 0.0
    peak_date = datetime(today.year, 1, 1) + timedelta(days=int(peak_doy) - 1)
    diff = today.timetuple().tm_yday - peak_doy
    if diff < -35:
        stage = "Mostly green canopy; color change has not really started."
    elif diff < -21:
        stage = "Early signs: scattered early-turning maples and sumac (roughly 5-15% color)."
    elif diff < -10:
        stage = "Color is building (roughly 15-40%)."
    elif diff < -3:
        stage = "Approaching peak (roughly 40-70% color)."
    elif diff <= 7:
        stage = "At or near peak color (roughly 70-100%)."
    elif diff <= 18:
        stage = "Past peak; leaves are dropping (roughly half down)."
    elif diff <= 35:
        stage = "Late season; most leaves have fallen."
    else:
        stage = "Leaves are down for the season."
    return (f"{stage} Estimated peak around {peak_date.strftime('%b %d').replace(' 0', ' ')} (give or take 1-2 weeks). "
            "This is an estimate from latitude, elevation and date, not a field report.")


def _g(item, action, timing):
    return {"item": item, "action": action, "timing": timing}


_GARDEN = {
    ("cold", "spring"): [
        _g("Peas, Spinach & Radishes", "Direct Sow", "As soon as soil is workable"),
        _g("Onions & Brassica Transplants", "Harden Off & Plant", "2-4 weeks before last frost"),
        _g("Tomatoes & Peppers", "Hold Indoors", "Wait until frost danger has passed"),
    ],
    ("cold", "summer"): [
        _g("Lettuce & Greens", "Succession Sow", "Use shade cloth in heat spells"),
        _g("Warm-Season Crops", "Peak Growing", "Water deeply and keep harvesting"),
        _g("Garlic", "Harvest", "When the lower leaves turn brown"),
    ],
    ("cold", "fall"): [
        _g("Cold-Hardy Greens & Roots", "Row Cover Production", "Harvest steadily; protect crowns from hard frost"),
        _g("Garlic & Perennial Alliums", "Pre-Freeze Planting Window", "Plant cloves 4-6 weeks before the ground freezes"),
        _g("Winter Mulch", "Bed Winterization", "Mulch perennial crowns and berry canes"),
    ],
    ("cold", "winter"): [
        _g("Onions & Peppers", "Start Seeds Indoors", "Late winter, 8-10 weeks before last frost"),
        _g("Apple & Pear Trees", "Dormant Pruning", "Late winter on mild days"),
        _g("Perennial Beds", "Mulch & Snow Cover", "Keep crowns insulated through freeze-thaw cycles"),
    ],
    ("temperate", "spring"): [
        _g("Peas, Lettuce & Spinach", "Direct Sow", "As soil warms to roughly 40-50°F"),
        _g("Potatoes", "Plant Seed Potatoes", "2-4 weeks before last frost"),
        _g("Tomatoes & Peppers", "Transplant", "After the last frost date"),
    ],
    ("temperate", "summer"): [
        _g("Beans, Squash & Cucumbers", "Peak Harvest", "Pick often to keep plants producing"),
        _g("Broccoli & Cabbage", "Start Fall Seedlings", "Mid to late summer"),
        _g("Garden Beds", "Deep Watering", "About an inch per week; mulch to hold moisture"),
    ],
    ("temperate", "fall"): [
        _g("Cool-Season Brassicas", "Direct Sowing Window", "Sow cold-hardy greens through late autumn"),
        _g("Garlic & Shallots", "Pre-Winter Planting", "Plant cloves before deep frost"),
        _g("Cover Crops (Clover / Winter Rye)", "Soil Shield Sowing", "Establish before cold dormancy"),
    ],
    ("temperate", "winter"): [
        _g("Seed Orders & Garden Plan", "Plan", "Order seeds and map crop rotation"),
        _g("Fruit Trees & Grapes", "Dormant Pruning", "Late winter before buds swell"),
        _g("Kale & Spinach", "Protect Under Cover", "Row cover keeps hardy greens producing"),
    ],
    ("warm", "spring"): [
        _g("Tomatoes, Peppers & Okra", "Transplant", "After the last frost, early spring"),
        _g("Beans & Cucumbers", "Direct Sow", "As soil passes 65°F"),
        _g("Melons & Sweet Potatoes", "Plant", "Once soil is reliably warm"),
    ],
    ("warm", "summer"): [
        _g("Okra, Southern Peas & Sweet Potatoes", "Peak Growing", "Heat-loving crops thrive now"),
        _g("Broccoli & Cabbage Transplants", "Start for Fall", "Late summer"),
        _g("Garden Beds", "Mulch & Water Deeply", "Water early in the day"),
    ],
    ("warm", "fall"): [
        _g("Kale, Collards & Spinach", "Active Sowing Window", "Prime direct seeding through autumn and winter"),
        _g("Fall Tomatoes & Peppers", "Extended Late Harvest", "Fruit set continues until the first frost"),
        _g("Carrots, Radishes & Turnips", "Direct Sowing Window", "Soil temperatures favor root crops"),
    ],
    ("warm", "winter"): [
        _g("Kale, Collards & Lettuce", "Grow & Harvest", "Protect from rare hard freezes"),
        _g("Citrus & Fruit Trees", "Freeze Protection & Pruning", "Cover on frost nights; prune after the last freeze"),
        _g("Tomatoes & Peppers", "Start Seeds Indoors", "Late winter for spring transplanting"),
    ],
}


def garden_guide(lat: float, elev_ft, today: datetime):
    month = today.month if lat >= 0 else ((today.month + 5) % 12) + 1  # flip seasons in the Southern Hemisphere
    season = "winter" if month in (12, 1, 2) else "spring" if month in (3, 4, 5) else "summer" if month in (6, 7, 8) else "fall"
    if abs(lat) >= 44.0 or (elev_ft or 0) >= 3500:
        band = "cold"
    elif abs(lat) <= 33.0:
        band = "warm"
    else:
        band = "temperate"
    return _GARDEN[(band, season)]


def generate_microclimate_profile(lat: float, lon: float, elev_ft, location_name: str, is_coast: bool, tide_text, station, today: datetime):
    garden_season = garden_guide(lat, elev_ft, today)
    elev_known = elev_ft is not None
    elev_txt = f"{elev_ft:,} ft" if elev_known else "unknown"

    if elev_known and elev_ft >= 3000:
        micro_memo = f"High-Altitude Sector (Elev. {elev_txt}): Rapid nighttime radiation cooling with valley inversions possible."
        boating_body = f"Mountain Lakes & High-Elevation Reservoirs ({location_name})"
    elif elev_known and elev_ft >= 1000:
        micro_memo = f"Upland / Piedmont Terrain (Elev. {elev_txt}): Wider day-to-night temperature swings than the coast."
        boating_body = f"Regional Freshwater Reservoirs & River Basins ({location_name})"
    elif is_coast:
        micro_memo = f"Coastal Zone (Elev. {elev_txt}): Nearby water moderates daytime highs and nighttime lows; sea breezes are common."
        boating_body = f"Coastal Waters, Sounds & Tidal Rivers ({location_name})"
    else:
        micro_memo = f"Inland Lowland (Elev. {elev_txt}): Cool air can pool in low spots overnight."
        boating_body = f"Regional Rivers & Inland Lakes ({location_name})"

    if tide_text:
        tides_desc = tide_text
    elif station:
        tides_desc = "Tide predictions are temporarily unavailable. Please try again shortly."
    elif elev_known and elev_ft >= 1000:
        tides_desc = "Not applicable: inland, non-tidal location."
    else:
        tides_desc = "No NOAA tide station within about 37 miles of this location."

    return micro_memo, boating_body, tides_desc, garden_season


def calculate_6hr_forecast_metrics(curr_temp, curr_wind, hourly_36):
    usable = [h for h in hourly_36[:6] if h.get("temp") is not None]
    if not usable:
        return curr_temp, curr_wind, 0, "6-Hour Outlook: hourly forecast unavailable right now"
    weights = [1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125]
    t_sum = w_sum = total_w = 0.0
    max_rain = 0
    for i, h in enumerate(usable):
        weight = weights[i]
        t_sum += h["temp"] * weight
        w_sum += _num(h.get("wind_mph"), curr_wind) * weight
        total_w += weight
        r_val = h.get("rain_chance")
        if r_val is not None and r_val > max_rain:
            max_rain = r_val
    avg_temp = round(t_sum / total_w)
    avg_wind = round(w_sum / total_w, 1)
    trend_note = f"6-Hour Outlook: Expected ~{avg_temp}°F, winds ~{avg_wind} mph, max rain risk {max_rain}%"
    return avg_temp, avg_wind, max_rain, trend_note

def calculate_team_match_score(query: str, d_name: str, s_name: str, short_d: str, abbrev: str):
    q = query.lower().strip()
    d_name = d_name.lower().strip()
    s_name = s_name.lower().strip()
    short_d = short_d.lower().strip()
    abbrev = abbrev.lower().strip()

    if q in [d_name, short_d, abbrev]:
        return 100
    if q == s_name and q not in GENERIC_STOPWORDS:
        return 92

    if any(alias in q for alias in ["nc state", "ncsu", "wolfpack"]):
        if "north carolina state" in d_name or "nc state" in short_d or s_name == "wolfpack":
            return 98

    if q in d_name:
        return 88
    if short_d in q or (s_name in q and s_name not in GENERIC_STOPWORDS):
        return 82

    q_words = [w for w in q.split() if w not in GENERIC_STOPWORDS and len(w) > 2]
    if q_words:
        matches = [w for w in q_words if w in d_name or w in s_name]
        if len(matches) == len(q_words):
            return 80
        if len(matches) > 0 and len(q_words) == 1 and matches[0] in [s_name, short_d]:
            return 75

    return 0

_VENUE_GEO_CACHE = {}


def geocode_venue_cached(query: str):
    """(lat, lon) for a venue city, remembered after the first success."""
    if query in _VENUE_GEO_CACHE:
        return _VENUE_GEO_CACHE[query]
    lat, lon, _elev, _label = get_coordinates(query)
    if lat is not None and lon is not None:
        _VENUE_GEO_CACHE[query] = (lat, lon)
        return lat, lon
    return None, None


def resolve_venue_location(home_team_name: str, venue_city: str, venue_state: str):
    """Where the game is actually played: the HOME team's venue, never the searched team's."""
    home_l = (home_team_name or "").lower()
    city_l = (venue_city or "").lower()
    for key in sorted(TEAM_STADIUM_MAP, key=len, reverse=True):
        val = TEAM_STADIUM_MAP[key]
        if re.search(rf"\b{re.escape(key)}\b", home_l) and (not city_l or city_l in val["venue"].lower()):
            return val["lat"], val["lon"], val.get("indoor", False)
    if venue_city:
        query = f"{venue_city}, {venue_state}" if venue_state else venue_city
        lat, lon = geocode_venue_cached(query)
        if lat is not None:
            return lat, lon, None
    return None, None, None


def fetch_stadium_live_weather(lat, lon, is_indoor: bool = False):
    if lat is None or lon is None:
        return "Stadium weather unavailable (venue location could not be determined)."
    try:
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={round(lat, 4)}&longitude={round(lon, 4)}"
               "&current=temperature_2m,weather_code,wind_speed_10m&temperature_unit=fahrenheit&wind_speed_unit=mph")
        res = cached_get(url, 300, timeout=3.5)
        curr = res.get("current") or {}
        if curr.get("temperature_2m") is None:
            raise ValueError("no temperature in response")
        t = round(curr["temperature_2m"])
        w = round(_num(curr.get("wind_speed_10m"), 0.0), 1)
        cond = WMO_CODE_MAP.get(curr.get("weather_code"), "Conditions unavailable")
        if is_indoor:
            return f"Outdoor: {t}°F, {cond}, Wind {w} mph • Indoor / climate-controlled venue"
        return f"{t}°F, {cond}, Wind {w} mph"
    except Exception as exc:
        logger.warning("Stadium weather lookup failed: %s", exc)
        return "Stadium weather temporarily unavailable."


_SPORT_LEAGUES = [
    ("football", "nfl", "NFL", "limit=100"),
    ("baseball", "mlb", "MLB", "limit=100"),
    ("football", "college-football", "NCAA", "groups=80&limit=100"),
    ("hockey", "nhl", "NHL", "limit=100"),
    ("basketball", "nba", "NBA", "limit=100"),
]


def _fetch_scoreboard(spec):
    sport, league_path, _tag, q_params = spec
    url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league_path}/scoreboard?{q_params}"
    try:
        return cached_get(url, 60, timeout=3.5, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    except Exception as exc:
        logger.warning("ESPN scoreboard failed (%s): %s", league_path, exc)
        return None


def fetch_live_sports_events(sport_query: str):
    events = []
    default_teams = ["panthers", "braves", "nc state"]
    active_search = [s.strip().lower() for s in (sport_query or "").split(",") if s.strip()] or default_teams

    # Fetch each league's scoreboard once (in parallel, cached 60 s) and reuse it for every team.
    boards = list(_SPORTS_POOL.map(_fetch_scoreboard, _SPORT_LEAGUES))
    if all(b is None for b in boards):
        return [{
            "title": "Live sports data is temporarily unavailable",
            "venue": "", "time": "Please try again in a minute.", "score": "", "conditions": "", "alternatives": [],
        }]

    for raw_s_key in active_search:
        clean_key = re.sub(r'\b(football|baseball|basketball|hockey|soccer|mens|womens|men\'s|women\'s|matchup|game)\b', '', raw_s_key, flags=re.IGNORECASE).strip()
        candidates = []

        for spec, board in zip(_SPORT_LEAGUES, boards):
            if not board:
                continue
            league_tag = spec[2]
            for ev in board.get("events", []):
                comp = (ev.get("competitions") or [{}])[0]
                competitors = comp.get("competitors", [])

                for c in competitors:
                    t_info = c.get("team", {})
                    d_name = t_info.get("displayName", "")
                    s_name = t_info.get("name", "")
                    short_d = t_info.get("shortDisplayName", "")
                    abbrev = t_info.get("abbreviation", "")

                    score = calculate_team_match_score(clean_key or raw_s_key, d_name, s_name, short_d, abbrev)
                    if score >= 70:
                        venue = comp.get("venue", {})
                        v_name = venue.get("fullName", "Stadium")
                        city = venue.get("address", {}).get("city", "")
                        state = venue.get("address", {}).get("state", "")
                        venue_str = f"{v_name} ({city}, {state})" if city else v_name
                        espn_indoor = bool(venue.get("indoor", False))

                        home_comp = next((x for x in competitors if x.get("homeAway") == "home"), None)
                        home_name = (home_comp or {}).get("team", {}).get("displayName", "")
                        v_lat, v_lon, map_indoor = resolve_venue_location(home_name, city, state)
                        is_indoor = espn_indoor or bool(map_indoor)

                        date_str = ev.get("date", "")
                        status_type = ev.get("status", {}).get("type", {})
                        status_str = status_type.get("detail", "")
                        state_val = status_type.get("state", "")

                        live_game_score = ""
                        if competitors and len(competitors) >= 2:
                            away_comp = next((x for x in competitors if x.get("homeAway") == "away"), competitors[0])
                            home_c = next((x for x in competitors if x.get("homeAway") == "home"), competitors[1])
                            away_abbr = away_comp.get("team", {}).get("abbreviation") or away_comp.get("team", {}).get("shortDisplayName") or "AWAY"
                            home_abbr = home_c.get("team", {}).get("abbreviation") or home_c.get("team", {}).get("shortDisplayName") or "HOME"
                            a_score = away_comp.get("score")
                            h_score = home_c.get("score")
                            if a_score is not None and h_score is not None and str(a_score) != "" and str(h_score) != "" and state_val in ["in", "post"]:
                                live_game_score = f"{away_abbr} {a_score} - {h_score} {home_abbr}"

                        try:
                            dt_obj = datetime.fromisoformat(date_str.replace("Z", "+00:00")).astimezone(ZoneInfo("America/New_York"))
                            time_formatted = dt_obj.strftime("%A %I:%M %p %Z")  # shows EDT or EST correctly
                        except Exception:
                            time_formatted = status_str or "Game time TBD"

                        candidates.append({
                            "score_rank": score,
                            "matched_team": f"{d_name} ({league_tag})",
                            "title": ev.get("name", raw_s_key.title()),
                            "venue": venue_str,
                            "time": f"{time_formatted} • {status_str}" if status_str and status_str != time_formatted else time_formatted,
                            "game_score": live_game_score,
                            "lat": v_lat, "lon": v_lon, "indoor": is_indoor,
                            "league_tag": league_tag
                        })
                        break

        if candidates:
            candidates.sort(key=lambda x: x["score_rank"], reverse=True)
            top = candidates[0]
            cond_str = fetch_stadium_live_weather(top["lat"], top["lon"], top["indoor"])

            alternatives = []
            seen_alts = {top["matched_team"]}
            for cand in candidates[1:]:
                alt_name = cand["matched_team"]
                if alt_name not in seen_alts and len(alternatives) < 3:
                    seen_alts.add(alt_name)
                    clean_alt_query = cand["matched_team"].split("(")[0].strip()
                    alternatives.append({"name": alt_name, "query": clean_alt_query})

            events.append({
                "title": top["title"],
                "venue": top["venue"],
                "time": top["time"],
                "score": top.get("game_score", ""),
                "conditions": cond_str,
                "alternatives": alternatives
            })
        else:
            matched_val = None
            if clean_key:
                for k in sorted(TEAM_STADIUM_MAP, key=len, reverse=True):
                    if re.search(rf"\b{re.escape(k)}\b", clean_key) or re.search(rf"\b{re.escape(clean_key)}\b", k):
                        matched_val = TEAM_STADIUM_MAP[k]
                        break
            if matched_val:
                events.append({
                    "title": matched_val["name"],
                    "venue": matched_val["venue"],
                    "time": "No game found on today's scoreboard",
                    "score": "",
                    "conditions": "Home venue right now: " + fetch_stadium_live_weather(matched_val["lat"], matched_val["lon"], matched_val.get("indoor", False)),
                    "alternatives": []
                })
            elif raw_s_key:
                events.append({
                    "title": f"{raw_s_key.title()}",
                    "venue": "",
                    "time": "No matching team or game found. Try the full team name (for example, 'Atlanta Braves').",
                    "score": "",
                    "conditions": "",
                    "alternatives": []
                })

    return events

def _describe_window(codes):
    """One plain-English description for a stretch of hourly weather codes."""
    codes = [c for c in codes if c is not None]
    if not codes:
        return None
    if any(c >= 95 for c in codes):
        return WMO_CODE_MAP.get(max(codes), "Thunderstorm")
    precip = [c for c in codes if c in PRECIP_CODES]
    if len(precip) >= max(2, len(codes) // 4):
        pool = precip
    else:
        pool = [c for c in codes if c not in PRECIP_CODES] or codes
    top = max(set(pool), key=pool.count)
    return WMO_CODE_MAP.get(top, "Mixed conditions")


def _fmt_clock(dt_obj):
    return dt_obj.strftime("%I:%M %p").lstrip("0")


def fetch_comprehensive_weather(lat: float, lon: float):
    """Returns (current, hourly_36, daily_5, sun_times, tz).
    `current` is None when Open-Meteo is unreachable - the caller then reports 'unavailable'
    instead of inventing weather."""
    headers = {"User-Agent": "ThickMooseWeather/2.0 (contact@thickmooselabs.com)"}
    curr_obs = None
    raw_hourly = []
    daily_forecasts = []
    daily_dates = []
    sun_times = {"sunrise": None, "sunset": None, "sunrise_dt": None, "sunset_dt": None}
    resolved_tz = timezone.utc

    try:
        om_url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,surface_pressure,uv_index,wind_speed_10m,wind_direction_10m,weather_code,is_day"
            f"&hourly=temperature_2m,relative_humidity_2m,apparent_temperature,surface_pressure,uv_index,wind_speed_10m,precipitation_probability,weather_code,cloud_cover"
            f"&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max,sunrise,sunset"
            f"&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=auto&forecast_days=7"
        )
        om_res = cached_get(om_url, 120, timeout=5)
        try:
            resolved_tz = ZoneInfo(om_res.get("timezone") or "")
        except Exception:
            resolved_tz = timezone.utc

        def _at(arr, i):
            return arr[i] if isinstance(arr, list) and i < len(arr) else None

        curr_data = om_res.get("current") or {}
        t_raw = curr_data.get("temperature_2m")
        if t_raw is not None:
            feels_raw = curr_data.get("apparent_temperature")
            feels = round(feels_raw) if feels_raw is not None else None
            is_day_raw = curr_data.get("is_day")
            curr_obs = {
                "temp": round(t_raw),
                "condition": WMO_CODE_MAP.get(curr_data.get("weather_code"), "Conditions unavailable"),
                "wind": _r1(curr_data.get("wind_speed_10m")),
                "wind_direction": _r1(curr_data.get("wind_direction_10m")),
                "humidity": _r1(curr_data.get("relative_humidity_2m")),
                "pressure_hpa": _r1(curr_data.get("surface_pressure")),
                "uv_index": curr_data.get("uv_index"),
                "heat_index": feels,
                "feels_like": feels,
                "is_night": (is_day_raw == 0) if is_day_raw is not None else None,
            }

        dd = om_res.get("daily") or {}
        dates = dd.get("time") or []
        highs = dd.get("temperature_2m_max") or []
        lows = dd.get("temperature_2m_min") or []
        precips = dd.get("precipitation_probability_max") or []
        uv_maxs = dd.get("uv_index_max") or []
        codes = dd.get("weather_code") or []
        sunrises = dd.get("sunrise") or []
        sunsets = dd.get("sunset") or []

        # Open-Meteo returns LOCAL wall-clock times with no offset, so keep them "naive"
        # and attach the location's timezone - never convert them as if they were server time.
        sr_naive = [datetime.fromisoformat(s) if s else None for s in sunrises]
        ss_naive = [datetime.fromisoformat(s) if s else None for s in sunsets]
        if sr_naive and sr_naive[0]:
            sun_times["sunrise"] = _fmt_clock(sr_naive[0])
            sun_times["sunrise_dt"] = sr_naive[0]
        if ss_naive and ss_naive[0]:
            sun_times["sunset"] = _fmt_clock(ss_naive[0])
            sun_times["sunset_dt"] = ss_naive[0]

        h_data = om_res.get("hourly") or {}
        h_times = h_data.get("time") or []
        h_naive = [datetime.fromisoformat(t) for t in h_times]
        h_temps = h_data.get("temperature_2m") or []
        h_rains = h_data.get("precipitation_probability") or []
        h_codes = h_data.get("weather_code") or []
        h_winds = h_data.get("wind_speed_10m") or []
        h_press = h_data.get("surface_pressure") or []
        h_cloud = h_data.get("cloud_cover") or []

        for i in range(min(5, len(dates))):
            high = _at(highs, i)
            low = _at(lows, i)
            if high is None or low is None:
                continue
            d_obj = datetime.strptime(dates[i], "%Y-%m-%d")
            h_val, l_val = round(high), round(low)
            daily_max_prob = _at(precips, i)
            u_val = _at(uv_maxs, i)
            c_desc = WMO_CODE_MAP.get(_at(codes, i), None)
            sr_i = _at(sr_naive, i)
            ss_i = _at(ss_naive, i)
            sr_next = _at(sr_naive, i + 1)

            day_idx, night_idx = [], []
            if sr_i and ss_i:
                day_idx = [k for k, t in enumerate(h_naive) if sr_i <= t < ss_i]
                if sr_next:
                    night_idx = [k for k, t in enumerate(h_naive) if ss_i <= t < sr_next]

            def _max_prob(idx_list, fallback):
                vals = [h_rains[k] for k in idx_list if k < len(h_rains) and h_rains[k] is not None]
                return max(vals) if vals else fallback

            day_prob = _max_prob(day_idx, daily_max_prob)
            night_prob = _max_prob(night_idx, None)
            day_desc = _describe_window([_at(h_codes, k) for k in day_idx]) or c_desc
            night_desc = _describe_window([_at(h_codes, k) for k in night_idx])

            rain_txt = f" Rain chance {day_prob}%." if day_prob is not None else ""
            day_summary = (f"{day_desc} with a high near {h_val}°F.{rain_txt}" if day_desc
                           else f"High near {h_val}°F.{rain_txt}")
            night_rain_txt = f" Rain chance {night_prob}%." if night_prob is not None else ""
            if night_desc:
                night_summary = f"{night_desc} overnight, low near {l_val}°F.{night_rain_txt}"
            else:
                night_summary = f"Low near {l_val}°F.{night_rain_txt}"

            daily_dates.append(d_obj.date())
            daily_forecasts.append({
                "date": d_obj.strftime("%A, %b %d"),
                "high": h_val,
                "low": l_val,
                "rain_prob_max": daily_max_prob,
                "uv_max": u_val,
                "day_rain_prob": day_prob,
                "night_rain_prob": night_prob,
                "sunrise": _fmt_clock(sr_i) if sr_i else None,
                "sunset": _fmt_clock(ss_i) if ss_i else None,
                "moon_rise": "—",
                "moon_set": "—",
                "day_summary": day_summary,
                "night_summary": night_summary,
            })

        date_to_idx = {d: i for i, d in enumerate(dates)}
        now_local = datetime.now(resolved_tz)
        for idx, t_naive in enumerate(h_naive):
            dt_obj = t_naive.replace(tzinfo=resolved_tz)
            if dt_obj < now_local - timedelta(minutes=50):
                continue
            temp = _at(h_temps, idx)
            if temp is None:
                continue
            j = date_to_idx.get(t_naive.strftime("%Y-%m-%d"))
            sr_j, ss_j = _at(sr_naive, j) if j is not None else None, _at(ss_naive, j) if j is not None else None
            if sr_j and ss_j:
                is_night = t_naive < sr_j or t_naive >= ss_j
            else:
                is_night = (t_naive.hour < 7 or t_naive.hour >= 19)
            wind = _at(h_winds, idx)
            raw_hourly.append({
                "time": t_naive.strftime("%I %p").lstrip("0"),
                "hour": t_naive.strftime("%I %p").lstrip("0"),
                "temp": round(temp),
                "condition": WMO_CODE_MAP.get(_at(h_codes, idx), "Conditions unavailable"),
                "rain_chance": _at(h_rains, idx),
                "pressure": _at(h_press, idx),
                "is_night": is_night,
                "wind_mph": round(wind, 1) if wind is not None else None,
                "cloud_cover": _at(h_cloud, idx),
            })
            if len(raw_hourly) >= 36:
                break
    except Exception as exc:
        logger.warning("Open-Meteo forecast failed: %s", exc)

    # Nearest official observation (NWS) refines the "right now" numbers when it is fresh.
    if curr_obs is not None:
        try:
            pts = cached_get(f"https://api.weather.gov/points/{round(lat, 4)},{round(lon, 4)}", 21600, timeout=3.5, headers=headers)
            stn_url = (pts.get("properties") or {}).get("observationStations")
            if stn_url:
                stn_res = cached_get(stn_url, 21600, timeout=3.5, headers=headers)
                for feat in (stn_res.get("features") or [])[:2]:
                    stn_id = (feat.get("properties") or {}).get("stationIdentifier")
                    if not stn_id:
                        continue
                    obs = requests.get(f"https://api.weather.gov/stations/{stn_id}/observations/latest", headers=headers, timeout=3.5).json()
                    p = obs.get("properties") or {}
                    ts = p.get("timestamp")
                    try:
                        age_min = (datetime.now(timezone.utc) - datetime.fromisoformat(ts.replace("Z", "+00:00"))).total_seconds() / 60.0
                    except Exception:
                        age_min = 9999
                    temp_c = (p.get("temperature") or {}).get("value")
                    if temp_c is None or age_min > 90:
                        continue
                    t_f = round((temp_c * 9 / 5) + 32)
                    if curr_obs.get("feels_like") is not None:
                        shifted = curr_obs["feels_like"] + (t_f - curr_obs["temp"])
                        curr_obs["feels_like"] = shifted
                        curr_obs["heat_index"] = shifted
                    curr_obs["temp"] = t_f
                    text_desc = p.get("textDescription")
                    if text_desc:
                        curr_obs["condition"] = text_desc
                    wind_kmh = (p.get("windSpeed") or {}).get("value")
                    if wind_kmh is not None:
                        curr_obs["wind"] = round(wind_kmh * 0.621371, 1)
                    rh_raw = (p.get("relativeHumidity") or {}).get("value")
                    if rh_raw is not None:
                        curr_obs["humidity"] = round(rh_raw, 1)
                    break
        except Exception as exc:
            logger.info("NWS observation unavailable, using Open-Meteo values: %s", exc)

    # Moonrise / moonset for each forecast day (real calculation, not a fixed pair of times).
    if astro is not None:
        for d_date, entry in zip(daily_dates, daily_forecasts):
            try:
                entry["moon_rise"], entry["moon_set"] = astro.moon_times(lat, lon, d_date, resolved_tz)
            except Exception as exc:
                logger.info("Moon times failed: %s", exc)

    calibrated_hourly = []
    if raw_hourly and curr_obs is not None:
        offset = curr_obs["temp"] - raw_hourly[0]["temp"]
        for idx, item in enumerate(raw_hourly):
            decay = max(0.0, 1.0 - (idx / 12.0))
            calibrated = dict(item)
            calibrated["temp"] = round(item["temp"] + (offset * decay))
            calibrated_hourly.append(calibrated)

    return curr_obs, calibrated_hourly, daily_forecasts, sun_times, resolved_tz

def get_full_weather_data(query: str, sport_team: str = "Panthers, Braves, NC State"):
    lat, lon, elev_ft, location_name = get_coordinates(query)
    if lat is None or lon is None:
        raise HTTPException(status_code=404, detail="Location not recognized. Please check your city, state, or ZIP code.")

    # Independent lookups run side by side; one failing never takes the others down.
    f_weather = _POOL.submit(fetch_comprehensive_weather, lat, lon)
    f_aqi = _POOL.submit(fetch_live_aqi, lat, lon)
    f_alerts = _POOL.submit(fetch_noaa_alerts, lat, lon)
    f_station = _POOL.submit(nearest_tide_station, lat, lon)
    f_sports = _POOL.submit(fetch_live_sports_events, sport_team)
    f_enso = _POOL.submit(fetch_enso)

    live, hourly_36, daily_list, sun_times, local_tz = _result(
        f_weather, default=(None, [], [], {}, timezone.utc), label="weather")
    if live is None or not daily_list:
        raise HTTPException(status_code=503, detail="Weather data is temporarily unavailable. Please try again in a moment.")

    live_aqi = _result(f_aqi, default={"aqi": None, "value": None, "category": "Unavailable", "pm25": None, "status": "Unavailable"}, label="aqi")
    unavailable_alert = "NWS alerts are unavailable right now."
    extreme_alerts_str, tropical_alerts_str = _result(f_alerts, default=(unavailable_alert, unavailable_alert), label="alerts")
    station = _result(f_station, default=None, label="tide station")
    sports_events = _result(f_sports, default=[], label="sports")
    enso_text = _result(f_enso, default=None, label="enso")

    now = datetime.now(local_tz)
    is_coast = is_coastal_region(station)
    tide_text = fetch_noaa_tides(station) if station else None

    # Numbers used by the scoring formulas. If a single field is missing we fall back to a neutral
    # value for the math only; the "current" block below still reports the real (missing) value.
    curr_temp = live["temp"]
    curr_cond = live["condition"]
    curr_wind = _num(live.get("wind"), 0.0)
    curr_wind_dir = live.get("wind_direction")
    curr_hum = _num(live.get("humidity"), 50.0)
    curr_feels_like = live.get("feels_like")
    curr_heat_index = live.get("heat_index")
    curr_pressure = _num(live.get("pressure_hpa"), 1013.2)
    curr_uv = _num(live.get("uv_index"), 0.0)

    dew_point = dew_point_f(curr_temp, curr_hum)
    dew_txt = f"{dew_point}°F" if dew_point is not None else "unavailable"

    is_night_now = live.get("is_night")
    if is_night_now is None:
        sr_dt, ss_dt = sun_times.get("sunrise_dt"), sun_times.get("sunset_dt")
        naive_now = now.replace(tzinfo=None)
        if sr_dt and ss_dt:
            is_night_now = naive_now < sr_dt or naive_now >= ss_dt
        else:
            is_night_now = (now.hour < 7 or now.hour >= 19)

    micro_memo, boating_body, tides_desc, garden_season = generate_microclimate_profile(
        lat, lon, elev_ft, location_name, is_coast, tide_text, station, now.replace(tzinfo=None)
    )

    avg_temp_6h, avg_wind_6h, max_rain_6h, six_hour_summary = calculate_6hr_forecast_metrics(curr_temp, curr_wind, hourly_36)
    rain_penalty = max_rain_6h * 0.45

    sunrise = sun_times.get("sunrise") or "--"
    sunset = sun_times.get("sunset") or "--"

    # "Tonight's low" = coolest hour of the coming night; today's high from the daily forecast.
    night_temps = [h["temp"] for h in hourly_36[:24] if h.get("is_night") and h.get("temp") is not None]
    tonight_low = min(night_temps) if night_temps else daily_list[0]["low"]
    today_high = daily_list[0]["high"]
    afternoon_high = today_high
    if (now.hour >= 15 or is_night_now) and len(daily_list) > 1:
        afternoon_high = daily_list[1]["high"]
    next_day_rain = _num(daily_list[1].get("rain_prob_max"), 0) if len(daily_list) > 1 else 0

    encoded_label = urllib.parse.quote(location_name)
    radar_url = f"/radar?lat={round(lat, 4)}&lon={round(lon, 4)}&label={encoded_label}"
    radar_time_str = now.strftime("%I:%M %p").lstrip("0")

    beach_base = 100 - abs(avg_temp_6h - 82) * 2.0 - (avg_wind_6h * 1.5) - rain_penalty
    beach_score = max(20, min(99, round(beach_base if is_coast else beach_base - 10)))

    swim_base = avg_temp_6h * 1.1 - (avg_wind_6h * 1.8) - (rain_penalty * 0.8)
    swim_score = max(20, min(98, round(swim_base)))

    hike_base = 100 - abs(avg_temp_6h - 65) * 1.6 - (max(0, curr_hum - 65) * 0.4) - (avg_wind_6h * 0.4) - rain_penalty
    hike_score = max(30, min(99, round(hike_base)))

    surf_score = max(30, min(95, round(60 + (avg_wind_6h * 1.8) - (rain_penalty * 0.3)))) if is_coast else 40

    outdoor_activities = {
        "beach_and_sunbathing": {
            "score": beach_score,
            "details": f"{'🏖 Coastal Shore' if is_coast else '☀ Inland Recreation'}: Now {curr_temp}°F → 6-hour trend ~{avg_temp_6h}°F with {avg_wind_6h} mph winds.\n• {'Optimal beach window with light shore winds.' if avg_temp_6h >= 75 and avg_wind_6h < 14 and max_rain_6h < 20 else 'Brisk shore breezes; warm layers or windbreaker suggested.' if avg_wind_6h >= 14 else 'Cooler coastal temps; midday peak recommended.'}\n• {six_hour_summary}."
        },
        "swimming_and_water": {
            "score": swim_score,
            "details": f"🏊 Water Index: Current air {curr_temp}°F → 6-hour trend ~{avg_temp_6h}°F. Winds averaging {avg_wind_6h} mph.\n• {'Comfortable open water recreation.' if avg_temp_6h >= 76 and avg_wind_6h < 12 else 'Cool surface conditions; keep sessions brief.'}\n• {six_hour_summary}."
        },
        "hiking_and_trails": {
            "score": hike_score,
            "details": f"🥾 Trail Comfort: Current {curr_temp}°F with {curr_hum}% humidity.\n• {'Dry terrain and great visibility expected across the next 6 hours.' if max_rain_6h < 20 else 'Shower potential rising within 6h; pack a waterproof shell.'}\n• {six_hour_summary}."
        },
        "surfing_and_boardsports": {
            "score": surf_score,
            "details": f"🏄 Boardsports & Swell: {'Clean coastal breakers' if is_coast else 'Inland chop'} with {avg_wind_6h} mph sustained winds.\n• {six_hour_summary}."
        },
        "walking": {
            "score": max(35, min(99, round(100 - abs(avg_temp_6h - 70) * 1.5 - (max(0, curr_hum - 65) * 0.4) - (avg_wind_6h * 0.5) - rain_penalty))),
            "details": f"🚶 Walking Comfort: Currently {curr_temp}°F, winds {curr_wind} mph.\n• 6-hour average holds near {avg_temp_6h}°F with {avg_wind_6h} mph wind.\n• {'Excellent walking conditions.' if max_rain_6h < 15 else 'Spotty precipitation possible later in the window.'}"
        },
        "running": {
            "score": max(30, min(99, round(100 - abs(avg_temp_6h - 58) * 1.8 - (max(0, curr_hum - 60) * 0.5) - (avg_wind_6h * 0.6) - rain_penalty))),
            "details": f"🏃 Aerobic Cardio: Current {curr_temp}°F → 6-hour weighted ~{avg_temp_6h}°F.\n• {'Prime running window with low thermal strain.' if 48 <= avg_temp_6h <= 65 else 'Warm for sustained distance; pace yourself.' if avg_temp_6h > 65 else 'Chilly air; warm up thoroughly.'}\n• {six_hour_summary}."
        },
        "biking": {
            "score": max(30, min(99, round(100 - abs(avg_temp_6h - 68) * 1.3 - (avg_wind_6h * 1.4) - rain_penalty))),
            "details": f"🚴 Road & Trail Cycling: Current winds {curr_wind} mph → 6-hour average {avg_wind_6h} mph.\n• {'Road surfaces dry with minimal resistance.' if max_rain_6h < 20 else 'Pavement dampness risk developing within 6 hours.'}"
        },
        "boating": {
            "score": max(25, min(99, round(95 - (avg_wind_6h * 2.2) - (rain_penalty * 0.5)))),
            "details": f"⛵ Navigation ({boating_body}): Winds {curr_wind} mph (now) → 6-hour average {avg_wind_6h} mph.\n• {'Calm navigable water with chop under 1 ft.' if avg_wind_6h < 10 else 'Moderate surface chop; secure gear.' if avg_wind_6h < 18 else 'Caution: Steep surface wind chop.'}"
        },
        "fishing": {
            "score": max(45, min(96, round(88 - (avg_wind_6h * 0.8)))),
            "details": f"🎣 Angler Index: Ambient {curr_temp}°F with winds around {avg_wind_6h} mph.\n• {'Stable atmospheric pressure favors active feeding along structure.' if avg_wind_6h < 12 else 'Turbulent surface chop dispersing baitfish along windy edges.'}\n• {six_hour_summary}."
        },
        "camping": {
            "score": max(35, min(99, round(98 - abs(tonight_low - 55) * 1.2 - (avg_wind_6h * 0.8) - (rain_penalty * 0.6)))),
            "details": f"⛺ Overnight Camping: Low settling near {tonight_low}°F under {curr_cond.lower()} skies.\n• 6-hour wind average {avg_wind_6h} mph with rain ceiling at {max_rain_6h}%."
        },
        "mowing": {
            "score": 95 if curr_hum < 75 and curr_temp > 55 and max_rain_6h < 20 else (70 if max_rain_6h < 40 else 40),
            "details": f"🌱 Lawn Care: Ambient {curr_temp}°F, humidity {curr_hum}%.\n• {'Next 6 hours look clear for cutting.' if max_rain_6h < 20 else 'Mow early; rain chance increases later in 6-hour block.'}"
        },
        "hunting": {
            "score": 88 if avg_wind_6h < 10 and max_rain_6h < 25 else 65,
            "details": f"🏹 Game Movement: Winds averaging {avg_wind_6h} mph across 6-hour forecast window.\n• Steady scent dispersion; peak dawn/dusk feeding favored."
        }
    }

    # 1. Car Wash Index
    car_wash_score = max(20, min(99, round(98 - (max_rain_6h * 0.6) - (next_day_rain * 0.35) - (avg_wind_6h * 0.5))))
    car_wash_note = (
        "Optimal wash & wax window. Clear road conditions with zero rain interference expected for 48 hours."
        if car_wash_score >= 80 else
        "Acceptable for a quick rinse. Spotty precipitation possible over the next 24-48 hours."
        if car_wash_score >= 55 else
        "Hold off on washing. Elevated rain chance will cause dirty road splashback and spot residue."
    )

    # 2. Dog Walking & Paw Safety Index
    is_day = not is_night_now
    estimated_pavement_f = round(curr_temp + (25 if (is_day and curr_uv > 3.0) else 5))
    paw_burn_risk = estimated_pavement_f >= 120
    dog_walk_score = max(25, min(99, round(96 - (max(0, curr_temp - 82) * 1.5) - (rain_penalty * 0.8) - (15 if paw_burn_risk else 0))))
    dog_walk_details = (
        f"🐕 Canine Comfort: Air {curr_temp}°F | Est. Asphalt {estimated_pavement_f}°F.\n"
        f"• {'⚠️ Caution: Pavement surface exceeds 120°F. Walk pets on grass or turf to prevent paw burns.' if paw_burn_risk else 'Safe pavement temperatures for extended walks.'}\n"
        f"• {'Dry paths with minimal mud risk.' if max_rain_6h < 20 else 'Pack a towel for damp paws upon return.'}"
    )

    # 3. Outdoor Dining & Patio Index
    patio_base = 98 - abs(curr_temp - 74) * 1.6 - (avg_wind_6h * 1.4) - (max_rain_6h * 0.6)
    patio_score = max(30, min(99, round(patio_base)))
    patio_details = (
        f"🍷 Patio & Deck Comfort: Ambient {curr_temp}°F with {avg_wind_6h} mph breeze.\n"
        f"• {'Prime outdoor dining environment; pleasant atmospheric warmth with minimal breeze disturbance.' if patio_score >= 75 else 'Brisk or breezy patio dining; light layers or heat lamps recommended.' if curr_temp < 68 or avg_wind_6h > 12 else 'Midday heat elevated; shaded seating strongly recommended.'}\n"
        f"• Rain ceiling over next 6 hours: {max_rain_6h}%."
    )

    # 4. Mosquito & Biting Insect Index
    mosquito_risk_score = min(98, max(15, round((curr_hum * 0.6) + (max(0, curr_temp - 55) * 0.7) - (curr_wind * 1.8))))
    mosquito_details = (
        f"🦟 Insect Activity: Hazard Score {mosquito_risk_score}/100.\n"
        f"• {'High biting midge and mosquito flight pressure around shaded turf and marsh edges due to high humidity (' + str(curr_hum) + '%).' if mosquito_risk_score >= 70 else 'Moderate insect activity; light repellent recommended for dawn/dusk intervals.' if mosquito_risk_score >= 45 else 'Low insect activity; breezy conditions and cooler temperatures suppress flight.'}\n"
        f"• Mosquitoes are most active around dawn and dusk."
    )

    # 5. Sinus, Joint & Migraine Pressure Index
    future_pressure = _num(hourly_36[min(6, len(hourly_36) - 1)].get("pressure"), curr_pressure) if hourly_36 else curr_pressure
    press_swing = abs(curr_pressure - future_pressure)
    headache_score = max(30, min(96, round(92 - (press_swing * 4.5) - (abs(curr_hum - 50) * 0.25))))
    sinus_details = (
        f"🧠 Barometric & Biometric Impact: Current Barometer {curr_pressure} hPa.\n"
        f"• {'Stable atmospheric pressure gradient; low probability of weather-triggered migraines or arthritic joint flare-ups.' if press_swing < 3.0 else 'Active barometric fluctuation (' + str(round(press_swing, 1)) + ' hPa shift). Individuals sensitive to pressure changes may experience sinus congestion or headaches.'}\n"
        f"• Dew point holds near {dew_txt}."
    )

    # 6. UV Radiation & Sunscreen Burn Time
    burn_time_min = round(200 / max(1.0, curr_uv)) if curr_uv > 0 else 999
    burn_str = f"Roughly {burn_time_min} minutes for unprotected fair skin (rough estimate)" if curr_uv >= 3.0 else "Minimal burn danger without direct prolonged exposure"

    # 7. Natural Home Ventilation & HVAC Guidance
    hvac_score = 92 if (62 <= curr_temp <= 74 and curr_hum < 65 and max_rain_6h < 20) else (65 if (55 <= curr_temp <= 80) else 40)
    hvac_details = (
        f"🏡 Fresh Air Ventilation Index: Score {hvac_score}/100.\n"
        f"• {'Prime conditions to open windows and naturally ventilate home; outdoor air is crisp and comfortable with low dust.' if hvac_score >= 80 else 'Keep windows closed and cycle HVAC. Outdoor humidity (' + str(curr_hum) + '%) will introduce moisture into indoor living spaces.' if curr_hum > 75 else 'Moderate conditions. Screen ventilation acceptable during midday hours.'}"
    )

    foliage_text = foliage_status(lat, elev_ft, is_coast, now.replace(tzinfo=None))

    # Humidity-driven hair / makeup guidance (the label now follows the actual humidity).
    frizz_level = "High" if curr_hum > 75 else "Moderate" if curr_hum > 50 else "Low"
    aqi_val = live_aqi.get("value")
    aqi_line = (f"{live_aqi.get('category', 'Unavailable')} (AQI {aqi_val}"
                + (f" • PM2.5 {live_aqi.get('pm25')} µg/m³" if live_aqi.get("pm25") is not None else "") + ")"
                if aqi_val is not None else "Unavailable right now")

    lifestyle = {
        "clothing": {
            "morning": f"🌅 Morning ({tonight_low}°F): {clothing_advice(tonight_low)}",
            "afternoon": f"☀️ Afternoon ({afternoon_high}°F): {clothing_advice(afternoon_high)}",
            "night": f"🌙 Night ({tonight_low}°F): {clothing_advice(tonight_low)}",
        },
        "hair_makeup": {
            "hair_frizz_index": f"{frizz_level} ({curr_hum}% RH / Dew point {dew_txt}). {'Silicone anti-humidity serum, smoothing oil, or sleek updos recommended.' if curr_hum > 75 else 'Standard hold styling product should do the job.' if curr_hum > 50 else 'Low humidity; a hydrating leave-in conditioner helps.'}",
            "makeup_finish_index": f"Dew point {dew_txt}: {'High atmospheric moisture — oil-controlling matte primer and setting spray recommended.' if (curr_hum > 75 or (dew_point is not None and dew_point >= 65)) else 'Balanced moisture — hydrating base and standard foundation hold well.' if (dew_point is not None and dew_point >= 50) else 'Crisp, dry air — a hydrating moisturizer and luminous finish prevent flaking.'}"
        },
        "car_wash_index": {
            "score": car_wash_score,
            "details": f"🚗 Vehicle Care: Score {car_wash_score}/100.\n• {car_wash_note}\n• Next 6-hour rain risk: {max_rain_6h}% | Tomorrow: {next_day_rain}%."
        },
        "dog_walking": {
            "score": dog_walk_score,
            "details": dog_walk_details
        },
        "outdoor_dining": {
            "score": patio_score,
            "details": patio_details
        },
        "mosquito_and_insect": {
            "score": mosquito_risk_score,
            "details": mosquito_details
        },
        "allergens_and_pollen": {
            "pollen_counts": "Not available: no live pollen feed is connected for this location yet.",
            "mold_spore_risk": "Elevated near damp soil and unpaved corridors (estimated from humidity)" if curr_hum > 75 else "Low to moderate (estimated from humidity)",
            "air_quality": aqi_line
        },
        "sinus_and_migraine": {
            "score": headache_score,
            "details": sinus_details
        },
        "sun_and_uv_protection": {
            "max_uv_rating": f"Index {curr_uv:.1f} ({uv_label(curr_uv)})",
            "fair_skin_burn_time": burn_str,
            "recommended_protection": "Broad-spectrum SPF 30+ & UV400 sunglasses recommended during midday peak (11 AM - 3 PM)" if curr_uv >= 3 else "Minimal sunscreen required for short exposures"
        },
        "home_and_energy": {
            "score": hvac_score,
            "details": hvac_details
        },
        "leaf_change": foliage_text,
        "planting_harvest": garden_season
    }

    if max_rain_6h >= 40:
        boundary_desc = f"Unsettled boundary layer: active precipitation potential ({max_rain_6h}% peak over 6h)."
    elif curr_wind >= 14:
        boundary_desc = f"Breezy frontal mixing with surface gusts around {curr_wind} mph."
    else:
        boundary_desc = "Mild boundary layer with light surface flow."

    # Astronomy: everything below is calculated (astro.py), nothing is a fixed placeholder.
    night_clouds = [h["cloud_cover"] for h in hourly_36[:24] if h.get("is_night") and h.get("cloud_cover") is not None]
    cloud_avg = (sum(night_clouds) / len(night_clouds)) if night_clouds else None
    astronomy = {"sunrise": sunrise, "sunset": sunset}
    moon_rise, moon_set = daily_list[0].get("moon_rise", "—"), daily_list[0].get("moon_set", "—")
    if astro is not None:
        try:
            astronomy.update(astro.astronomy_summary(lat, lon, now.astimezone(timezone.utc), local_tz, cloud_cover_night=cloud_avg))
        except Exception as exc:
            logger.warning("Astronomy summary failed: %s", exc)
            astronomy["status"] = "Astronomy details are temporarily unavailable."
    else:
        astronomy["status"] = "Astronomy details are unavailable (astro.py is missing from this deployment)."

    precip_now = hourly_36[0].get("rain_chance") if hourly_36 else None
    daily_max = daily_list[0].get("rain_prob_max")
    precip_summary = (f"Precip Now: {precip_now if precip_now is not None else '--'}% | "
                      f"6h Peak: {max_rain_6h}% | Daily Max: {daily_max if daily_max is not None else '--'}%")

    weather_climate = {
        "microclimate_memo": micro_memo,
        "watershed_overview": f"Target Waterway: {boating_body}",
        "tides_and_hydrology": tides_desc,
        "enso_index": enso_text or "ENSO status is unavailable right now.",
        "tropical_updates": tropical_alerts_str,
        "extreme_weather_24h": extreme_alerts_str,
    }

    return {
        "lat": lat, "lon": lon, "elevation_ft": elev_ft, "location_name": location_name,
        "radar_url": radar_url,
        "radar_time": radar_time_str,
        "current": {
            "temp": curr_temp,
            "heat_index": curr_heat_index,
            "feels_like": curr_feels_like,
            "humidity": live.get("humidity"),
            "wind": live.get("wind"),
            "condition": curr_cond,
            "is_night": bool(is_night_now),
            "uv_index": live.get("uv_index"),
            "sunrise": sunrise,
            "sunset": sunset,
            "moon_rise": moon_rise,
            "moon_set": moon_set,
            "precip_summary": precip_summary,
            "rain_duration": boundary_desc,
            "aqi": live_aqi.get("value"),
            "air_quality": live_aqi.get("category"),
            "aqi_category": live_aqi.get("category")
        },
        "hourly_36": hourly_36,
        "daily": daily_list,
        "aqi": live_aqi,
        "weather_climate": weather_climate,
        "outdoor_activities": outdoor_activities,
        "lifestyle": lifestyle,
        "sporting_event": {"events": sports_events},
        "astronomy": astronomy,
    }

@asynccontextmanager
async def lifespan(app: FastAPI):
    await flet_fastapi.app_manager.start()
    yield
    await flet_fastapi.app_manager.shutdown()

app = FastAPI(title="Thick Moose Weather API", lifespan=lifespan)

assets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "assets"))

@app.get("/manifest.json")
def get_manifest():
    manifest_path = os.path.join(assets_dir, "manifest.json")
    if os.path.exists(manifest_path):
        return FileResponse(manifest_path, media_type="application/manifest+json")
    raise HTTPException(status_code=404, detail="Manifest not found")

@app.get("/radar", response_class=HTMLResponse)
def get_radar_page(
    lat: float = Query(34.1378, ge=-90.0, le=90.0),
    lon: float = Query(-77.9150, ge=-180.0, le=180.0),
    label: str = Query("Location", max_length=120),
):
    safe_label = html.escape(label, quote=True)                      # for HTML text
    js_label = json.dumps(label).replace("<", "\\u003c")            # for the JavaScript string
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Thick Moose Radar • {safe_label}</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        * {{ box-sizing: border-box; }}
        body, html {{ margin: 0; padding: 0; height: 100%; width: 100%; background: #1a1a1a; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; overflow: hidden; }}
        #map {{ height: 100%; width: 100%; background: #1a1a1a; }}

        .leaflet-layer {{
            transition: opacity 0.35s ease-in-out !important;
            will-change: opacity;
        }}

        .top-hud {{
            position: absolute; top: 12px; left: 12px; right: 12px;
            display: flex; justify-content: space-between; align-items: center;
            z-index: 1000; pointer-events: none;
        }}
        .hud-card {{
            background: rgba(26, 26, 26, 0.92); backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
            border: 1px solid rgba(255, 193, 7, 0.4); border-radius: 12px;
            padding: 6px 12px; color: white; display: flex; align-items: center; gap: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5); pointer-events: auto;
        }}
        .back-link {{
            color: #ffc107; text-decoration: none; font-size: 13px; font-weight: bold;
            display: flex; align-items: center; gap: 4px;
        }}
        .hud-title {{ font-size: 12px; font-weight: 700; color: #fff; max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}

        .legend-bar {{
            display: flex; align-items: center; gap: 4px; font-size: 10px; font-weight: 600; color: #aaa;
        }}
        .legend-gradient {{
            width: 70px; height: 7px; border-radius: 4px;
            background: linear-gradient(to right, #00e5ff, #00e676, #ffeb3b, #ff5722, #d500f9);
        }}

        .controls {{
            position: absolute; bottom: 18px; left: 50%; transform: translateX(-50%);
            background: rgba(26, 26, 26, 0.94); backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
            border: 1.5px solid rgba(255, 193, 7, 0.6); border-radius: 18px;
            padding: 7px 12px; display: flex; align-items: center; gap: 8px; z-index: 1000;
            color: white; box-shadow: 0 8px 30px rgba(0,0,0,0.7);
            width: calc(100% - 24px); max-width: 480px;
        }}
        .btn-ctrl {{
            background: #ffc107; color: #000; border: none; border-radius: 8px;
            width: 32px; height: 32px; font-size: 13px; font-weight: bold;
            display: flex; align-items: center; justify-content: center; cursor: pointer;
            flex-shrink: 0;
        }}
        .btn-ctrl:hover {{ background: #ffe082; }}
        .badge {{
            padding: 4px 7px; border-radius: 6px; font-size: 11px; font-weight: 800; letter-spacing: 0.5px;
            white-space: nowrap; text-align: center; flex-shrink: 0; min-width: 50px;
        }}
        .badge-past {{ background: rgba(0, 229, 255, 0.2); color: #00e5ff; border: 1px solid #00e5ff; }}
        .badge-live {{ background: rgba(76, 175, 80, 0.25); color: #4caf50; border: 1px solid #4caf50; }}
        .badge-future {{ background: rgba(255, 193, 7, 0.25); color: #ffc107; border: 1px solid #ffc107; }}
        .time-display {{ font-size: 12px; font-weight: 700; min-width: 58px; text-align: center; color: #fff; flex-shrink: 0; }}
        .timeline {{
            flex: 1; min-width: 60px; cursor: pointer; accent-color: #ffc107; height: 6px;
        }}

        @keyframes radar-pulse {{
            0% {{ transform: scale(0.9); box-shadow: 0 0 0 0 rgba(255, 193, 7, 0.8); }}
            70% {{ transform: scale(1.1); box-shadow: 0 0 0 16px rgba(255, 193, 7, 0); }}
            100% {{ transform: scale(0.9); box-shadow: 0 0 0 0 rgba(255, 193, 7, 0); }}
        }}
        .pulse-pin {{
            background: #ffc107; color: black; border: 2.5px solid #000; border-radius: 50%;
            width: 30px; height: 30px; display: flex; align-items: center; justify-content: center;
            font-size: 15px; animation: radar-pulse 2s infinite; cursor: pointer;
        }}
    </style>
</head>
<body>
    <div class="top-hud">
        <div class="hud-card">
            <a href="/" class="back-link">← Dashboard</a>
            <span style="color:#555">|</span>
            <span class="hud-title">📍 {safe_label}</span>
        </div>
        <div class="hud-card">
            <div class="legend-bar">
                <span>Rain</span>
                <div class="legend-gradient"></div>
                <span style="color:#ff5722">Storm</span>
            </div>
        </div>
    </div>

    <div id="map"></div>

    <div class="controls">
        <button class="btn-ctrl" id="playBtn" onclick="togglePlay()">⏸</button>
        <div id="statusBadge" class="badge badge-live">LIVE</div>
        <div id="timeDisplay" class="time-display">--:--</div>
        <input type="range" id="slider" class="timeline" min="0" max="0" value="0" oninput="onSlider(this.value)">
    </div>

    <script>
        const lat = {lat};
        const lon = {lon};
        const labelText = {js_label};

        const map = L.map('map', {{ zoomControl: false, minZoom: 4, maxZoom: 18 }}).setView([lat, lon], 8);
        L.control.zoom({{ position: 'topright' }}).addTo(map);

        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
            attribution: '&copy; Esri &mdash; Esri, DeLorme, NAVTEQ | Doppler: RainViewer',
            maxNativeZoom: 16,
            maxZoom: 19
        }}).addTo(map);

        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
            maxNativeZoom: 16,
            maxZoom: 19,
            zIndex: 150
        }}).addTo(map);

        const pinIcon = L.divIcon({{
            className: 'custom-pin-container',
            html: '<div class="pulse-pin">📍</div>',
            iconSize: [30, 30],
            iconAnchor: [15, 15]
        }});
        L.marker([lat, lon], {{ icon: pinIcon, zIndexOffset: 1000 }}).addTo(map).bindPopup((() => {{ const el = document.createElement('b'); el.textContent = '📍 ' + labelText; return el; }})()).openPopup();

        let allFrames = [];
        let radarLayers = [];
        let hostUrl = "https://tilecache.rainviewer.com";
        let liveIndex = 0;
        let currentIndex = 0;
        let isPlaying = true;
        let timer = null;

        // Continuous atmospheric advection vector (East-Northeast at base zoom 8)
        const baseShiftX = 9;  // +9px East per 10-minute step
        const baseShiftY = -3; // -3px North per 10-minute step
        const totalFutureSteps = 6; // 60 minutes forecast window (+10m through +60m)

        fetch('https://api.rainviewer.com/public/weather-maps.json')
            .then(res => res.json())
            .then(data => {{
                hostUrl = data.host || "https://tilecache.rainviewer.com";
                const past = (data.radar && data.radar.past) ? data.radar.past : [];
                const rawNowcast = (data.radar && data.radar.nowcast) ? data.radar.nowcast : [];

                if (past.length === 0) return;

                const lastPast = past[past.length - 1];
                const liveTime = lastPast.time;

                past.forEach((p, idx) => {{
                    allFrames.push({{
                        time: p.time,
                        path: p.path,
                        type: (idx === past.length - 1) ? 'live' : 'past',
                        minuteOffset: 0,
                        shiftX: 0,
                        shiftY: 0,
                        opacity: 0.85
                    }});
                }});

                liveIndex = past.length - 1;

                // Build guaranteed 60-minute prediction loop without jumps
                for (let step = 1; step <= totalFutureSteps; step++) {{
                    const futureTime = liveTime + (step * 600);
                    const minuteOffset = step * 10;
                    
                    let path = lastPast.path;
                    let sx = 0;
                    let sy = 0;

                    if (rawNowcast.length >= step) {{
                        path = rawNowcast[step - 1].path;
                        sx = 0;
                        sy = 0;
                    }} else {{
                        const extraSteps = step - rawNowcast.length;
                        path = rawNowcast.length > 0 ? rawNowcast[rawNowcast.length - 1].path : lastPast.path;
                        sx = extraSteps * baseShiftX;
                        sy = extraSteps * baseShiftY;
                    }}

                    allFrames.push({{
                        time: futureTime,
                        path: path,
                        type: 'predicted',
                        minuteOffset: minuteOffset,
                        shiftX: sx,
                        shiftY: sy,
                        opacity: Math.max(0.60, 0.85 - (step * 0.03))
                    }});
                }}

                document.getElementById('slider').max = allFrames.length - 1;

                allFrames.forEach((f) => {{
                    const layer = L.tileLayer(hostUrl + f.path + '/256/{{z}}/{{x}}/{{y}}/2/1_1.png', {{
                        tileSize: 256,
                        opacity: 0,
                        maxNativeZoom: 7,
                        maxZoom: 19,
                        zIndex: 100
                    }});
                    layer.addTo(map);
                    radarLayers.push(layer);
                }});

                showFrame(liveIndex);
                play();
            }})
            .catch(() => {{
                document.getElementById('timeDisplay').innerText = "Live";
            }});

        function showFrame(idx) {{
            if (radarLayers.length === 0) return;
            currentIndex = idx;

            const f = allFrames[idx];
            const currentZoom = map.getZoom();
            const zoomScale = Math.pow(2, currentZoom - 8);

            radarLayers.forEach((l, i) => {{
                const frameData = allFrames[i];
                const container = l.getContainer();
                if (i === idx) {{
                    l.setOpacity(frameData.opacity);
                    if (container) {{
                        const finalX = Math.round(frameData.shiftX * zoomScale);
                        const finalY = Math.round(frameData.shiftY * zoomScale);
                        container.style.translate = `${{finalX}}px ${{finalY}}px`;
                    }}
                }} else {{
                    l.setOpacity(0);
                }}
            }});

            document.getElementById('slider').value = idx;

            const d = new Date(f.time * 1000);
            document.getElementById('timeDisplay').innerText = d.toLocaleTimeString([], {{ hour: 'numeric', minute: '2-digit' }});

            const badge = document.getElementById('statusBadge');
            if (f.type === 'past') {{
                badge.className = 'badge badge-past';
                badge.innerText = 'PAST';
            }} else if (f.type === 'live') {{
                badge.className = 'badge badge-live';
                badge.innerText = 'LIVE';
            }} else {{
                badge.className = 'badge badge-future';
                badge.innerText = `+${{f.minuteOffset}}m`;
            }}
        }}

        map.on('zoomend', () => {{
            showFrame(currentIndex);
        }});

        function play() {{
            if (timer) clearInterval(timer);
            timer = setInterval(() => {{
                let next = currentIndex + 1;
                if (next >= allFrames.length) next = 0;
                showFrame(next);
            }}, 550);
            isPlaying = true;
            document.getElementById('playBtn').innerText = '⏸';
        }}

        function pause() {{
            if (timer) clearInterval(timer);
            isPlaying = false;
            document.getElementById('playBtn').innerText = '▶';
        }}

        function togglePlay() {{
            if (isPlaying) pause(); else play();
        }}

        function onSlider(val) {{
            pause();
            showFrame(parseInt(val));
        }}
    </script>
</body>
</html>"""

@app.get("/weather")
def api_weather(query: str = "", sport_team: str = "Panthers, Braves, NC State"):
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query parameter is required")
    try:
        return get_full_weather_data(query, sport_team)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error building weather data")
        raise HTTPException(status_code=500, detail="Something went wrong loading the weather. Please try again.")
@app.get("/.well-known/assetlinks.json", response_class=FileResponse)
async def serve_assetlinks():
    assetlinks_path = Path(__file__).resolve().parent / "assets" / "assetlinks.json"
    if assetlinks_path.exists():
        return FileResponse(path=str(assetlinks_path), media_type="application/json")
    return JSONResponse(status_code=404, content={"error": "assetlinks.json not found"})

assets_path = Path(__file__).resolve().parent / "assets"
app.mount("/", flet_fastapi.app(main.main, assets_dir=str(assets_path)))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, proxy_headers=True, forwarded_allow_ips="*")
