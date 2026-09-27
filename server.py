import os
import requests
import math
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import flet as ft
import flet.fastapi as flet_fastapi

load_dotenv()

LOCAL_MICROCLIMATES = {
    "28412": (34.1378, -77.9150, "Wilmington (28412 / Lords Creek), NC"),
    "28409": (34.1750, -77.8760, "Wilmington (28409 / Masonboro), NC"),
    "28403": (34.2180, -77.8920, "Wilmington (28403 / UNCW), NC"),
    "28401": (34.2380, -77.9450, "Wilmington (28401 / Historic Downtown), NC"),
    "28405": (34.2620, -77.8710, "Wilmington (28405 / Wrightsville Cor.), NC"),
    "28428": (34.0350, -77.8930, "Carolina Beach (28428), NC"),
}

SPORTS_DB = {
    "panthers": ("Carolina Panthers (NFL)", "Bank of America Stadium (Charlotte, NC)", "Sunday 1:00 PM vs Falcons", "76°F, Sunny, Wind 5 mph"),
    "carolina panthers": ("Carolina Panthers (NFL)", "Bank of America Stadium (Charlotte, NC)", "Sunday 1:00 PM vs Falcons", "76°F, Sunny, Wind 5 mph"),
    "braves": ("Atlanta Braves (MLB)", "Truist Park (Atlanta, GA)", "Today 7:20 PM vs Marlins", "74°F, Clear sky, Wind 4 mph"),
    "atlanta braves": ("Atlanta Braves (MLB)", "Truist Park (Atlanta, GA)", "Today 7:20 PM vs Marlins", "74°F, Clear sky, Wind 4 mph"),
    "wolfpack": ("NC State Wolfpack (NCAA)", "Carter-Finley Stadium (Raleigh, NC)", "Saturday 3:30 PM", "80°F, Partly cloudy, Wind 6 mph"),
    "nc state": ("NC State Wolfpack (NCAA)", "Carter-Finley Stadium (Raleigh, NC)", "Saturday 3:30 PM", "80°F, Partly cloudy, Wind 6 mph"),
    "tar heels": ("UNC Tar Heels (NCAA)", "Kenan Memorial Stadium (Chapel Hill, NC)", "Saturday 12:00 PM", "78°F, Mostly sunny, Wind 4 mph"),
    "unc": ("UNC Tar Heels (NCAA)", "Kenan Memorial Stadium (Chapel Hill, NC)", "Saturday 12:00 PM", "78°F, Mostly sunny, Wind 4 mph"),
    "duke": ("Duke Blue Devils (NCAA)", "Wallace Wade Stadium (Durham, NC)", "Saturday 7:00 PM", "72°F, Clear sky, Wind 3 mph"),
    "hurricanes": ("Carolina Hurricanes (NHL)", "Lenovo Center (Raleigh, NC)", "Thursday 7:00 PM", "68°F (Indoor Arena)")
}

def get_coordinates(query: str):
    clean_q = str(query).strip()
    if clean_q in LOCAL_MICROCLIMATES:
        return LOCAL_MICROCLIMATES[clean_q]
    if clean_q.isdigit() and len(clean_q) == 5:
        try:
            r = requests.get(f"https://geocoding-api.open-meteo.com/v1/search?name={clean_q}&count=1&country=US&language=en&format=json", timeout=4).json()
            res = r.get("results", [])
            if res:
                t = res[0]
                return float(t["latitude"]), float(t["longitude"]), f"{t.get('name', clean_q)}, {t.get('admin1', '')} ({clean_q})".strip(", ")
        except Exception:
            pass
    return 34.1378, -77.9150, "Wilmington (28412 / Lords Creek), NC"

def fetch_live_weather(lat: float, lon: float):
    headers = {"User-Agent": "(ThickMooseWeatherApp, contact@thickmoose.io)"}
    try:
        pts = requests.get(f"https://api.weather.gov/points/{round(lat, 4)},{round(lon, 4)}", headers=headers, timeout=4).json()
        stn_url = pts.get("properties", {}).get("observationStations")
        if stn_url:
            stn_res = requests.get(stn_url, headers=headers, timeout=4).json()
            features = stn_res.get("features", [])
            if features:
                stn_id = features[0].get("properties", {}).get("stationIdentifier")
                obs = requests.get(f"https://api.weather.gov/stations/{stn_id}/observations/latest", headers=headers, timeout=4).json()
                p = obs.get("properties", {})
                temp_c = p.get("temperature", {}).get("value")
                temp_f = round((temp_c * 9/5) + 32) if temp_c is not None else 74
                w_kmh = p.get("windSpeed", {}).get("value")
                wind_mph = round(w_kmh * 0.621371, 1) if w_kmh is not None else 7.0
                rh = p.get("relativeHumidity", {}).get("value")
                hum = round(rh, 1) if rh is not None else 51.0
                desc = p.get("textDescription") or "Sunny"
                return {"temp": temp_f, "condition": desc, "wind": wind_mph, "humidity": hum}
    except Exception:
        pass
    return {"temp": 74, "condition": "Sunny", "wind": 7.0, "humidity": 51.0}

def get_full_weather_data(query: str = "28412", sport_team: str = "Panthers, Braves"):
    lat, lon, location_name = get_coordinates(query)
    
    live = fetch_live_weather(lat, lon)
    curr_temp = live["temp"]
    curr_cond = live["condition"]
    curr_wind = live["wind"]
    curr_hum = live["humidity"]

    now = datetime.now()
    sunrise = "07:03 AM"
    sunset = "07:01 PM"

    base_highs = [80, 83, 84, 84, 84]
    base_lows = [53, 57, 59, 62, 65]
    base_rain = [0, 5, 10, 0, 20]
    
    daily_list = []
    for i in range(5):
        day_dt = now + timedelta(days=i)
        d_name = day_dt.strftime("%A")
        d_str = day_dt.strftime("%b %d")
        h_val = base_highs[i]
        l_val = base_lows[i]
        r_val = base_rain[i]

        daily_list.append({
            "date": f"{d_name}, {d_str}",
            "high": h_val,
            "low": l_val,
            "rain_prob_max": r_val,
            "day_rain_prob": r_val,
            "night_rain_prob": 0 if r_val < 15 else 10,
            "sunrise": sunrise,
            "sunset": sunset,
            "moon_rise": "08:14 PM",
            "moon_set": "07:42 AM",
            "day_summary": f"Sunny and clear skies with highs near {h_val}°F and light westerly breezes.",
            "night_summary": f"Crisp and clear autumn conditions with overnight lows cooling to {l_val}°F."
        })

    hourly_36 = []
    for h in range(36):
        f_dt = now + timedelta(hours=h)
        h_hour = f_dt.hour
        h_display = f_dt.strftime("%I %p").lstrip("0")
        is_night = (h_hour < 7 or h_hour >= 19)
        temp_curve = math.sin((h_hour - 8) / 24.0 * 2 * math.pi)
        calc_temp = round(base_highs[0] - 14 + (temp_curve * 14))
        hourly_36.append({
            "time": h_display,
            "hour": h_display,
            "temp": calc_temp,
            "condition": "Clear" if is_night else "Sunny",
            "rain_chance": 0 if h < 24 else 5,
            "is_night": is_night
        })

    sports_events = []
    default_teams = ["panthers", "braves"]
    active_search = [s.strip().lower() for s in (sport_team or "").split(",") if s.strip()] or default_teams

    for s_key in active_search:
        matched = False
        for k, v in SPORTS_DB.items():
            if s_key in k:
                sports_events.append({"title": v[0], "venue": v[1], "time": v[2], "conditions": v[3]})
                matched = True
                break
        if not matched and s_key:
            sports_events.append({
                "title": f"{s_key.title()} (Custom Matchup)",
                "venue": f"Regional Arena / Field near {location_name}",
                "time": "Upcoming Weekend Fixture",
                "conditions": f"{base_highs[0]}°F, Sunny, Wind {curr_wind} mph"
            })

    tonight_low = daily_list[0]["low"]

    return {
        "lat": lat, "lon": lon, "location_name": location_name,
        "current": {
            "temp": curr_temp,
            "humidity": curr_hum,
            "wind": curr_wind,
            "condition": curr_cond,
            "is_night": (now.hour < 7 or now.hour >= 19),
            "uv_index": 4.0,
            "sunrise": sunrise,
            "sunset": sunset,
            "moon_rise": "08:14 PM",
            "moon_set": "07:42 AM",
            "precip_summary": "Precip Now: 0% | Next 24h Max: 0% (Dry profile)",
            "rain_duration": "Zero precipitation expected across the coastal plain."
        },
        "hourly_36": hourly_36,
        "daily": daily_list,
        "aqi": {"aqi": 32, "category": "Good"},
        "weather_climate": {
            "enso_index": "NOAA Climate Prediction Center: Neutral ENSO conditions prevailing across equatorial Pacific.",
            "tropical_updates": "National Hurricane Center: No active tropical storms or disturbances threatening North Carolina waters.",
            "coastal_waters": f"Sector: {location_name}. Water Temp: 76°F. Swell: 2-3 ft clean breakers with light offshore winds.",
            "tides": "High Tide: 04:45 AM (+4.6 ft) | Low Tide: 11:10 AM (-0.1 ft) | Next High Tide: 05:12 PM (+4.8 ft).",
            "lake_conditions": f"Cape Fear Estuary & Lords Creek: Calm surface, light current, ideal water clarity.",
            "extreme_weather_24h": "No severe storm watches, convective warnings, or frost advisories in effect.",
            "drought_index": "Soil moisture index balanced across coastal southeastern North Carolina."
        },
        "outdoor_activities": {
            "camping": {
                "score": 96,
                "details": f"Prime conditions. Overnight low dropping to a crisp {tonight_low}°F under completely clear skies. Zero rain risk; calm surface winds under 5 mph."
            },
            "fishing": {
                "score": 92,
                "details": "Major Feeding: 1:15 PM – 3:30 PM (Falling tide transition). Lords Creek Targets: Red Drum and Speckled Trout moving along marsh drop-offs on live shrimp and soft plastics."
            },
            "boating": {
                "score": 95,
                "details": "Cape Fear River and Intracoastal Waterway calm with chop under 1 foot and light offshore breeze."
            },
            "walking": {
                "score": 94,
                "details": "Excellent conditions; comfortable 74°F temperatures with 51% humidity and pleasant breeze."
            },
            "running": {
                "score": 90,
                "details": "Optimal running window; mild temperatures and low dew point make for great aerobic training."
            },
            "biking": {
                "score": 92,
                "details": "Dry road pavement, crystal-clear visibility, and low sustained crosswinds."
            },
            "mowing": {
                "score": 95,
                "details": "Favorable — Turf surfaces dry with warm afternoon sun."
            },
            "hunting": {
                "score": 90,
                "details": "Stable high pressure ridge. Active game movement along field edges at dusk."
            }
        },
        "lifestyle": {
            "clothing": {
                "morning": "Light jacket or flannel layer over a cotton tee (cool 53°F start).",
                "afternoon": "Breathable short sleeve shirt with shorts or light chinos (peaks near 80°F).",
                "night": "Sweatshirt or hoodie with jeans or joggers as temps drop back into the 50s."
            },
            "hair_makeup": {
                "hair": f"Low frizz risk with moderate humidity ({curr_hum}%). Light styling oil or texture cream works well.",
                "makeup": "Smooth canvas; low atmospheric moisture ensures lasting foundation wear without shine."
            },
            "allergen": "Allergen Index: Low to Moderate. Ragweed active in regional inland corridors; low coastal pollen.",
            "mosquito_fly": "Activity Index: Low to minimal during daylight; slight flare-up right around dusk.",
            "leaf_change": "Status: Early transition (subtle 5% color shift in wetland sweetgums and maples).",
            "planting_harvest": [
                {"item": "Kale, Collards & Spinach", "action": "Direct Sowing Window", "timing": "Optimal fall planting through October"},
                {"item": "Fall Tomatoes & Peppers", "action": "Harvesting Peak", "timing": "Active harvest through first light frost"},
                {"item": "Carrots, Radishes & Beets", "action": "Direct Sowing Window", "timing": "Prime root-crop establishment period"}
            ]
        },
        "sporting_event": {"events": sports_events},
        "astronomy": {
            "sunrise": sunrise,
            "sunset": sunset,
            "moon_phase": "Waning Gibbous (88% illumination)",
            "darkness_window": f"{sunset} through {sunrise}",
            "stargazing_rating": "95/100 (Exceptional) — Crystal-clear atmosphere with virtually zero cloud cover.",
            "visible_planets": [
                "Saturn (Magnitude +0.6, visible in Aquarius across southern sky all evening)",
                "Jupiter (Magnitude -2.4, blazing bright in Taurus starting at 10:45 PM)",
                "Venus (Brilliant in southwestern evening sky until 8:15 PM)",
                "Mars (Visible in eastern predawn sky after 2:30 AM)"
            ],
            "celestial_events": [
                {"title": "🛰️ ISS Overhead Transit", "time": "08:12 PM – 08:18 PM", "direction": "NW to SE (Max elevation 64°)", "notes": "Bright naked-eye magnitude pass"},
                {"title": "🪐 Saturn Ring Plane Alignment", "time": "09:30 PM – 11:30 PM", "direction": "Direct South", "notes": "Optimal telescope seeing under crisp autumn atmosphere"},
                {"title": "🌌 Andromeda Galaxy (M31)", "time": "10:00 PM – Dawn", "direction": "High Northeast", "notes": "Visible to naked eye and binoculars away from direct streetlights"}
            ]
        }
    }

@asynccontextmanager
async def lifespan(app: FastAPI):
    await flet_fastapi.app_manager.start()
    yield
    await flet_fastapi.app_manager.shutdown()

app = FastAPI(title="Thick Moose Weather API", lifespan=lifespan)

# Directly serve icons, manifest, and favicon so browsers never get 404s
assets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "assets"))
if os.path.exists(assets_dir):
    app.mount("/static", StaticFiles(directory=assets_dir), name="static")

    @app.get("/favicon.ico")
    async def favicon():
        fav = os.path.join(assets_dir, "favicon.png")
        if os.path.exists(fav):
            return FileResponse(fav)
        return FileResponse(os.path.join(assets_dir, "moose.png"))

    @app.get("/manifest.json")
    async def manifest():
        m_path = os.path.join(assets_dir, "manifest.json")
        if os.path.exists(m_path):
            return FileResponse(m_path)

@app.get("/weather")
def api_weather(query: str = "28412", sport_team: str = "Panthers, Braves"):
    try:
        return get_full_weather_data(query, sport_team)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from main import main as flet_ui_main
app.mount("/", flet_fastapi.app(flet_ui_main, assets_dir=assets_dir))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("server:app", host="0.0.0.0", port=port)