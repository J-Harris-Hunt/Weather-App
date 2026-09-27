import os
import requests
import math
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
import flet as ft
import flet.fastapi as flet_fastapi

load_dotenv()

WMO_MAP = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 51: "Light drizzle", 61: "Slight rain", 63: "Moderate rain",
    65: "Heavy rain", 71: "Slight snow", 75: "Heavy snow", 95: "Thunderstorm"
}

SPORTS_DB = {
    "panthers": ("Carolina Panthers (NFL)", "Bank of America Stadium (Charlotte, NC)", "Sun 1:00 PM", "76°F, Sunny"),
    "carolina panthers": ("Carolina Panthers (NFL)", "Bank of America Stadium (Charlotte, NC)", "Sun 1:00 PM", "76°F, Sunny"),
    "braves": ("Atlanta Braves (MLB)", "Truist Park (Atlanta, GA)", "Today 7:20 PM", "74°F, Clear sky"),
    "atlanta braves": ("Atlanta Braves (MLB)", "Truist Park (Atlanta, GA)", "Today 7:20 PM", "74°F, Clear sky"),
    "wolfpack": ("NC State Wolfpack (NCAA)", "Carter-Finley Stadium (Raleigh, NC)", "Saturday 3:30 PM", "80°F, Partly cloudy"),
    "nc state": ("NC State Wolfpack (NCAA)", "Carter-Finley Stadium (Raleigh, NC)", "Saturday 3:30 PM", "80°F, Partly cloudy"),
    "tar heels": ("UNC Tar Heels (NCAA)", "Kenan Memorial Stadium (Chapel Hill, NC)", "Saturday 12:00 PM", "78°F, Mostly sunny"),
    "unc": ("UNC Tar Heels (NCAA)", "Kenan Memorial Stadium (Chapel Hill, NC)", "Saturday 12:00 PM", "78°F, Mostly sunny"),
    "duke": ("Duke Blue Devils (NCAA)", "Wallace Wade Stadium (Durham, NC)", "Saturday 7:00 PM", "75°F, Clear sky"),
    "hurricanes": ("Carolina Hurricanes (NHL)", "Lenovo Center (Raleigh, NC)", "Matchup 7:00 PM", "68°F (Indoor Arena)")
}

LOCAL_MICROCLIMATES = {
    "28412": (34.1378, -77.9150, "Wilmington (28412 / Lords Creek), NC"),
    "28409": (34.1750, -77.8760, "Wilmington (28409 / Masonboro), NC"),
    "28403": (34.2180, -77.8920, "Wilmington (28403 / UNCW), NC"),
    "28401": (34.2380, -77.9450, "Wilmington (28401 / Historic Downtown), NC"),
    "28405": (34.2620, -77.8710, "Wilmington (28405 / Wrightsville Cor.), NC"),
    "28428": (34.0350, -77.8930, "Carolina Beach (28428), NC"),
}

def get_coordinates(query: str):
    clean_q = str(query).strip()
    if clean_q in LOCAL_MICROCLIMATES:
        return LOCAL_MICROCLIMATES[clean_q]

    if clean_q.isdigit() and len(clean_q) == 5:
        try:
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={clean_q}&count=1&country=US&language=en&format=json"
            geo_res = requests.get(geo_url, timeout=5).json()
            results = geo_res.get("results", [])
            if results:
                top = results[0]
                return float(top["latitude"]), float(top["longitude"]), f"{top.get('name', clean_q)}, {top.get('admin1', '')} ({clean_q})".strip(", ")
        except Exception:
            pass

    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={clean_q}&count=1&language=en&format=json"
        geo_res = requests.get(geo_url, timeout=5).json()
        results = geo_res.get("results", [])
        if results:
            top = results[0]
            return float(top["latitude"]), float(top["longitude"]), f"{top.get('name', clean_q)}, {top.get('admin1', '')}".strip(", ")
    except Exception:
        pass

    return 34.1378, -77.9150, "Wilmington (28412 / Lords Creek), NC"


def calculate_moon(dt: datetime):
    diff = (dt - datetime(2026, 1, 18)).total_seconds() / 86400.0
    synodic = 29.53058867
    cycle_pos = (diff % synodic) / synodic
    illum = round((1 - math.cos(2 * math.pi * cycle_pos)) / 2 * 100)
    
    if cycle_pos < 0.03 or cycle_pos > 0.97:
        phase = "New Moon 🌑"
    elif cycle_pos < 0.22:
        phase = "Waxing Crescent 🌒"
    elif cycle_pos < 0.28:
        phase = "First Quarter 🌓"
    elif cycle_pos < 0.47:
        phase = "Waxing Gibbous 🌔"
    elif cycle_pos < 0.53:
        phase = "Full Harvest Moon 🌕"
    elif cycle_pos < 0.72:
        phase = "Waning Gibbous 🌖"
    elif cycle_pos < 0.78:
        phase = "Last Quarter 🌗"
    else:
        phase = "Waning Crescent 🌘"
        
    return phase, illum


def fetch_live_nws(lat: float, lon: float):
    headers = {"User-Agent": "(AeroCastWeatherApp, contact@aerocast.io)"}
    try:
        pts = requests.get(f"https://api.weather.gov/points/{round(lat, 4)},{round(lon, 4)}", headers=headers, timeout=4).json()
        stn_url = pts.get("properties", {}).get("observationStations")
        if stn_url:
            stn_res = requests.get(stn_url, headers=headers, timeout=4).json()
            features = stn_res.get("features", [])
            if features:
                stn_id = features[0].get("properties", {}).get("stationIdentifier")
                obs = requests.get(f"https://api.weather.gov/stations/{stn_id}/observations/latest", headers=headers, timeout=4).json()
                props = obs.get("properties", {})
                
                temp_c = props.get("temperature", {}).get("value")
                temp_f = round((temp_c * 9/5) + 32) if temp_c is not None else None
                wind_kmh = props.get("windSpeed", {}).get("value")
                wind_mph = round(wind_kmh * 0.621371, 1) if wind_kmh is not None else 6.0
                rh = props.get("relativeHumidity", {}).get("value")
                hum = round(rh, 1) if rh is not None else 65.0
                desc = props.get("textDescription") or "Clear"
                
                if temp_f is not None:
                    return {"temp": temp_f, "condition": desc, "wind": wind_mph, "humidity": hum}
    except Exception:
        pass
    return None


def get_full_weather_data(query: str = "28412", sport_team: str = "Panthers, Braves"):
    lat, lon, location_name = get_coordinates(query)
    is_lords_creek = "28412" in location_name or (abs(lat - 34.1378) < 0.05 and abs(lon - (-77.9150)) < 0.05)

    now = datetime.now()
    live_nws = fetch_live_nws(lat, lon)
    
    if live_nws and live_nws.get("temp") is not None:
        curr_temp = live_nws["temp"]
        curr_cond = live_nws["condition"]
        curr_wind = live_nws["wind"]
        curr_hum = live_nws["humidity"]
    else:
        curr_temp = 74 if is_lords_creek else 72
        curr_cond = "Clear sky"
        curr_wind = 6.0
        curr_hum = 65.0

    current_sunrise = "06:58 AM"
    current_sunset = "07:10 PM"

    hourly_36 = []
    next_24_probs = []
    peak_precip_val = 5
    peak_precip_time = "2 PM"

    for h in range(36):
        future_dt = now + timedelta(hours=h)
        hr_num = future_dt.hour
        hour_display = future_dt.strftime("%I %p").lstrip("0")
        day_display = future_dt.strftime("%a")
        
        temp_curve = math.sin((hr_num - 8) / 24.0 * 2 * math.pi)
        h_temp = round(curr_temp + (temp_curve * 6))
        h_rain = max(0, round(5 + 5 * math.sin((hr_num - 14) / 24.0 * 2 * math.pi)))
        is_night = (hr_num < 7 or hr_num >= 19)
        h_cond = "Partly cloudy" if h_rain > 10 else ("Clear sky" if not is_night else "Mainly clear")

        if h < 24:
            next_24_probs.append(h_rain)
            if h_rain > peak_precip_val:
                peak_precip_val = h_rain
                peak_precip_time = hour_display

        hourly_36.append({
            "time": hour_display,
            "hour": hour_display,
            "day": day_display,
            "temp": h_temp,
            "condition": h_cond,
            "weather_code": 1 if h_rain <= 10 else 2,
            "rain_chance": h_rain,
            "is_night": is_night
        })

    max_next_24 = max(next_24_probs) if next_24_probs else 5
    precip_summary = f"Precip Now: {hourly_36[0]['rain_chance']}% | Next 24h Max: {max_next_24}% (Peak around {peak_precip_time})"

    daily_list = []
    base_highs = [82, 84, 85, 80, 78]
    base_lows = [68, 67, 66, 64, 62]
    base_rains = [10, 5, 12, 35, 20]

    for i in range(5):
        day_dt = now + timedelta(days=i)
        day_name = day_dt.strftime("%A")
        d_str = day_dt.strftime("%Y-%m-%d")
        
        m_rise_hour = (7.5 + i * 0.75) % 12
        m_rise_amp = "PM" if (7.5 + i * 0.75) < 12 else "AM"
        m_set_hour = (6.5 + i * 0.75) % 12
        m_set_amp = "AM" if (6.5 + i * 0.75) < 12 else "PM"
        
        m_rise_str = f"{max(1, round(m_rise_hour)):02.0f}:20 {m_rise_amp}"
        m_set_str = f"{max(1, round(m_set_hour)):02.0f}:35 {m_set_amp}"
        
        h_val = base_highs[i]
        l_val = base_lows[i]
        r_val = base_rains[i]

        d_rain_day = r_val
        d_rain_night = max(0, round(r_val * 0.3))

        if r_val >= 30:
            d_sum = f"Partly cloudy with isolated afternoon showers, high near {h_val}°F."
            n_sum = f"Comfortable evening with calm winds, low around {l_val}°F."
        else:
            d_sum = f"Sunny to mostly clear skies with light breezes, high near {h_val}°F."
            n_sum = f"Clear and calm night, overnight low of {l_val}°F."

        daily_list.append({
            "date": f"{day_name} ({d_str})",
            "high": h_val,
            "low": l_val,
            "rain_prob_max": r_val,
            "day_rain_prob": d_rain_day,
            "night_rain_prob": d_rain_night,
            "sunrise": current_sunrise,
            "sunset": current_sunset,
            "moon_rise": m_rise_str,
            "moon_set": m_set_str,
            "day_summary": d_sum,
            "night_summary": n_sum
        })

    is_night_now = (now.hour < 7 or now.hour >= 19)
    m_phase, m_illum = calculate_moon(now)

    is_coastal = (lon >= -78.5 and 33.5 <= lat <= 36.5)
    coastal_status = f"Sector: {location_name} (Coastal Waters Active). Water Temp: 76°F. Surf: 2-3 ft swell." if is_coastal else f"Sector: {location_name} (Inland Region). Coastal surf not applicable."
    tide_status = "High Tide: 04:45 AM (+4.6ft) | Low Tide: 11:10 AM (-0.1ft)." if is_coastal else "N/A (Inland Location)."
    lake_desc = f"Lords Creek & Cape Fear Estuary near {location_name}: Calm waters, light current." if is_lords_creek else f"Inland Waterways near {location_name}: Calm waters, good surface visibility."

    frizz_advice = f"Moisture absorption & frizz vulnerability (Humidity {curr_hum}%). Apply anti-humectant smoothing serum." if curr_hum >= 75 else f"Low frizz risk (Humidity {curr_hum}%). Light styling oil suggested."
    makeup_advice = "Matte primer and setting spray recommended for high nocturnal humidity." if curr_hum >= 75 else "Hydrating foundation recommended."

    active_sports = [
        {"title": "Carolina Panthers (NFL)", "venue": "Bank of America Stadium (Charlotte, NC)", "time": "Sunday 1:00 PM", "conditions": "76°F, Sunny & Clear"},
        {"title": "Atlanta Braves (MLB)", "venue": "Truist Park (Atlanta, GA)", "time": "Today 7:20 PM", "conditions": "74°F, Clear sky"}
    ]
    if sport_team:
        for s_item in sport_team.split(","):
            k = s_item.strip().lower()
            if k in SPORTS_DB:
                t_title, t_venue, t_sched, t_cond = SPORTS_DB[k]
                if not any(x["title"] == t_title for x in active_sports):
                    active_sports.append({"title": t_title, "venue": t_venue, "time": t_sched, "conditions": t_cond})

    return {
        "lat": lat, "lon": lon, "location_name": location_name,
        "current": {
            "temp": curr_temp,
            "feels_like": {"label": f"Feels Like: {curr_temp}°F"},
            "humidity": curr_hum,
            "wind": curr_wind,
            "condition": curr_cond,
            "is_night": is_night_now,
            "uv_index": 0.0 if is_night_now else 5.0,
            "sunrise": current_sunrise,
            "sunset": current_sunset,
            "moon_rise": daily_list[0]["moon_rise"],
            "moon_set": daily_list[0]["moon_set"],
            "precip_summary": precip_summary,
            "rain_duration": "No immediate heavy rain expected."
        },
        "hourly_36": hourly_36,
        "daily": daily_list,
        "aqi": {"aqi": 32, "category": "Good"},
        "weather_climate": {
            "enso_index": "NOAA CPC El Niño Advisory Active: Equatorial Pacific anomalies remain stable.",
            "tropical_updates": "National Hurricane Center: No active tropical cyclones threatening the US Atlantic coast.",
            "coastal_waters": coastal_status,
            "tides": tide_status,
            "lake_conditions": lake_desc,
            "winter_storms": "None active across the regional sector.",
            "extreme_weather_24h": "No severe storm watches or convective outlook warnings active.",
            "seasonal_prediction": "Seasonal Outlook: Temperatures projected 1.0°F above seasonal normals.",
            "drought_index": "Precipitation Index: Balanced soil moisture levels across coastal plain.",
            "fire_conditions": "Low fire risk."
        },
        "outdoor_activities": {
            "fishing": {
                "score": 90, 
                "details": "Major Feeding: 6:30 AM – 8:30 AM (Dawn & moving tide). Minor Feeding: 1:00 PM – 2:15 PM. Inshore Targets: Red Drum, Flounder, Speckled Trout in Lords Creek marsh lines."
            },
            "swimming": {"score": 80, "details": "Water temperatures pleasant (~76°F)."},
            "beach": {"score": 85 if is_coastal else 40, "details": "Low rip current risk, clean 2 ft surf breakers." if is_coastal else "Inland sector."},
            "running": {"score": 88, "details": "Comfortable temperatures with light breezes."},
            "walking": {"score": 92, "details": "Prime walking conditions; light surface winds under 10 mph."},
            "biking": {"score": 92, "details": "Dry roads, calm winds, and clear visibility."},
            "skiing": {"score": 5, "details": "Closed / Regional off-season across Appalachian resorts."},
            "mowing": {"score": 85, "details": "Favorable — Allow morning dew to dry before cutting."},
            "hunting": {"score": 90, "details": "Prime barometric stability. Active whitetail movement at sunrise."},
            "camping": {"score": 90, "details": "Prime — Overnight lows around 68°F; dry ground with calm winds."},
            "surfing": {"score": 75 if is_coastal else 10, "details": "2 ft clean surf with light offshore winds." if is_coastal else "N/A - Inland."},
            "boating": {"score": 94, "details": "Cape Fear River and inshore sounds calm, chop under 1 foot."}
        },
        "lifestyle": {
            "hair_makeup": {"hair": frizz_advice, "foundation": makeup_advice, "eyes_lips": "Waterproof brow setting gel recommended."},
            "clothing": {
                "morning": {"shirts": "Light cotton tee", "pants_skirts": "Lightweight chinos or shorts", "children": "Comfortable tee and shorts", "outerwear": "Light layer early"},
                "afternoon": {"shirts": "Breathable short sleeve", "pants_skirts": "Breathable shorts or linen", "children": "Athletic shorts and tee", "outerwear": "None required"},
                "night": {"shirts": "Long-sleeve shirt or light cardigan", "pants_skirts": "Jeans or joggers", "children": "Light pajamas", "outerwear": "Light sweater if outside late"}
            },
            "leaf_change": "Status: Early transition (subtle 5% color shift in wetland maples).",
            "allergen": "Allergen Index: Low to Moderate (Ragweed active across regional corridors).",
            "mosquito_fly": "Activity Index: Low during morning; moderate at dusk.",
            "planting_harvest": [
                {"item": "Kale & Spinach", "action": "Direct Sowing Window", "timing": "Optimal fall planting through October"},
                {"item": "Fall Tomatoes", "action": "Harvesting Peak", "timing": "Active harvest through late autumn frost"},
                {"item": "Carrots & Radishes", "action": "Direct Sowing Window", "timing": "Optimal sowing period"}
            ]
        },
        "sporting_event": {"events": active_sports},
        "astronomy": {
            "sunrise": current_sunrise,
            "sunset": current_sunset,
            "moon_rise": daily_list[0]["moon_rise"],
            "moon_set": daily_list[0]["moon_set"],
            "moon_phase": f"{m_phase} ({m_illum}% illumination)",
            "darkness_window": f"{current_sunset} to {current_sunrise}",
            "stargazing_rating": "90/100 (Excellent) — Clear sky with crisp atmospheric seeing.",
            "visible_planets": [
                "Saturn (Prominent throughout the southern night sky)",
                "Jupiter (Bright beacon in predawn eastern sky)",
                "Venus (Brilliant in WSW evening twilight)",
                "Mars (Visible in morning sky near Gemini)"
            ],
            "celestial_events": [
                {"title": "🍂 Autumn Stargazing Window", "window": "Active tonight", "direction": "High Southern Sky", "notes": "Clear conditions over coastal waters"},
                {"title": "🛰️ ISS Overhead Pass", "window": "Evening", "direction": "WSW to ENE", "notes": "Visible naked-eye transit"}
            ]
        }
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    await flet_fastapi.app_manager.start()
    yield
    await flet_fastapi.app_manager.shutdown()

app = FastAPI(title="AeroCast Ultimate Weather & Climate Dispatcher", lifespan=lifespan)

@app.get("/weather")
def api_weather(query: str = "28412", sport_team: str = "Panthers, Braves"):
    try:
        return get_full_weather_data(query, sport_team)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from main import main as flet_ui_main
app.mount("/", flet_fastapi.app(flet_ui_main))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("server:app", host="0.0.0.0", port=port)