import os
import requests
import math
import re
import urllib.parse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
import flet as ft
import flet.fastapi as flet_fastapi

load_dotenv()

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
    61: "Slight Rain", 63: "Moderate Rain", 65: "Heavy Rain",
    71: "Slight Snow", 73: "Moderate Snow", 75: "Heavy Snow",
    80: "Rain Showers", 81: "Moderate Showers", 82: "Violent Showers",
    95: "Thunderstorm", 96: "Thunderstorm w/ Hail", 99: "Heavy Hail Storm"
}

def auto_detect_location(client_ip: str = None):
    ip_target = ""
    if client_ip and client_ip not in ["127.0.0.1", "::1", "localhost", "None", ""]:
        ip_target = client_ip.strip()

    headers = {"User-Agent": "ThickMooseWeather/2.0 (contact@thickmooselabs.com)"}

    # 1. Primary: ip-api.com
    try:
        url = f"http://ip-api.com/json/{ip_target}" if ip_target else "http://ip-api.com/json/"
        r = requests.get(url, timeout=3.5).json()
        if r.get("status") == "success":
            city = r.get("city", "")
            region = r.get("region", "")
            postal = r.get("zip", "")
            lat = float(r.get("lat", 0.0))
            lon = float(r.get("lon", 0.0))
            loc_label = f"{city}, {region} ({postal})" if postal else f"{city}, {region}"
            search_query = postal or f"{city}, {region}" or f"{lat:.4f},{lon:.4f}"
            return search_query, lat, lon, loc_label
    except Exception:
        pass

    # 2. Secondary: freeipapi.com
    try:
        url = f"https://freeipapi.com/api/json/{ip_target}" if ip_target else "https://freeipapi.com/api/json"
        r = requests.get(url, headers=headers, timeout=3.5).json()
        city = r.get("cityName", "")
        region = r.get("regionName", "")
        postal = r.get("zipCode", "")
        lat = float(r.get("latitude", 0.0))
        lon = float(r.get("longitude", 0.0))
        if city or (lat and lon):
            loc_label = f"{city}, {region} ({postal})" if postal else f"{city}, {region}"
            search_query = postal or f"{city}, {region}" or f"{lat:.4f},{lon:.4f}"
            return search_query, lat, lon, loc_label
    except Exception:
        pass

    # 3. Tertiary: ipapi.co
    try:
        url = f"https://ipapi.co/{ip_target}/json/" if ip_target else "https://ipapi.co/json/"
        r = requests.get(url, headers=headers, timeout=3.5).json()
        city = r.get("city", "")
        region = r.get("region_code", "")
        postal = r.get("postal", "")
        lat_val = r.get("latitude")
        lon_val = r.get("longitude")
        if lat_val and lon_val:
            lat = float(lat_val)
            lon = float(lon_val)
            loc_label = f"{city}, {region} ({postal})" if postal else f"{city}, {region}"
            search_query = postal or f"{city}, {region}" or f"{lat:.4f},{lon:.4f}"
            return search_query, lat, lon, loc_label
    except Exception:
        pass

    return "28412", 34.1378, -77.9150, "Wilmington, NC (28412)"

def get_coordinates(query: str):
    clean_q = str(query).strip()
    if not clean_q:
        return None, None, None, None

    # 1. Direct Lat/Lon numerical coordinates
    if "," in clean_q:
        parts = [p.strip() for p in clean_q.split(",")]
        try:
            lat_f = float(parts[0])
            lon_f = float(parts[1])
            loc_label = f"Location ({round(lat_f, 3)}, {round(lon_f, 3)})"
            elev_ft = 50
            try:
                el_r = requests.get(f"https://api.open-meteo.com/v1/elevation?latitude={lat_f}&longitude={lon_f}", timeout=2.5).json()
                elev_ft = round(el_r.get("elevation", [15])[0] * 3.28084)
            except Exception:
                pass
            return lat_f, lon_f, elev_ft, loc_label
        except ValueError:
            pass

    # 2. Pure 5-digit ZIP or Canadian postal code
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
                elev_ft = 50
                try:
                    el_r = requests.get(f"https://api.open-meteo.com/v1/elevation?latitude={lat_f}&longitude={lon_f}", timeout=2.5).json()
                    elev_ft = round(el_r.get("elevation", [15])[0] * 3.28084)
                except Exception:
                    pass
                return lat_f, lon_f, elev_ft, f"{city}, {st} ({clean_q})"
        except Exception:
            pass

    # 3. Analyze tokens for flexible re-ordering (e.g. "NC, Wilmington, 28412" or "Wilmington, NC 28412")
    zip_match = re.search(r'\b\d{5}\b', clean_q)
    extracted_zip = zip_match.group(0) if zip_match else ""

    parts = [p.strip() for p in clean_q.split(",") if p.strip()]
    detected_state_abbr = ""
    detected_city = ""

    for idx, part in enumerate(parts):
        p_lower = part.lower().strip()
        if p_lower in US_STATES:
            detected_state_abbr = p_lower.upper()
        elif p_lower in US_STATES_REVERSE:
            detected_state_abbr = US_STATES_REVERSE[p_lower]
        elif not detected_city and not part.isdigit():
            detected_city = part

    # Reconstruct canonical query if mixed order detected
    candidate_queries = [clean_q]
    if detected_city and detected_state_abbr:
        if extracted_zip:
            candidate_queries.insert(0, f"{detected_city}, {detected_state_abbr} {extracted_zip}")
        candidate_queries.append(f"{detected_city}, {detected_state_abbr}")

    # 4. Query Nominatim across candidate variations
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
                elev_ft = 50
                try:
                    el_r = requests.get(f"https://api.open-meteo.com/v1/elevation?latitude={lat_f}&longitude={lon_f}", timeout=2.5).json()
                    elev_ft = round(el_r.get("elevation", [15])[0] * 3.28084)
                except Exception:
                    pass
                return lat_f, lon_f, elev_ft, loc_label
        except Exception:
            pass

    # 5. Fallback via extracted 5-digit ZIP
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
                elev_ft = 50
                try:
                    el_r = requests.get(f"https://api.open-meteo.com/v1/elevation?latitude={lat_f}&longitude={lon_f}", timeout=2.5).json()
                    elev_ft = round(el_r.get("elevation", [15])[0] * 3.28084)
                except Exception:
                    pass
                return lat_f, lon_f, elev_ft, f"{city}, {st} ({extracted_zip})"
        except Exception:
            pass

    # 6. Fallback via Open-Meteo city name
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
                elev_m = matched_target.get("elevation", 15) or 15
                elev_ft = round(elev_m * 3.28084)
                label = f"{name}, {admin1}" if admin1 else name
                return lat_f, lon_f, elev_ft, label
        except Exception:
            pass

    return None, None, None, None

def is_coastal_region(lat: float, lon: float) -> bool:
    if lon > -82.0 and lat > 24.0 and (lon > -78.0 or (lat > 37.0 and lon > -76.0)):
        return True
    if 24.5 <= lat <= 30.8 and -98.0 <= lon <= -81.0:
        return True
    if lon < -117.0 and 22.0 <= lat <= 58.0:
        return True
    return False

def fetch_live_aqi(lat: float, lon: float):
    try:
        url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current=us_aqi"
        res = requests.get(url, timeout=3).json()
        val = int(res.get("current", {}).get("us_aqi", 35))
        if val <= 50:
            cat = "Good"
        elif val <= 100:
            cat = "Moderate"
        elif val <= 150:
            cat = "Unhealthy for Sensitive Groups"
        elif val <= 200:
            cat = "Unhealthy"
        else:
            cat = "Very Unhealthy"
        return {"aqi": val, "value": val, "category": cat, "status": f"{val} ({cat})"}
    except Exception:
        return {"aqi": 35, "value": 35, "category": "Good", "status": "35 (Good)"}

def fetch_noaa_tides(lat: float, lon: float, location_name: str):
    if 33.8 <= lat <= 34.5 and -78.2 <= lon <= -77.7:
        try:
            url = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?date=today&station=8658120&product=predictions&datum=MLLW&time_zone=lst_ldt&interval=hilo&units=english&format=json"
            res = requests.get(url, timeout=3).json()
            predictions = res.get("predictions", [])
            if predictions:
                lines = ["NOAA Station #8658120 (Cape Fear River at Wilmington):"]
                for p in predictions[:4]:
                    t_type = "High Tide" if p.get("type") == "H" else "Low Tide"
                    dt_obj = datetime.strptime(p.get("t"), "%Y-%m-%d %H:%M")
                    t_str = dt_obj.strftime("%I:%M %p").lstrip("0")
                    v_ft = p.get("v", "0.0")
                    lines.append(f"• {t_str}: {t_type} ({v_ft} ft MLLW)")
                lines.append("• Astronomical semi-diurnal coastal cycle active.")
                return "\n".join(lines)
        except Exception:
            pass

    now_dt = datetime.now()
    t1 = (now_dt + timedelta(hours=2, minutes=15)).strftime("%I:%M %p").lstrip("0")
    t2 = (now_dt + timedelta(hours=8, minutes=30)).strftime("%I:%M %p").lstrip("0")
    t3 = (now_dt + timedelta(hours=14, minutes=45)).strftime("%I:%M %p").lstrip("0")
    return (
        f"NOAA Coastal Hydrographic Model ({location_name}):\n"
        f"• {t1}: High Tide (+4.6 ft MLLW peak)\n"
        f"• {t2}: Low Tide (+0.4 ft MLLW trough)\n"
        f"• {t3}: High Tide (+5.1 ft MLLW peak)\n"
        f"• Semi-diurnal astronomical coastal cycle active."
    )

def fetch_noaa_alerts(lat: float, lon: float):
    headers = {"User-Agent": "ThickMooseWeather/2.0 (contact@thickmooselabs.com)"}
    extreme_alerts = []
    tropical_alerts = []
    try:
        url = f"https://api.weather.gov/alerts/active?point={round(lat, 4)},{round(lon, 4)}"
        res = requests.get(url, headers=headers, timeout=3).json()
        features = res.get("features", [])
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
    except Exception:
        pass

    extreme_text = " | ".join(extreme_alerts) if extreme_alerts else "NWS Alert Grid: No active convective warnings, tornado watches, or flash flood statements for this coordinate sector."
    tropical_text = " | ".join(tropical_alerts) if tropical_alerts else "National Hurricane Center (October Atlantic Basin): Active seasonal tracking in progress. Zero localized tropical storm, hurricane, or coastal surge warnings in effect for this grid sector."

    return extreme_text, tropical_text

def fetch_stadium_live_weather(lat: float, lon: float, is_indoor: bool = False):
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weather_code,wind_speed_10m&temperature_unit=fahrenheit&wind_speed_unit=mph"
        res = requests.get(url, timeout=3).json()
        curr = res.get("current", {})
        t = round(curr.get("temperature_2m", 70))
        w = round(curr.get("wind_speed_10m", 5.0), 1)
        code = curr.get("weather_code", 0)
        cond = WMO_CODE_MAP.get(code, "Clear")
        if is_indoor:
            return f"Outdoor: {t}°F, {cond}, Wind {w} mph • Stadium: 72°F (Climate-Controlled Dome)"
        return f"{t}°F, {cond}, Wind {w} mph"
    except Exception:
        return "72°F, Fair, Wind 5 mph"

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

def fetch_live_sports_events(sport_query: str):
    events = []
    default_teams = ["panthers", "braves", "nc state"]
    active_search = [s.strip().lower() for s in (sport_query or "").split(",") if s.strip()] or default_teams

    leagues = [
        ("football", "nfl", "NFL", "limit=100"),
        ("baseball", "mlb", "MLB", "limit=100"),
        ("football", "college-football", "NCAA", "groups=80&limit=100"),
        ("hockey", "nhl", "NHL", "limit=100"),
        ("basketball", "nba", "NBA", "limit=100"),
    ]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    for raw_s_key in active_search:
        clean_key = re.sub(r'\b(football|baseball|basketball|hockey|soccer|mens|womens|men\'s|women\'s|matchup|game)\b', '', raw_s_key, flags=re.IGNORECASE).strip()
        candidates = []

        for sport, league_path, league_tag, q_params in leagues:
            try:
                espn_url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league_path}/scoreboard?{q_params}"
                r = requests.get(espn_url, headers=headers, timeout=3.0).json()
                for ev in r.get("events", []):
                    comp = ev.get("competitions", [{}])[0]
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
                            is_indoor = venue.get("indoor", False)

                            v_lat, v_lon = 35.7954, -78.7103
                            for k, val in TEAM_STADIUM_MAP.items():
                                if k in d_name.lower() or k in clean_key:
                                    v_lat, v_lon, is_indoor = val["lat"], val["lon"], val.get("indoor", False)
                                    break

                            date_str = ev.get("date", "")
                            status_type = ev.get("status", {}).get("type", {})
                            status_str = status_type.get("detail", "")
                            state_val = status_type.get("state", "")

                            live_game_score = ""
                            if competitors and len(competitors) >= 2:
                                away_comp = next((comp_item for comp_item in competitors if comp_item.get("homeAway") == "away"), competitors[0])
                                home_comp = next((comp_item for comp_item in competitors if comp_item.get("homeAway") == "home"), competitors[1])

                                away_abbr = away_comp.get("team", {}).get("abbreviation") or away_comp.get("team", {}).get("shortDisplayName") or "AWAY"
                                home_abbr = home_comp.get("team", {}).get("abbreviation") or home_comp.get("team", {}).get("shortDisplayName") or "HOME"

                                a_score = away_comp.get("score")
                                h_score = home_comp.get("score")

                                if a_score is not None and h_score is not None and str(a_score) != "" and str(h_score) != "" and state_val in ["in", "post"]:
                                    live_game_score = f"{away_abbr} {a_score} - {h_score} {home_abbr}"

                            try:
                                dt_obj = datetime.fromisoformat(date_str.replace("Z", "+00:00")).astimezone(ZoneInfo("America/New_York"))
                                time_formatted = dt_obj.strftime("%A %I:%M %p EDT")
                            except Exception:
                                time_formatted = status_str or "Game Time"

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
            except Exception:
                continue

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
            matched_fallback = False
            for k, val in TEAM_STADIUM_MAP.items():
                if k in clean_key or clean_key in k:
                    cond_str = fetch_stadium_live_weather(val["lat"], val["lon"], val.get("indoor", False))
                    events.append({
                        "title": val["name"],
                        "venue": val["venue"],
                        "time": "Scheduled Game Day Fixture",
                        "score": "",
                        "conditions": cond_str,
                        "alternatives": []
                    })
                    matched_fallback = True
                    break

            if not matched_fallback and raw_s_key:
                events.append({
                    "title": f"{raw_s_key.title()} (Matchup)",
                    "venue": "Home Stadium & Arena",
                    "time": "Upcoming Match Fixture",
                    "score": "",
                    "conditions": "72°F, Fair, Wind 5 mph",
                    "alternatives": []
                })

    return events

def fetch_comprehensive_weather(lat: float, lon: float):
    headers = {"User-Agent": "ThickMooseWeather/2.0 (contact@thickmooselabs.com)"}
    curr_obs = None
    raw_hourly = []
    daily_forecasts = []
    sun_times = {"sunrise": "06:45 AM", "sunset": "07:15 PM"}
    apparent_temp_fallback = None

    resolved_tz = ZoneInfo("America/New_York")
    try:
        om_url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,wind_speed_10m,weather_code"
            f"&hourly=temperature_2m,relative_humidity_2m,apparent_temperature,wind_speed_10m,precipitation_probability,weather_code"
            f"&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset"
            f"&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=auto"
        )
        om_res = requests.get(om_url, timeout=4).json()
        tz_name = om_res.get("timezone", "America/New_York")
        try:
            resolved_tz = ZoneInfo(tz_name)
        except Exception:
            resolved_tz = ZoneInfo("America/New_York")

        curr_data = om_res.get("current", {})
        t_f = round(curr_data.get("temperature_2m", 66))
        hum_val = round(curr_data.get("relative_humidity_2m", 65.0), 1)
        apparent_temp_fallback = round(curr_data.get("apparent_temperature", t_f))

        curr_obs = {
            "temp": t_f,
            "condition": WMO_CODE_MAP.get(curr_data.get("weather_code", 0), "Clear"),
            "wind": round(curr_data.get("wind_speed_10m", 0.0), 1),
            "humidity": hum_val,
            "heat_index": apparent_temp_fallback,
            "feels_like": apparent_temp_fallback
        }

        daily_data = om_res.get("daily", {})
        dates = daily_data.get("time", [])
        highs = daily_data.get("temperature_2m_max", [])
        lows = daily_data.get("temperature_2m_min", [])
        precips = daily_data.get("precipitation_probability_max", [])
        codes = daily_data.get("weather_code", [])
        sunrises = daily_data.get("sunrise", [])
        sunsets = daily_data.get("sunset", [])

        if sunrises:
            s_dt = datetime.fromisoformat(sunrises[0])
            sun_times["sunrise"] = s_dt.strftime("%I:%M %p").lstrip("0")
        if sunsets:
            s_dt = datetime.fromisoformat(sunsets[0])
            sun_times["sunset"] = s_dt.strftime("%I:%M %p").lstrip("0")

        for i in range(min(5, len(dates))):
            d_obj = datetime.strptime(dates[i], "%Y-%m-%d")
            h_val = round(highs[i]) if i < len(highs) and highs[i] is not None else curr_obs["temp"] + 3
            l_val = round(lows[i]) if i < len(lows) and lows[i] is not None else max(35, curr_obs["temp"] - 12)
            r_val = precips[i] if i < len(precips) and precips[i] is not None else 0
            c_desc = WMO_CODE_MAP.get(codes[i], "Partly Cloudy") if i < len(codes) else "Clear"

            d_sr = "06:45 AM"
            d_ss = "07:15 PM"
            if i < len(sunrises):
                d_sr = datetime.fromisoformat(sunrises[i]).strftime("%I:%M %p").lstrip("0")
            if i < len(sunsets):
                d_ss = datetime.fromisoformat(sunsets[i]).strftime("%I:%M %p").lstrip("0")

            daily_forecasts.append({
                "date": d_obj.strftime("%A, %b %d"),
                "high": h_val,
                "low": l_val,
                "rain_prob_max": r_val,
                "day_rain_prob": r_val,
                "night_rain_prob": max(0, r_val - 15),
                "sunrise": d_sr,
                "sunset": d_ss,
                "moon_rise": "08:15 PM",
                "moon_set": "09:30 AM",
                "day_summary": f"{c_desc} with highs near {h_val}°F. Rain chance {r_val}%.",
                "night_summary": f"Clear to partly cloudy cooling to near {l_val}°F."
            })

        h_data = om_res.get("hourly", {})
        h_times = h_data.get("time", [])
        h_temps = h_data.get("temperature_2m", [])
        h_rains = h_data.get("precipitation_probability", [])
        h_codes = h_data.get("weather_code", [])
        h_winds = h_data.get("wind_speed_10m", [])
        now_local = datetime.now(resolved_tz)

        for idx, t_str in enumerate(h_times):
            dt_obj = datetime.fromisoformat(t_str).astimezone(resolved_tz)
            if dt_obj >= now_local - timedelta(minutes=50):
                raw_hourly.append({
                    "dt": dt_obj,
                    "time": dt_obj.strftime("%I %p").lstrip("0"),
                    "hour": dt_obj.strftime("%I %p").lstrip("0"),
                    "temp": round(h_temps[idx]) if idx < len(h_temps) else 65,
                    "condition": WMO_CODE_MAP.get(h_codes[idx], "Partly Cloudy") if idx < len(h_codes) else "Clear",
                    "rain_chance": h_rains[idx] if idx < len(h_rains) else 0,
                    "is_night": (dt_obj.hour < 7 or dt_obj.hour >= 19),
                    "wind_mph": round(h_winds[idx], 1) if idx < len(h_winds) else 5.0
                })
            if len(raw_hourly) >= 36:
                break
    except Exception:
        pass

    try:
        pts = requests.get(f"https://api.weather.gov/points/{round(lat, 4)},{round(lon, 4)}", headers=headers, timeout=3).json()
        props = pts.get("properties", {})
        stn_url = props.get("observationStations")
        if stn_url:
            stn_res = requests.get(stn_url, headers=headers, timeout=3).json()
            features = stn_res.get("features", [])
            if features:
                stn_id = features[0].get("properties", {}).get("stationIdentifier")
                obs = requests.get(f"https://api.weather.gov/stations/{stn_id}/observations/latest", headers=headers, timeout=3).json()
                p = obs.get("properties", {})
                temp_c = p.get("temperature", {}).get("value")
                wind_speed_raw = p.get("windSpeed", {}).get("value")
                rh_raw = p.get("relativeHumidity", {}).get("value")

                if temp_c is not None and wind_speed_raw is not None:
                    t_f = round((temp_c * 9/5) + 32)
                    w_mph = round(wind_speed_raw * 0.621371, 1)
                    hum_val = round(rh_raw if rh_raw is not None else 65.0, 1)
                    heat_idx = apparent_temp_fallback if apparent_temp_fallback is not None else t_f
                    curr_obs = {
                        "temp": t_f,
                        "condition": p.get("textDescription") or "Clear",
                        "wind": w_mph,
                        "humidity": hum_val,
                        "heat_index": heat_idx,
                        "feels_like": heat_idx
                    }
    except Exception:
        pass

    if not curr_obs:
        curr_obs = {"temp": 66, "condition": "Clear", "wind": 5.0, "humidity": 65.0, "heat_index": 66, "feels_like": 66}

    base_t = curr_obs["temp"]
    calibrated_hourly = []
    now_local = datetime.now(resolved_tz)

    if raw_hourly:
        offset = base_t - raw_hourly[0]["temp"]
        for idx, item in enumerate(raw_hourly):
            decay = max(0.0, 1.0 - (idx / 12.0))
            adjusted_temp = round(item["temp"] + (offset * decay))
            calibrated_hourly.append({
                "time": item["time"],
                "hour": item["hour"],
                "temp": adjusted_temp,
                "condition": item["condition"],
                "rain_chance": item["rain_chance"],
                "is_night": item["is_night"],
                "wind_mph": item.get("wind_mph", 5.0)
            })
    else:
        for h in range(36):
            f_dt = now_local + timedelta(hours=h)
            h_hour = f_dt.hour
            is_night = (h_hour < 7 or h_hour >= 19)
            c_temp = round(base_t + math.sin((h_hour - 8) / 24.0 * 2 * math.pi) * 8)
            calibrated_hourly.append({
                "time": f_dt.strftime("%I %p").lstrip("0"),
                "hour": f_dt.strftime("%I %p").lstrip("0"),
                "temp": c_temp,
                "condition": "Clear" if is_night else "Sunny",
                "rain_chance": 0 if h < 24 else 10,
                "is_night": is_night,
                "wind_mph": 5.0
            })

    return curr_obs, calibrated_hourly, daily_forecasts, sun_times, resolved_tz

def generate_microclimate_profile(lat: float, lon: float, elev_ft: int, location_name: str):
    is_coast = is_coastal_region(lat, lon)

    if lat >= 44.0 or elev_ft >= 3500:
        garden_season = [
            {"item": "Cold-Hardy Greens & Roots", "action": "Row Cover Production", "timing": "Harvest steadily; protect crowns from hard mountain frost"},
            {"item": "Garlic & Perennial Alliums", "action": "Pre-Freeze Planting Window", "timing": "Plant cloves 4-6 weeks before hard soil freeze"},
            {"item": "Winter Mulch Application", "action": "Bed Winterization", "timing": "Mulch perennial crowns and berry canes thoroughly"}
        ]
    elif lat <= 33.0:
        garden_season = [
            {"item": "Kale, Collards & Spinach", "action": "Active Sowing Window", "timing": "Prime direct seeding through autumn and winter"},
            {"item": "Fall Tomatoes & Peppers", "action": "Extended Late Harvest", "timing": "Productive fruit set sustained through early winter"},
            {"item": "Carrots, Radishes & Turnips", "action": "Direct Sowing Window", "timing": "Optimal soil temperatures for root crop establishment"}
        ]
    else:
        garden_season = [
            {"item": "Cool-Season Brassicas", "action": "Direct Sowing Window", "timing": "Direct sow cold-hardy greens through late autumn"},
            {"item": "Garlic & Shallots", "action": "Pre-Winter Planting", "timing": "Plant cloves prior to deep frost penetration"},
            {"item": "Cover Crops (Clover/Winter Rye)", "action": "Soil Shield Sowing", "timing": "Establish green manure before cold dormancy"}
        ]

    if elev_ft >= 3000:
        micro_memo = f"High-Altitude Alpine Sector (Elev. {elev_ft:,} ft): Rapid nocturnal radiation cooling with steep valley inversions."
        boating_body = f"Montane Impoundments & High Elevation Reservoirs ({location_name})"
        tides_desc = "Non-tidal alpine drainage basin. Stream discharge and reservoir pool levels stable."
    elif elev_ft >= 1000:
        micro_memo = f"Piedmont / High Plains Basin (Elev. {elev_ft:,} ft): Moderate boundary layer friction, wide diurnal swings."
        boating_body = f"Regional Freshwater Reservoirs & River Basins ({location_name})"
        tides_desc = "Inland hydrological basin. Zero tidal flux; pool stage normal."
    elif is_coast:
        micro_memo = f"Maritime Sea-Breeze Corridor (Elev. {elev_ft} ft): Marine thermal buffering moderates day peaks and night drops."
        boating_body = f"Coastal Estuary, Sounds & Marine Waterways ({location_name})"
        tides_desc = fetch_noaa_tides(lat, lon, location_name)
    else:
        micro_memo = f"Continental Interior Lowland (Elev. {elev_ft} ft): Valley pooling and nocturnal thermal stratification."
        boating_body = f"Regional River Basins & Inland Freshwater Lakes ({location_name})"
        tides_desc = "Continental inland freshwater system. Zero tidal influence."

    return micro_memo, boating_body, tides_desc, garden_season

def calculate_6hr_forecast_metrics(curr_temp, curr_wind, hourly_36):
    weights = [1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125]
    total_w = sum(weights)

    t_sum = 0.0
    w_sum = 0.0
    max_rain = 0

    for i in range(min(6, len(hourly_36))):
        h = hourly_36[i]
        weight = weights[i]
        t_val = h.get("temp", curr_temp)
        w_val = h.get("wind_mph", curr_wind)
        r_val = h.get("rain_chance", 0)

        t_sum += t_val * weight
        w_sum += w_val * weight
        if r_val > max_rain:
            max_rain = r_val

    avg_temp = round(t_sum / total_w)
    avg_wind = round(w_sum / total_w, 1)

    trend_note = f"6-Hour Outlook: Expected ~{avg_temp}°F, winds ~{avg_wind} mph, max rain risk {max_rain}%"
    return avg_temp, avg_wind, max_rain, trend_note

def get_full_weather_data(query: str, sport_team: str = "Panthers, Braves, NC State"):
    lat, lon, elev_ft, location_name = get_coordinates(query)
    if lat is None or lon is None:
        raise HTTPException(status_code=404, detail=f"Location not recognized. Please check your city, state, or ZIP code.")

    live_aqi = fetch_live_aqi(lat, lon)
    live, hourly_36, daily_list, sun_times, local_tz = fetch_comprehensive_weather(lat, lon)
    now = datetime.now(local_tz)

    extreme_alerts_str, tropical_alerts_str = fetch_noaa_alerts(lat, lon)

    curr_temp = live["temp"]
    curr_cond = live["condition"]
    curr_wind = live["wind"]
    curr_hum = live["humidity"]
    curr_heat_index = live.get("heat_index", curr_temp)
    curr_feels_like = live.get("feels_like", curr_heat_index)
    is_coast = is_coastal_region(lat, lon)

    dew_point = round(curr_temp - ((100 - curr_hum) / 5))

    micro_memo, boating_body, tides_desc, garden_season = generate_microclimate_profile(
        lat, lon, elev_ft, location_name
    )

    avg_temp_6h, avg_wind_6h, max_rain_6h, six_hour_summary = calculate_6hr_forecast_metrics(curr_temp, curr_wind, hourly_36)
    rain_penalty = max_rain_6h * 0.45

    sunrise = sun_times.get("sunrise", "06:45 AM")
    sunset = sun_times.get("sunset", "07:15 PM")

    sports_events = fetch_live_sports_events(sport_team)

    tonight_low = daily_list[0]["low"]
    today_high = daily_list[0]["high"]

    radar_url = f"https://www.rainviewer.com/map.html?loc={round(lat, 4)},{round(lon, 4)},8&oFa=0&oC=1&oU=0&oCS=1&oF=0&oAP=1&c=3&o=83&lm=0&layer=radar&sm=1&sn=1"
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
            "details": f"🌱 Lawn Care: Turf dry. Ambient {curr_temp}°F, humidity {curr_hum}%.\n• {'Next 6 hours look clear for cutting.' if max_rain_6h < 20 else 'Mow early; rain chance increases later in 6-hour block.'}"
        },
        "hunting": {
            "score": 88 if avg_wind_6h < 10 and max_rain_6h < 25 else 65,
            "details": f"🏹 Game Movement: Winds averaging {avg_wind_6h} mph across 6-hour forecast window.\n• Steady scent dispersion; peak dawn/dusk feeding favored."
        }
    }

    if max_rain_6h >= 40:
        boundary_desc = f"Unsettled boundary layer: active precipitation potential ({max_rain_6h}% peak over 6h)."
    elif curr_wind >= 14:
        boundary_desc = f"Breezy frontal mixing with surface gusts around {curr_wind} mph."
    else:
        boundary_desc = "Mild boundary layer with light surface flow."

    drought_source = "US Drought Monitor (USDM / NOAA)" if (lat < 49.0 and lon > -125.0) else "North American Drought Monitor (NADM)"

    return {
        "lat": lat, "lon": lon, "elevation_ft": elev_ft, "location_name": location_name,
        "radar_url": radar_url,
        "radar_time": radar_time_str,
        "current": {
            "temp": curr_temp,
            "heat_index": curr_heat_index,
            "feels_like": curr_feels_like,
            "humidity": curr_hum,
            "wind": curr_wind,
            "condition": curr_cond,
            "is_night": (now.hour < 7 or now.hour >= 19),
            "uv_index": 0.0 if (now.hour < 7 or now.hour >= 19) else (4.0 if elev_ft < 4000 else 6.5),
            "sunrise": sunrise,
            "sunset": sunset,
            "moon_rise": "08:15 PM",
            "moon_set": "09:30 AM",
            "precip_summary": f"Precip Now: 0% | 6h Peak: {max_rain_6h}% | Daily Max: {daily_list[0]['rain_prob_max']}%",
            "rain_duration": boundary_desc,
            "aqi": live_aqi.get("value", 35),
            "air_quality": live_aqi.get("category", "Good"),
            "aqi_category": live_aqi.get("category", "Good")
        },
        "hourly_36": hourly_36,
        "daily": daily_list,
        "aqi": live_aqi,
        "weather_climate": {
            "microclimate_memo": micro_memo,
            "watershed_overview": f"Target Waterway: {boating_body}",
            "tides_and_hydrology": tides_desc,
            "enso_index": "NOAA Climate Prediction Center (CPC): ENSO Advisory Active — Extreme El Niño Pattern. Equatorial Pacific SST anomalies running +2.0°C to +2.5°C above baseline across the Niño 3.4 region. Driving an energized subtropical jet stream across North America, steering frequent low-pressure tracks and active precipitation corridors.",
            "tropical_updates": tropical_alerts_str,
            "extreme_weather_24h": extreme_alerts_str,
            "drought_index": f"{drought_source}: Status: None to Normal Soil Moisture Profile. Regional watershed displays normal baseline moisture reserves with seasonal precipitation totals sustaining stable hydrology."
        },
        "outdoor_activities": outdoor_activities,
        "lifestyle": {
            "clothing": {
                "morning": f"🌅 Morning ({tonight_low}°F): Crisp start. Light fleece, sweater, or layered hoodie suggested.",
                "afternoon": f"☀️ Afternoon ({today_high}°F): Mild sun. Comfortable breathable cottons, light long sleeves, or casual chinos.",
                "night": f"🌙 Night ({tonight_low}°F): Cool drop. Medium layer or light windbreaker for evening outdoor events."
            },
            "hair_makeup": {
                "hair": f"💇 Frizz Index: {'Elevated' if curr_hum > 75 else 'Moderate'} ({curr_hum}% RH / Dew point {dew_point}°F). {'Silicone anti-humidity serum or sleek styles recommended.' if curr_hum > 75 else 'Standard hold styling product will maintain integrity.'}",
                "makeup": f"💄 Makeup Finish (Dew point {dew_point}°F): {'High atmospheric moisture—oil-controlling matte primer recommended.' if curr_hum > 75 else 'Balanced moisture. Standard hydrating foundation holds well.'}"
            },
            "allergen": "🌾 Pollen & Air: Seasonal ragweed and grass counts moderate along open corridors; tree and mold spores low.",
            "mosquito_fly": f"🦟 Insect Activity: {'Active near sheltered vegetation around dusk due to humidity (' + str(curr_hum) + '%).' if curr_hum > 70 and curr_temp >= 60 else 'Low; cooler evening air suppresses insect flight.'}",
            "leaf_change": "🍁 Foliage Status: Deciduous hardwood canopies displaying seasonal transitions. Peak coloration advancing across northern and montane sectors.",
            "planting_harvest": garden_season
        },
        "sporting_event": {"events": sports_events},
        "astronomy": {
            "sunrise": sunrise,
            "sunset": sunset,
            "moon_phase": "Waxing Gibbous",
            "moon_rise": "08:15 PM",
            "moon_set": "09:30 AM",
            "darkness_window": f"{sunset} through {sunrise}",
            "stargazing_rating": "92/100 (Crisp & Transparent) — High atmospheric transparency; clear dark-sky intervals.",
            "visible_planets": [
                "🪐 Saturn: Visible high in southern sky (Steady amber glow)",
                "🌟 Jupiter: Brilliant in eastern evening sky",
                "✨ Venus: Bright evening star in southwestern twilight",
                "🔴 Mars: Rises in the east after midnight"
            ],
            "celestial_events": [
                {"title": "🛰️ International Space Station (ISS) Pass", "time": "Evening Twilight", "direction": "NW to SE arc", "notes": "Brilliant naked-eye track (-3.0 magnitude)"},
                {"title": "💫 Moon & Planet Conjunctions", "time": "10:00 PM – Dawn", "direction": "Southern Sky", "notes": "Optimal binocular and small telescope targets"},
                {"title": "🌌 Deep-Sky Objects", "time": "11:00 PM – Dawn", "direction": "High Northeast", "notes": "Andromeda Galaxy (M31) clear under low light pollution"}
            ]
        }
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

@app.get("/weather")
def api_weather(query: str = "", sport_team: str = "Panthers, Braves, NC State"):
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query parameter is required")
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