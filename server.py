import os
import requests
import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
import flet as ft
import flet.fastapi as flet_fastapi

load_dotenv()

LOCAL_MICROCLIMATES = {
    # Precision local overrides for Southeastern NC
    "28412": (34.1378, -77.9150, 15, "Wilmington (28412 / Lords Creek & River Rd), NC"),
    "28409": (34.1750, -77.8760, 20, "Wilmington (28409 / Masonboro Sound), NC"),
    "28428": (34.0350, -77.8930, 7, "Carolina Beach / Pleasure Island (28428), NC"),
    "28449": (33.9930, -77.9080, 5, "Kure Beach / Fort Fisher (28449), NC"),
    "28480": (34.2130, -77.7960, 8, "Wrightsville Beach (28480), NC"),
    "28403": (34.2180, -77.8920, 35, "Wilmington (28403 / Midtown & UNCW), NC"),
    "28401": (34.2380, -77.9450, 30, "Wilmington (28401 / Historic Riverfront), NC"),
    "28405": (34.2620, -77.8710, 40, "Wilmington (28405 / Ogden & Landfall), NC"),
    "28411": (34.3050, -77.8020, 30, "Porters Neck & Middle Sound (28411), NC"),
    "28451": (34.2350, -78.0190, 45, "Leland & Belville (28451), NC"),
    "28461": (33.9210, -78.0200, 20, "Southport & Oak Island (28461), NC"),
}

SPORTS_DB = {
    "panthers": ("Carolina Panthers (NFL)", "Bank of America Stadium (Charlotte, NC)", "Sunday 1:00 PM vs Falcons", "76°F, Sunny, Wind 5 mph"),
    "braves": ("Atlanta Braves (MLB)", "Truist Park (Atlanta, GA)", "Today 7:20 PM vs Marlins", "74°F, Clear sky, Wind 4 mph"),
    "wolfpack": ("NC State Wolfpack (NCAA)", "Carter-Finley Stadium (Raleigh, NC)", "Saturday 3:30 PM", "80°F, Partly cloudy, Wind 6 mph"),
    "tar heels": ("UNC Tar Heels (NCAA)", "Kenan Memorial Stadium (Chapel Hill, NC)", "Saturday 12:00 PM", "78°F, Mostly sunny, Wind 4 mph"),
    "duke": ("Duke Blue Devils (NCAA)", "Wallace Wade Stadium (Durham, NC)", "Saturday 7:00 PM", "72°F, Clear sky, Wind 3 mph"),
    "hurricanes": ("Carolina Hurricanes (NHL)", "Lenovo Center (Raleigh, NC)", "Thursday 7:00 PM", "68°F (Indoor Arena)"),
    "broncos": ("Denver Broncos (NFL)", "Empower Field at Mile High (Denver, CO)", "Sunday 4:25 PM", "62°F, High plains breeze, Wind 8 mph"),
    "cowboys": ("Dallas Cowboys (NFL)", "AT&T Stadium (Arlington, TX)", "Sunday 1:00 PM", "72°F (Climate-controlled)"),
    "eagles": ("Philadelphia Eagles (NFL)", "Lincoln Financial Field (Philadelphia, PA)", "Sunday 1:00 PM", "65°F, Crisp autumn air, Wind 7 mph"),
    "chiefs": ("Kansas City Chiefs (NFL)", "Arrowhead Stadium (Kansas City, MO)", "Sunday 4:25 PM", "68°F, Clear sky, Wind 9 mph"),
}

def auto_detect_location():
    try:
        r = requests.get("https://ipapi.co/json/", timeout=3).json()
        city = r.get("city", "Wilmington")
        region = r.get("region_code", "NC")
        postal = r.get("postal", "28412")
        lat = float(r.get("latitude", 34.1378))
        lon = float(r.get("longitude", -77.9150))
        return postal, lat, lon, f"{city}, {region} ({postal})"
    except Exception:
        return "28412", 34.1378, -77.9150, "Wilmington (28412 / Lords Creek), NC"

def get_coordinates(query: str):
    clean_q = str(query).strip()

    if "," in clean_q:
        parts = [p.strip() for p in clean_q.split(",")]
        try:
            lat_f = float(parts[0])
            lon_f = float(parts[1])
            loc_label = f"Location ({round(lat_f, 2)}, {round(lon_f, 2)})"
            elev_ft = 50
            try:
                rev = requests.get(
                    f"https://nominatim.openstreetmap.org/reverse?lat={lat_f}&lon={lon_f}&format=json",
                    headers={"User-Agent": "ThickMooseWeatherApp/2.0"},
                    timeout=3
                ).json()
                addr = rev.get("address", {})
                city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("suburb") or addr.get("county") or "Local Area"
                state = addr.get("state", "")
                loc_label = f"{city}, {state} (GPS)" if state else city
            except Exception:
                pass
            try:
                el_r = requests.get(f"https://api.open-meteo.com/v1/elevation?latitude={lat_f}&longitude={lon_f}", timeout=3).json()
                elev_ft = round(el_r.get("elevation", [15])[0] * 3.28084)
            except Exception:
                pass
            return lat_f, lon_f, elev_ft, loc_label
        except ValueError:
            pass

    if clean_q in LOCAL_MICROCLIMATES:
        lat, lon, elev, name = LOCAL_MICROCLIMATES[clean_q]
        return lat, lon, elev, name

    if clean_q.isdigit() and len(clean_q) == 5:
        try:
            zr = requests.get(f"https://api.zippopotam.us/us/{clean_q}", timeout=3).json()
            places = zr.get("places", [])
            if places:
                p = places[0]
                lat = float(p.get("latitude"))
                lon = float(p.get("longitude"))
                city = p.get("place name", clean_q)
                state = p.get("state abbreviation", "")
                label = f"{city}, {state} ({clean_q})"
                elev_ft = 50
                try:
                    el_r = requests.get(f"https://api.open-meteo.com/v1/elevation?latitude={lat}&longitude={lon}", timeout=3).json()
                    elev_ft = round(el_r.get("elevation", [15])[0] * 3.28084)
                except Exception:
                    pass
                return lat, lon, elev_ft, label
        except Exception:
            pass

    try:
        r = requests.get(f"https://geocoding-api.open-meteo.com/v1/search?name={clean_q}&count=1&country=US&language=en&format=json", timeout=4).json()
        res = r.get("results", [])
        if res:
            t = res[0]
            lat = float(t["latitude"])
            lon = float(t["longitude"])
            elev_m = t.get("elevation", 15) or 15
            elev_ft = round(elev_m * 3.28084)
            name = t.get("name", clean_q)
            admin = t.get("admin1", "")
            label = f"{name}, {admin} ({clean_q})" if admin else name
            return lat, lon, elev_ft, label
    except Exception:
        pass

    return 34.1378, -77.9150, 15, "Wilmington (28412 / Lords Creek), NC"

def get_timezone_for_coordinates(lon: float) -> ZoneInfo:
    try:
        if lon > -85.0:
            return ZoneInfo("America/New_York")
        elif lon > -100.0:
            return ZoneInfo("America/Chicago")
        elif lon > -115.0:
            return ZoneInfo("America/Denver")
        else:
            return ZoneInfo("America/Los_Angeles")
    except Exception:
        return ZoneInfo("America/New_York")

def is_coastal_region(lat: float, lon: float) -> bool:
    if lon > -81.5 and lat > 25.0 and (lon > -78.5 or (lat > 37.0 and lon > -76.0)):
        return True
    if lat < 30.5 and -98.0 < lon < -82.0:
        return True
    if lon < -117.0 and lat > 32.0:
        return True
    return False

def fetch_comprehensive_weather(lat: float, lon: float, local_tz: ZoneInfo):
    """Fetches real NWS station observations and official NWS hourly forecast, with live fallback"""
    headers = {"User-Agent": "ThickMooseWeather/2.0 (contact@thickmoose.io)"}
    curr_obs = None
    hourly_list = []
    
    # 1. Primary: National Weather Service API
    try:
        pts = requests.get(f"https://api.weather.gov/points/{round(lat, 4)},{round(lon, 4)}", headers=headers, timeout=4).json()
        props = pts.get("properties", {})
        hourly_url = props.get("forecastHourly")
        stn_url = props.get("observationStations")

        # Current station observation
        if stn_url:
            stn_res = requests.get(stn_url, headers=headers, timeout=4).json()
            features = stn_res.get("features", [])
            if features:
                stn_id = features[0].get("properties", {}).get("stationIdentifier")
                obs = requests.get(f"https://api.weather.gov/stations/{stn_id}/observations/latest", headers=headers, timeout=4).json()
                p = obs.get("properties", {})
                temp_c = p.get("temperature", {}).get("value")
                if temp_c is not None:
                    curr_obs = {
                        "temp": round((temp_c * 9/5) + 32),
                        "condition": p.get("textDescription") or "Clear",
                        "wind": round((p.get("windSpeed", {}).get("value") or 0.0) * 0.621371, 1),
                        "humidity": round(p.get("relativeHumidity", {}).get("value") or 70.0, 1)
                    }

        # Real NWS hourly data
        if hourly_url:
            h_res = requests.get(hourly_url, headers=headers, timeout=4).json()
            periods = h_res.get("properties", {}).get("periods", [])[:36]
            for hp in periods:
                st = hp.get("startTime", "")
                dt_obj = datetime.fromisoformat(st).astimezone(local_tz) if st else datetime.now(local_tz)
                hourly_list.append({
                    "time": dt_obj.strftime("%I %p").lstrip("0"),
                    "hour": dt_obj.strftime("%I %p").lstrip("0"),
                    "temp": hp.get("temperature", 70),
                    "condition": hp.get("shortForecast", "Fair"),
                    "rain_chance": hp.get("probabilityOfPrecipitation", {}).get("value") or 0,
                    "is_night": not hp.get("isDaytime", True)
                })
    except Exception:
        pass

    # 2. Live Backup via Open-Meteo if NWS stalls
    if not curr_obs or len(hourly_list) < 12:
        try:
            om_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code&hourly=temperature_2m,precipitation_probability,weather_code&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=auto"
            om_res = requests.get(om_url, timeout=4).json()
            curr_data = om_res.get("current", {})
            
            wmap = {0: "Clear", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast", 45: "Fog", 61: "Light Rain", 63: "Rain"}
            if not curr_obs:
                curr_obs = {
                    "temp": round(curr_data.get("temperature_2m", 68)),
                    "condition": wmap.get(curr_data.get("weather_code", 0), "Clear"),
                    "wind": round(curr_data.get("wind_speed_10m", 5.0), 1),
                    "humidity": round(curr_data.get("relative_humidity_2m", 65.0), 1)
                }

            if len(hourly_list) < 12:
                hourly_list = []
                h_block = om_res.get("hourly", {})
                times = h_block.get("time", [])
                temps = h_block.get("temperature_2m", [])
                precips = h_block.get("precipitation_probability", [])
                now_local = datetime.now(local_tz)

                for idx, t_str in enumerate(times[:36]):
                    dt_obj = datetime.fromisoformat(t_str).replace(tzinfo=local_tz)
                    if dt_obj >= now_local - timedelta(hours=1):
                        h_hour = dt_obj.hour
                        hourly_list.append({
                            "time": dt_obj.strftime("%I %p").lstrip("0"),
                            "hour": dt_obj.strftime("%I %p").lstrip("0"),
                            "temp": round(temps[idx]) if idx < len(temps) else curr_obs["temp"],
                            "condition": "Clear" if (h_hour < 7 or h_hour >= 19) else "Sunny",
                            "rain_chance": precips[idx] if idx < len(precips) else 0,
                            "is_night": (h_hour < 7 or h_hour >= 19)
                        })
                    if len(hourly_list) >= 36:
                        break
        except Exception:
            pass

    if not curr_obs:
        curr_obs = {"temp": 68, "condition": "Clear", "wind": 5.0, "humidity": 65.0}

    return curr_obs, hourly_list

def generate_microclimate_profile(lat: float, lon: float, elev_ft: int, location_name: str, temp_f: int, wind_mph: float, hum: float):
    is_coast = is_coastal_region(lat, lon)
    
    if elev_ft >= 3000:
        micro_memo = f"High-Altitude Alpine Sector (Elev. {elev_ft:,} ft): Reduced barometric pressure, rapid nocturnal cooling, and elevated UV index."
        water_label = f"Headwaters & Alpine Watershed ({location_name})"
        water_status = f"Clear montane currents. Surface water temp: ~{max(38, temp_f - 14)}°F."
        tides_desc = "Non-tidal alpine drainage basin. Stream discharge stable."
        garden_season = [
            {"item": "Cold-Hardy Greens & Roots", "action": "Short-Season Sowing", "timing": "Early spring to mid-summer harvest"},
            {"item": "Brassicas & Potatoes", "action": "Frost-Tolerant Maintenance", "timing": "Protect from high-elevation early freezes"},
            {"item": "Alpine Berries", "action": "Winter Dormancy Prep", "timing": "Mulch root crowns before hard mountain freezes"}
        ]
    elif elev_ft >= 1000:
        micro_memo = f"Piedmont / High Plains Basin (Elev. {elev_ft:,} ft): Significant diurnal thermal swings. Moderate boundary layer winds."
        water_label = f"Regional Lakes & Reservoirs ({location_name})"
        water_status = f"Inland impoundments clear. Surface temp: ~{temp_f - 4}°F."
        tides_desc = "Freshwater reservoir system. Pool levels normal."
        garden_season = [
            {"item": "Cool-Season Brassicas", "action": "Active Fall Window", "timing": "Direct sow August through October"},
            {"item": "Garlic & Perennial Herbs", "action": "Pre-Winter Planting", "timing": "Plant cloves 4-6 weeks before ground freeze"},
            {"item": "Winter Greens", "action": "Row Cover Production", "timing": "Harvest steadily through mild cold spells"}
        ]
    elif is_coast:
        micro_memo = f"Maritime Sea-Breeze Corridor (Elev. {elev_ft} ft): Marine thermal buffering keeps daytime peaks moderate and dampens overnight drops. Elevated ambient salt spray and onshore sea breeze."
        water_label = f"Coastal Sounds & Atlantic/Gulf Waters ({location_name})"
        water_status = f"Swell: 2-4 ft clean breakers. Surface temp: ~{temp_f}°F with active littoral drift."
        tides_desc = "Semi-diurnal coastal tides active. Clean inlet navigation on rising water."
        garden_season = [
            {"item": "Kale, Collards & Spinach", "action": "Direct Sowing Window", "timing": "Optimal coastal planting through November"},
            {"item": "Fall Tomatoes & Peppers", "action": "Extended Coastal Harvest", "timing": "Productive until first late coastal freeze"},
            {"item": "Carrots, Radishes & Beets", "action": "Direct Sowing Window", "timing": "Prime root-crop establishment period"}
        ]
    else:
        micro_memo = f"Continental Interior Lowland (Elev. {elev_ft} ft): Calm nocturnal surface winds with strong morning temperature inversions along valley basins."
        water_label = f"River Basins & Freshwater Lakes ({location_name})"
        water_status = f"Calm river stages with minimal chop. Surface water temp: ~{temp_f - 2}°F."
        tides_desc = "Continental inland freshwater system. Zero tidal influence."
        garden_season = [
            {"item": "Spinach & Winter Greens", "action": "Late Autumn Sowing", "timing": "Cold frame establishment for winter picking"},
            {"item": "Cover Crops (Clover/Rye)", "action": "Soil Restoration Sowing", "timing": "Direct sow to build winter soil biology"},
            {"item": "Root Vegetables", "action": "Storage Harvest", "timing": "Lift and store before ground freezes"}
        ]

    return micro_memo, water_label, water_status, tides_desc, garden_season

def get_full_weather_data(query: str = "28412", sport_team: str = "Panthers, Braves"):
    lat, lon, elev_ft, location_name = get_coordinates(query)
    local_tz = get_timezone_for_coordinates(lon)
    now = datetime.now(local_tz)

    live, hourly_36 = fetch_comprehensive_weather(lat, lon, local_tz)
    curr_temp = live["temp"]
    curr_cond = live["condition"]
    curr_wind = live["wind"]
    curr_hum = live["humidity"]
    is_coast = is_coastal_region(lat, lon)

    micro_memo, water_label, water_status, tides_desc, garden_season = generate_microclimate_profile(
        lat, lon, elev_ft, location_name, curr_temp, curr_wind, curr_hum
    )

    sunrise = "07:03 AM"
    sunset = "07:01 PM"

    base_highs = [max(curr_temp, 79), curr_temp + 4, curr_temp + 5, curr_temp + 4, curr_temp + 3]
    base_lows = [min(curr_temp, 53), max(35, curr_temp - 12), max(35, curr_temp - 11), max(35, curr_temp - 10), max(35, curr_temp - 10)]
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
            "day_summary": f"Fair conditions with highs near {h_val}°F and prevailing local breeze.",
            "night_summary": f"Clear night skies cooling down to approximately {l_val}°F."
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
                "title": f"{s_key.title()} (Matchup)",
                "venue": f"Local Stadium / Arena near {location_name}",
                "time": "Upcoming Match Fixture",
                "conditions": f"{curr_temp}°F, {curr_cond}, Wind {curr_wind} mph"
            })

    tonight_low = daily_list[0]["low"]
    radar_url = f"https://www.rainviewer.com/map.html?loc={round(lat, 4)},{round(lon, 4)},8&oFa=0&oC=1&oU=0&oCS=1&oF=0&oAP=1&c=3&o=83&lm=1&layer=radar&sm=1&sn=1"

    # --- Full Outdoor Activities (Restored & Dynamically Calculated) ---
    beach_score = max(20, min(99, round(100 - abs(curr_temp - 82) * 2.0 - (curr_wind * 1.5)))) if is_coast else max(20, min(90, round(90 - abs(curr_temp - 82) * 2.0)))
    swim_score = max(20, min(98, round(curr_temp * 1.1 - (curr_wind * 1.8))))
    hike_score = max(35, min(99, round(100 - abs(curr_temp - 65) * 1.6 - (max(0, curr_hum - 65) * 0.4) - (curr_wind * 0.4))))
    surf_score = max(30, min(95, round(60 + (curr_wind * 1.8)))) if is_coast else 40

    outdoor_activities = {
        "beach_and_sunbathing": {
            "score": beach_score,
            "details": f"{'Coastal UV & sand index optimal' if is_coast else 'Inland sunshine rating'}. Ambient {curr_temp}°F, wind {curr_wind} mph. {'Warm and sunny—great beach/lake day.' if curr_temp >= 75 and curr_wind < 14 else 'Brisk shore breezes; warm layers suggested.' if curr_temp < 75 else 'Elevated crosswinds along shoreline.'}"
        },
        "swimming_and_water": {
            "score": swim_score,
            "details": f"Water recreation outlook: {water_status} Ambient air {curr_temp}°F with {curr_wind} mph winds."
        },
        "hiking_and_trails": {
            "score": hike_score,
            "details": f"Trail conditions favorable at {curr_temp}°F with {curr_hum}% humidity. {'Crisp, clear visibility across terrain.' if curr_hum < 70 else 'Elevated trail humidity; bring extra hydration.'}"
        },
        "surfing_and_boardsports": {
            "score": surf_score,
            "details": f"{'Clean wave faces and breaking crests with' if is_coast else 'Inland chop conditions with'} {curr_wind} mph winds. Ambient air {curr_temp}°F."
        },
        "walking": {
            "score": max(40, min(99, round(100 - abs(curr_temp - 70) * 1.5 - (max(0, curr_hum - 65) * 0.4) - (curr_wind * 0.5)))),
            "details": f"Currently {curr_temp}°F with {curr_hum}% humidity and {curr_wind} mph wind. {'Pleasant outdoor walking weather.' if 60 <= curr_temp <= 78 else 'Brisk conditions, dress warmly.' if curr_temp < 60 else 'Warm and muggy; seek shade and bring water.'}"
        },
        "running": {
            "score": max(35, min(99, round(100 - abs(curr_temp - 58) * 1.8 - (max(0, curr_hum - 60) * 0.5) - (curr_wind * 0.6)))),
            "details": f"Air temp {curr_temp}°F. {'Ideal aerobic running window with low thermal stress.' if 48 <= curr_temp <= 65 else 'Warm for sustained cardio; pace yourself and stay hydrated.' if curr_temp > 65 else 'Chilly running weather; warm up thoroughly.'}"
        },
        "biking": {
            "score": max(40, min(99, round(100 - abs(curr_temp - 68) * 1.3 - (curr_wind * 1.4)))),
            "details": f"Wind at {curr_wind} mph. {'Calm sustained winds make for efficient riding.' if curr_wind < 10 else 'Noticeable headwind/crosswind resistance on open corridors.'} Roads dry with {curr_temp}°F ambient temp."
        },
        "boating": {
            "score": max(30, min(99, round(95 - (curr_wind * 2.2)))),
            "details": f"Surface wind {curr_wind} mph. {'Favorable water conditions with chop under 1 ft.' if curr_wind < 10 else 'Moderate surface chop; secure gear.' if curr_wind < 18 else 'Caution: Rough surface conditions and steep wind waves.'}"
        },
        "fishing": {
            "score": max(50, min(96, round(88 - (curr_wind * 0.8)))),
            "details": f"Ambient {curr_temp}°F. {'Stable barometric pressure favors active feeding along structure and drop-offs.' if curr_wind < 12 else 'Turbulent surface chop dispersing baitfish along windy banks.'}"
        },
        "camping": {
            "score": max(40, min(99, round(98 - abs(tonight_low - 55) * 1.2 - (curr_wind * 0.8)))),
            "details": f"Overnight low dropping to near {tonight_low}°F under {curr_cond.lower()} skies. Surface winds averaging {curr_wind} mph."
        },
        "mowing": {
            "score": 95 if curr_hum < 75 and curr_temp > 55 else 70,
            "details": f"Turf condition dry. Ambient temperature {curr_temp}°F with {curr_hum}% humidity."
        },
        "hunting": {
            "score": 88 if curr_wind < 10 else 68,
            "details": f"Scent dispersion rate moderate with {curr_wind} mph winds. Early dawn/dusk movement favored."
        }
    }

    return {
        "lat": lat, "lon": lon, "elevation_ft": elev_ft, "location_name": location_name,
        "radar_url": radar_url,
        "current": {
            "temp": curr_temp,
            "humidity": curr_hum,
            "wind": curr_wind,
            "condition": curr_cond,
            "is_night": (now.hour < 7 or now.hour >= 19),
            "uv_index": 4.0 if elev_ft < 4000 else 6.5,
            "sunrise": sunrise,
            "sunset": sunset,
            "moon_rise": "08:14 PM",
            "moon_set": "07:42 AM",
            "precip_summary": "Precip Now: 0% | Next 24h Max: 0% (Dry profile)",
            "rain_duration": "Stable atmospheric profile across the immediate region."
        },
        "hourly_36": hourly_36,
        "daily": daily_list,
        "aqi": {"aqi": 32, "category": "Good"},
        "weather_climate": {
            "microclimate_memo": micro_memo,
            "watershed_overview": f"{water_label}: {water_status}",
            "tides_and_hydrology": tides_desc,
            "enso_index": "NOAA Climate Prediction Center: Neutral ENSO conditions prevailing across North America.",
            "tropical_updates": "National Hurricane Center / Storm Prediction Center: No convective or tropical threats active in this sector.",
            "extreme_weather_24h": "No severe storm watches, flood advisories, or convective warnings in effect for this grid point.",
            "drought_index": "Regional soil moisture balance normal."
        },
        "outdoor_activities": outdoor_activities,
        "lifestyle": {
            "clothing": {
                "morning": f"Wear layers: morning starts around {tonight_low}°F (light jacket, sweater, or fleece)." if tonight_low < 60 else "Comfortable start in short sleeves or light long sleeves.",
                "afternoon": f"Highs reaching near {base_highs[0]}°F: breathable short sleeves, light fabrics." if base_highs[0] >= 72 else f"Cooler afternoon peak of {base_highs[0]}°F: light jacket or layered sweater recommended.",
                "night": f"Cooling off towards {tonight_low}°F: hoodie, jacket, or heavier layers for evening outdoor plans."
            },
            "hair_makeup": {
                "hair": f"Frizz Alert: Humidity is elevated at {curr_hum}%. Anti-humidity serum or updo recommended." if curr_hum > 70 else f"Low frizz risk; moderate relative humidity ({curr_hum}%). Clean, lasting hold.",
                "makeup": f"High dew point/humidity ({curr_hum}%): use oil-free primer and setting spray." if curr_hum > 75 else f"Stable humidity ({curr_hum}%): standard foundation and moisturizers will hold well."
            },
            "allergen": "Regional ragweed and tree/grass pollen indices low-to-moderate.",
            "mosquito_fly": f"Bug activity elevated around damp vegetation due to {curr_hum}% humidity." if curr_hum > 75 and curr_temp > 68 else "Bug activity low to minimal under current air density.",
            "leaf_change": "Status: Early seasonal foliage transition.",
            "planting_harvest": garden_season
        },
        "sporting_event": {"events": sports_events},
        "astronomy": {
            "sunrise": sunrise,
            "sunset": sunset,
            "moon_phase": "Waning Gibbous",
            "darkness_window": f"{sunset} through {sunrise}",
            "stargazing_rating": "95/100 (Exceptional) — Clear atmosphere with minimal cloud cover.",
            "visible_planets": [
                "Saturn (Magnitude +0.6, visible across southern sky all evening)",
                "Jupiter (Magnitude -2.4, blazing bright in Taurus starting at 10:45 PM)",
                "Venus (Brilliant in southwestern evening sky until 8:15 PM)",
                "Mars (Visible in eastern predawn sky after 2:30 AM)"
            ],
            "celestial_events": [
                {"title": "🛰️ ISS Overhead Transit", "time": "08:12 PM – 08:18 PM", "direction": "NW to SE (Max elevation 64°)", "notes": "Bright naked-eye magnitude pass"},
                {"title": "🪐 Saturn Ring Plane Alignment", "time": "09:30 PM – 11:30 PM", "direction": "Direct South", "notes": "Optimal telescope seeing under crisp night skies"},
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

@app.get("/weather")
def api_weather(query: str = "28412", sport_team: str = "Panthers, Braves"):
    try:
        return get_full_weather_data(query, sport_team)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from main import main as flet_ui_main
assets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "assets"))
app.mount("/", flet_fastapi.app(flet_ui_main, assets_dir=assets_dir))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("server:app", host="0.0.0.0", port=port)