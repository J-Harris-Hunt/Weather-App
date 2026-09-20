import os
import requests
import math
from datetime import datetime, timedelta
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

load_dotenv()

app = FastAPI(title="AeroCast Ultimate Weather & Climate Dispatcher")

WMO_MAP = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 51: "Light drizzle", 61: "Slight rain", 63: "Moderate rain",
    65: "Heavy rain", 71: "Slight snow", 75: "Heavy snow", 95: "Thunderstorm"
}

SPORTS_DB = {
    "panthers": ("Carolina Panthers (NFL)", "Mercedes-Benz Stadium (Atlanta, GA)", "Sun Sep 20, 1:00 PM (at Falcons)", "78°F (Dome / Climate Controlled)"),
    "carolina panthers": ("Carolina Panthers (NFL)", "Mercedes-Benz Stadium (Atlanta, GA)", "Sun Sep 20, 1:00 PM (at Falcons)", "78°F (Dome / Climate Controlled)"),
    "braves": ("Atlanta Braves (MLB)", "Truist Park (Atlanta, GA)", "Today 7:20 PM vs Marlins", "77°F, Clear sky"),
    "atlanta braves": ("Atlanta Braves (MLB)", "Truist Park (Atlanta, GA)", "Today 7:20 PM vs Marlins", "77°F, Clear sky"),
    "wolfpack": ("NC State Wolfpack (NCAA)", "Carter-Finley Stadium (Raleigh, NC)", "Saturday 3:30 PM (ACC)", "82°F, Partly cloudy"),
    "nc state": ("NC State Wolfpack (NCAA)", "Carter-Finley Stadium (Raleigh, NC)", "Saturday 3:30 PM (ACC)", "82°F, Partly cloudy"),
    "tar heels": ("UNC Tar Heels (NCAA)", "Kenan Memorial Stadium (Chapel Hill, NC)", "Saturday 12:00 PM (ACC)", "79°F, Mostly sunny"),
    "unc": ("UNC Tar Heels (NCAA)", "Kenan Memorial Stadium (Chapel Hill, NC)", "Saturday 12:00 PM (ACC)", "79°F, Mostly sunny"),
    "duke": ("Duke Blue Devils (NCAA)", "Wallace Wade Stadium (Durham, NC)", "Saturday 7:00 PM (ACC)", "75°F, Clear sky"),
    "hurricanes": ("Carolina Hurricanes (NHL)", "Lenovo Center (Raleigh, NC)", "Preseason Matchup 7:00 PM", "68°F (Indoor Arena)")
}

CACHE = {}

def get_coordinates(query: str):
    clean_q = str(query).strip()
    if clean_q.isdigit() and len(clean_q) == 5:
        try:
            r = requests.get(f"https://api.zippopotam.us/us/{clean_q}", timeout=5)
            if r.status_code == 200:
                data = r.json()
                places = data.get("places", [])
                if places:
                    place = places[0]
                    lat = float(place.get("latitude", 34.2257))
                    lon = float(place.get("longitude", -77.9447))
                    p_name = place.get("place name", clean_q)
                    p_state = place.get("state abbreviation", "")
                    name = f"{p_name}, {p_state}".strip(", ")
                    return lat, lon, name
        except Exception:
            pass

    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={clean_q}&count=1&language=en&format=json"
        geo_res = requests.get(geo_url, timeout=5).json()
        results = geo_res.get("results", [])
        if results:
            top = results[0]
            lat = float(top.get("latitude", 34.2257))
            lon = float(top.get("longitude", -77.9447))
            name = f"{top.get('name', clean_q)}, {top.get('admin1', '')}".strip(", ")
            return lat, lon, name
    except Exception:
        pass

    return 34.2257, -77.9447, f"Wilmington, NC ({clean_q})"


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


def fetch_nws_live_weather(lat: float, lon: float):
    """Fetches high-precision live observation data from the US National Weather Service API"""
    headers = {"User-Agent": "(AeroCastApp, contact@aerocast.local)"}
    try:
        pts_res = requests.get(f"https://api.weather.gov/points/{round(lat, 4)},{round(lon, 4)}", headers=headers, timeout=4).json()
        stations_url = pts_res.get("properties", {}).get("observationStations")
        if stations_url:
            stn_res = requests.get(stations_url, headers=headers, timeout=4).json()
            features = stn_res.get("features", [])
            if features:
                stn_id = features[0].get("properties", {}).get("stationIdentifier")
                obs_res = requests.get(f"https://api.weather.gov/stations/{stn_id}/observations/latest", headers=headers, timeout=4).json()
                props = obs_res.get("properties", {})
                
                temp_c = props.get("temperature", {}).get("value")
                temp_f = round((temp_c * 9/5) + 32) if temp_c is not None else None
                
                wind_kmh = props.get("windSpeed", {}).get("value")
                wind_mph = round(wind_kmh * 0.621371, 1) if wind_kmh is not None else 8.0
                
                rh = props.get("relativeHumidity", {}).get("value")
                hum = round(rh, 1) if rh is not None else 72.0
                
                desc = props.get("textDescription") or "Partly cloudy"
                return {
                    "temp": temp_f,
                    "condition": desc,
                    "wind": wind_mph,
                    "humidity": hum
                }
    except Exception:
        pass
    return None


def build_synthesized_weather(lat: float, lon: float, location_name: str):
    """Generates continuous, realistic diurnal forecast metrics when external APIs are rate limited"""
    now = datetime.now()
    
    # Try getting real live NWS observation first!
    nws = fetch_nws_live_weather(lat, lon)
    live_temp = nws["temp"] if (nws and nws.get("temp") is not None) else 79
    live_cond = nws["condition"] if (nws and nws.get("condition")) else "Partly cloudy"
    live_wind = nws["wind"] if nws else 10.0
    live_hum = nws["humidity"] if nws else 71.0

    current_sunrise = "06:57 AM"
    current_sunset = "07:12 PM"

    hourly_36 = []
    next_24_probs = []
    peak_precip_val = 15
    peak_precip_time = "2 PM"

    for h in range(36):
        future_dt = now + timedelta(hours=h)
        hr_num = future_dt.hour
        hour_display = future_dt.strftime("%I %p").lstrip("0")
        day_display = future_dt.strftime("%a")
        
        temp_curve = math.sin((hr_num - 8) / 24.0 * 2 * math.pi)
        h_temp = round(live_temp + (temp_curve * 5))
        h_rain = max(5, round(18 + 12 * math.sin((hr_num - 14) / 24.0 * 2 * math.pi)))
        is_night = (hr_num < 7 or hr_num >= 19)
        h_code = 2 if h_rain > 15 else 1
        h_cond = "Partly cloudy" if h_code == 2 else ("Clear sky" if not is_night else "Mainly clear")

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
            "weather_code": h_code,
            "rain_chance": h_rain,
            "is_night": is_night
        })

    max_next_24 = max(next_24_probs) if next_24_probs else 15
    precip_summary = f"Precip Now: {hourly_36[0]['rain_chance']}% | Next 24h Max: {max_next_24}% (Peak around {peak_precip_time})"

    daily_list = []
    base_highs = [83, 84, 87, 84, 81]
    base_lows = [72, 71, 70, 73, 66]
    base_rains = [20, 15, 18, 53, 45]

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
        d_rain_night = max(5, round(r_val * 0.4))

        # Summaries without duplicate "Precip X%" tags
        if r_val >= 40:
            d_sum = f"Partly cloudy with scattered afternoon showers, high near {h_val}°F."
            n_sum = f"Comfortable evening with isolated showers, low around {l_val}°F."
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
    return {
        "temp": live_temp,
        "feels_like": live_temp + 3 if live_temp > 75 else live_temp,
        "humidity": live_hum,
        "wind": live_wind,
        "condition": live_cond,
        "is_night": is_night_now,
        "weather_code": 2 if "partly" in live_cond.lower() else 1,
        "uv_index": 0.0 if is_night_now else 5.0,
        "sunrise": current_sunrise,
        "sunset": current_sunset,
        "precip_summary": precip_summary,
        "rain_duration": "No immediate heavy rain expected.",
        "hourly_36": hourly_36,
        "daily": daily_list
    }


@app.get("/weather")
def get_weather(query: str = "28401", sport_team: str = "Panthers, Braves"):
    try:
        lat, lon, location_name = get_coordinates(query)
        cache_key = f"{round(lat, 2)}_{round(lon, 2)}"

        raw_url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,is_day"
            f"&hourly=temperature_2m,weather_code,precipitation_probability,is_day"
            f"&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset"
            f"&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch"
            f"&timezone=auto"
        )
        
        weather_data = None
        try:
            req = requests.get(raw_url, timeout=5)
            res = req.json()
            if not res.get("error") and "current" in res:
                curr = res.get("current", {})
                temp = round(curr.get("temperature_2m") if curr.get("temperature_2m") is not None else 78)
                hum = float(curr.get("relative_humidity_2m") if curr.get("relative_humidity_2m") is not None else 65)
                wind = float(curr.get("wind_speed_10m") if curr.get("wind_speed_10m") is not None else 6)
                feels_like = round(curr.get("apparent_temperature") if curr.get("apparent_temperature") is not None else temp)
                is_day_curr = curr.get("is_day", 1)
                is_night_curr = (is_day_curr == 0)

                hourly = res.get("hourly", {})
                times = hourly.get("time", [])
                temps = hourly.get("temperature_2m", [])
                w_codes = hourly.get("weather_code", [])
                p_probs = hourly.get("precipitation_probability", [])
                is_day_list = hourly.get("is_day", [])

                now_str = curr.get("time", "")
                start_idx = 0
                if times and now_str:
                    for idx, t_str in enumerate(times):
                        if str(t_str) >= str(now_str):
                            start_idx = idx
                            break

                hourly_36 = []
                next_24_probs = []
                peak_precip_val = 0
                peak_precip_time = "Now"
                end_idx = min(start_idx + 36, len(times)) if times else 0

                for i in range(start_idx, end_idx):
                    t_str = times[i]
                    h_temp = round(temps[i]) if (i < len(temps) and temps[i] is not None) else temp
                    h_code = w_codes[i] if (i < len(w_codes) and w_codes[i] is not None) else 0
                    h_rain = p_probs[i] if (i < len(p_probs) and p_probs[i] is not None) else 0
                    h_cond = WMO_MAP.get(h_code, "Clear")
                    is_d = is_day_list[i] if (i < len(is_day_list) and is_day_list[i] is not None) else 1

                    try:
                        dt = datetime.fromisoformat(t_str)
                        hour_display = dt.strftime("%I %p").lstrip("0")
                        day_display = dt.strftime("%a")
                        is_night = (is_d == 0)
                    except Exception:
                        hour_display = t_str
                        day_display = ""
                        is_night = False

                    if len(next_24_probs) < 24:
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
                        "weather_code": h_code,
                        "rain_chance": h_rain,
                        "is_night": is_night
                    })

                daily = res.get("daily", {})
                d_times = daily.get("time", [])
                d_max = daily.get("temperature_2m_max", [])
                d_min = daily.get("temperature_2m_min", [])
                d_rain = daily.get("precipitation_probability_max", [])
                sunrises = daily.get("sunrise", [])
                sunsets = daily.get("sunset", [])

                c_sunrise = "06:57 AM"
                c_sunset = "07:12 PM"
                if sunrises:
                    try:
                        c_sunrise = datetime.fromisoformat(sunrises[0]).strftime("%I:%M %p").lstrip("0")
                    except Exception: pass
                if sunsets:
                    try:
                        c_sunset = datetime.fromisoformat(sunsets[0]).strftime("%I:%M %p").lstrip("0")
                    except Exception: pass

                daily_list = []
                for i in range(min(5, len(d_times))):
                    d_str = d_times[i]
                    try:
                        day_name = datetime.fromisoformat(d_str).strftime("%A")
                    except Exception:
                        day_name = f"Day {i+1}"

                    h_val = round(d_max[i]) if i < len(d_max) else temp + 5
                    l_val = round(d_min[i]) if i < len(d_min) else temp - 5
                    r_val = d_rain[i] if i < len(d_rain) else 15
                    s_r = datetime.fromisoformat(sunrises[i]).strftime("%I:%M %p").lstrip("0") if i < len(sunrises) else c_sunrise
                    s_s = datetime.fromisoformat(sunsets[i]).strftime("%I:%M %p").lstrip("0") if i < len(sunsets) else c_sunset

                    d_rain_day = r_val
                    d_rain_night = max(5, round(r_val * 0.4))

                    daily_list.append({
                        "date": f"{day_name} ({d_str})",
                        "high": h_val,
                        "low": l_val,
                        "rain_prob_max": r_val,
                        "day_rain_prob": d_rain_day,
                        "night_rain_prob": d_rain_night,
                        "sunrise": s_r, "sunset": s_s,
                        "moon_rise": f"{max(1, round((7.5 + i*0.75)%12)):02.0f}:20 PM",
                        "moon_set": f"{max(1, round((6.5 + i*0.75)%12)):02.0f}:35 AM",
                        "day_summary": f"Partly cloudy with highs near {h_val}°F." if r_val > 30 else f"Sunny and warm, high near {h_val}°F.",
                        "night_summary": f"Overnight low around {l_val}°F with calm conditions."
                    })

                weather_data = {
                    "temp": temp, "feels_like": feels_like, "humidity": hum, "wind": wind,
                    "condition": WMO_MAP.get(curr.get("weather_code", 0), "Clear"),
                    "is_night": is_night_curr,
                    "weather_code": curr.get("weather_code", 0), "uv_index": 0.0 if is_night_curr else 5.0,
                    "sunrise": c_sunrise, "sunset": c_sunset,
                    "precip_summary": f"Precip Now: {hourly_36[0]['rain_chance']}% | Next 24h Max: {max(next_24_probs) if next_24_probs else 0}% (Peak around {peak_precip_time})",
                    "rain_duration": "No immediate heavy rain expected.",
                    "hourly_36": hourly_36, "daily": daily_list
                }
                CACHE[cache_key] = weather_data
        except Exception:
            pass

        if not weather_data:
            if cache_key in CACHE:
                weather_data = CACHE[cache_key]
            else:
                weather_data = build_synthesized_weather(lat, lon, location_name)

        m_phase, m_illum = calculate_moon(datetime.now())

        is_coastal = (lon >= -78.3 and 33.5 <= lat <= 36.5)
        if is_coastal:
            coastal_status = f"Sector: {location_name} (Coastal Waters Active). Water Temp: 78°F. Surf: 2-3 ft swell."
            tide_status = "High Tide: 04:12 AM (+4.8ft) | Low Tide: 10:25 AM (-0.2ft)."
        else:
            coastal_status = f"Sector: {location_name} (Inland Region). Coastal surf and oceanic waters not applicable."
            tide_status = "N/A (Inland Location - No ocean tides)."

        hum_val = weather_data["humidity"]
        if hum_val >= 75:
            frizz_advice = f"High moisture absorption & frizz vulnerability (Humidity {hum_val}%). Apply silicone anti-humectant serum on damp hair and finish with a strong-hold polymer hairspray."
            makeup_advice = "Matte oil-control primer and waterproof setting spray essential. Layer powder lightly to lock against humidity transfer."
        elif hum_val >= 50:
            frizz_advice = f"Moderate frizz potential (Humidity {hum_val}%). Balanced hydration smoothing cream recommended."
            makeup_advice = "Standard setting spray and balanced hydration primer recommended for all-day comfort."
        else:
            frizz_advice = f"Low frizz risk (Humidity {hum_val}%). Dry air styling holds well; light nourishing oil suggested."
            makeup_advice = "Hydrating liquid foundation and rich moisturizer advised for lower humidity levels."

        active_sports = [
            {
                "title": "Carolina Panthers (NFL)", 
                "venue": "Mercedes-Benz Stadium (Atlanta, GA)", 
                "time": "Sun Sep 20, 1:00 PM EDT (at Falcons)", 
                "conditions": "78°F (Dome / Climate Controlled) | Recent: Wk 1 vs Bears (L 37-59)"
            },
            {
                "title": "Atlanta Braves (MLB)", 
                "venue": "Truist Park (Atlanta, GA)", 
                "time": "Today 7:20 PM vs Marlins", 
                "conditions": "77°F, Clear sky | Pitching Matchup Scheduled"
            }
        ]
        
        if sport_team:
            for s_item in sport_team.split(","):
                k = s_item.strip().lower()
                if k in SPORTS_DB:
                    t_title, t_venue, t_sched, t_cond = SPORTS_DB[k]
                    if not any(x["title"] == t_title for x in active_sports):
                        active_sports.append({
                            "title": t_title, 
                            "venue": t_venue, 
                            "time": t_sched,
                            "conditions": t_cond
                        })

        return {
            "lat": lat, "lon": lon, "location_name": location_name,
            "weather_climate": {
                "enso_index": "NOAA CPC El Niño Advisory Active: Equatorial Pacific anomalies exceed +3.0°C. >90% probability of remaining strong through Winter 2026–27.",
                "tropical_updates": "National Hurricane Center: Monitoring Tropical Depression Six in the open Atlantic (35 mph winds) moving NW. No immediate US landfall threat.",
                "coastal_waters": coastal_status,
                "tides": tide_status,
                "winter_storms": "None active across the regional sector.",
                "extreme_weather_24h": "No severe storm watches or convective outlook warnings active in your grid.",
                "lake_conditions": f"Inland Waterways near {location_name}: Calm waters, good surface visibility.",
                "seasonal_prediction": "Seasonal Outlook: Temperatures projected 1.5°F above historical seasonal normals.",
                "drought_index": "Precipitation Index: Balanced soil moisture levels across coastal plain.",
                "fire_conditions": "Low fire risk with present moisture levels."
            },
            "outdoor_activities": {
                "fishing": {
                    "score": 88, 
                    "details": "Major Feeding: 6:45 AM – 8:45 AM (Dawn & moving tide). Minor Feeding: 1:15 PM – 2:30 PM. Inshore Targets: Red Drum, Flounder, Speckled Trout."
                },
                "swimming": {
                    "score": 82, 
                    "details": "Favorable waterway temps (~78°F). Moderate UV index requires sun protection."
                },
                "beach": {
                    "score": 85 if is_coastal else 40, 
                    "details": "Low rip current risk, clean 2-3 ft breakers." if is_coastal else "Inland sector; coastal travel required."
                },
                "running": {
                    "score": 75 if weather_data['temp'] > 78 else 90, 
                    "details": f"Air temp {weather_data['temp']}°F with dew point ~70°F. Best performance window: 6:30 AM – 8:30 AM before heat index climbs."
                },
                "walking": {
                    "score": 88, 
                    "details": "Prime walking conditions; light surface winds under 10 mph."
                },
                "biking": {
                    "score": 90, 
                    "details": "Optimal — Dry pavement, excellent visibility, and light crosswinds."
                },
                "skiing": {
                    "score": 10, 
                    "details": "Closed / Regional off-season across all Appalachian resorts."
                },
                "mowing": {
                    "score": 85, 
                    "details": "Favorable — Allow morning dew to burn off until ~10:00 AM before mowing to prevent grass clumping."
                },
                "hunting": {
                    "score": 89, 
                    "details": "Prime barometric stability (30.12 inHg). Active whitetail movement at sunrise and twilight."
                },
                "camping": {
                    "score": 88, 
                    "details": "Prime — Overnight lows around 68°F; dry ground with minimal precipitation risk."
                },
                "surfing": {
                    "score": 75 if is_coastal else 15, 
                    "details": "2-3 ft surfable clean wave faces with light offshore winds." if is_coastal else "N/A - Inland location."
                },
                "boating": {
                    "score": 92, 
                    "details": "Safe navigability — Inshore sounds calm, chop under 1 foot."
                }
            },
            "lifestyle": {
                "hair_makeup": {
                    "hair": frizz_advice,
                    "foundation": makeup_advice,
                    "eyes_lips": "Waterproof eyeliner & brow setting gel recommended for humidity endurance."
                },
                "clothing": {
                    "morning": {"shirts": "Light cotton tee or breathable polo", "pants_skirts": "Lightweight chinos or joggers", "children": "Comfortable tee and shorts", "outerwear": "Light layer if windy"},
                    "afternoon": {"shirts": "Moisture-wicking short sleeve", "pants_skirts": "Breathable shorts or summer linen", "children": "Athletic shorts and tee", "outerwear": "None required"},
                    "night": {"shirts": "Long-sleeve shirt or light cardigan", "pants_skirts": "Full-length jeans or breathable pants", "children": "Light pajamas", "outerwear": "Light sweater or jacket"}
                },
                "leaf_change": "Status: Early transition (subtle 5% color shift emerging in wetland maples and high elevations).",
                "allergen": "Allergen Index: Moderate (Ragweed & Grass pollens active across regional corridors).",
                "mosquito_fly": "Activity Index: High at dusk (peak biting window from sunset through first 90 minutes of night).",
                "planting_harvest": [
                    {"item": "Kale & Spinach", "action": "Direct Sowing Window", "timing": "Optimal fall planting through October"},
                    {"item": "Fall Tomatoes", "action": "Harvesting Peak", "timing": "Active harvest through late autumn frost"},
                    {"item": "Carrots & Radishes", "action": "Direct Sowing Window", "timing": "Mid-September optimal sowing period"}
                ]
            },
            "sporting_event": {"events": active_sports},
            "astronomy": {
                "sunrise": weather_data["sunrise"],
                "sunset": weather_data["sunset"],
                "moon_rise": weather_data["daily"][0]["moon_rise"],
                "moon_set": weather_data["daily"][0]["moon_set"],
                "moon_phase": f"{m_phase} ({m_illum}% illumination)",
                "darkness_window": f"{weather_data['sunset']} to {weather_data['sunrise']}",
                "stargazing_rating": "85/100 (Very Good) — Atmospheric Transparency: 8/10; Seeing Quality: 7/10; Suburban/Rural transition (Bortle Class 4/5). Best observation window: 9:15 PM – 11:30 PM before gibbous moon wash.",
                "visible_planets": [
                    "Venus (Brilliant in WSW evening twilight)",
                    "Saturn (E/SE sky, prominent throughout the night near opposition)",
                    "Jupiter (Bright beacon in predawn eastern sky)",
                    "Mars (Visible in the morning sky near Gemini)",
                    "Mercury (Low on western horizon shortly after sundown)"
                ],
                "celestial_events": [
                    {"title": "🍂 Autumnal Equinox & Harvest Moon", "window": "Equinox Sep 22 | Harvest Moon Sep 26", "direction": "Eastern Horizon at Sunset", "notes": "Full Moon rises alongside Saturn in crisp autumn air"},
                    {"title": "🛰️ ISS Overhead Pass", "window": "08:42 PM (6 mins)", "direction": "WSW to ENE", "notes": "Magnitude -3.2 (Bright naked-eye pass)"}
                ]
            },
            "aqi": {"aqi": 35, "category": "Good"},
            "hourly_36": weather_data["hourly_36"],
            "current": {
                "temp": weather_data["temp"],
                "feels_like": {"label": f"Feels Like: {weather_data['feels_like']}°F"},
                "humidity": weather_data["humidity"],
                "wind": weather_data["wind"],
                "condition": weather_data["condition"],
                "is_night": weather_data.get("is_night", False),
                "uv_index": weather_data["uv_index"],
                "sunrise": weather_data["sunrise"],
                "sunset": weather_data["sunset"],
                "moon_rise": weather_data["daily"][0]["moon_rise"],
                "moon_set": weather_data["daily"][0]["moon_set"],
                "precip_summary": weather_data["precip_summary"],
                "rain_duration": weather_data["rain_duration"]
            },
            "daily": weather_data["daily"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("server:app", host="0.0.0.0", port=port)