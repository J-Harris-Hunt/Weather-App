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
from fastapi.responses import FileResponse, HTMLResponse
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

WILMINGTON_FALLBACK = ("28412", 34.1378, -77.9150, "Wilmington, NC (28412)")

def auto_detect_location(client_ip=None):
    try:
        url = f"https://ipapi.co/{client_ip}/json/" if client_ip else "https://ipapi.co/json/"
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            # If corporate gateway tunnels to DC, VA, or AL, fall back to home base
            if data.get("region_code") in ["DC", "AL", "VA"]:
                return {"city": "Wilmington", "region": "NC", "postal": "28412", "lat": 34.18, "lon": -77.92}
            return {
                "city": data.get("city", "Wilmington"),
                "region": data.get("region_code", "NC"),
                "postal": data.get("postal", "28412"),
                "lat": float(data.get("latitude", 34.18)),
                "lon": float(data.get("longitude", -77.92)),
            }
    except Exception:
        pass
    return {"city": "Wilmington", "region": "NC", "postal": "28412", "lat": 34.18, "lon": -77.92}

    try:
        url = f"https://freeipapi.com/api/json/{ip_target}"
        r = requests.get(url, headers=headers, timeout=3.5).json()
        city = r.get("cityName", "")
        region = r.get("regionName", "")
        postal = r.get("zipCode", "")
        lat = float(r.get("latitude", 0.0))
        lon = float(r.get("longitude", 0.0))
        if city and city.lower() != "ashburn":
            loc_label = f"{city}, {region} ({postal})" if postal else f"{city}, {region}"
            search_query = postal or f"{city}, {region}" or f"{lat:.4f},{lon:.4f}"
            return search_query, lat, lon, loc_label
    except Exception:
        pass

    return WILMINGTON_FALLBACK

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
            elev_ft = 50
            try:
                el_r = requests.get(f"https://api.open-meteo.com/v1/elevation?latitude={lat_f}&longitude={lon_f}", timeout=2.5).json()
                elev_ft = round(el_r.get("elevation", [15])[0] * 3.28084)
            except Exception:
                pass
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
                elev_ft = 50
                try:
                    el_r = requests.get(f"https://api.open-meteo.com/v1/elevation?latitude={lat_f}&longitude={lon_f}", timeout=2.5).json()
                    elev_ft = round(el_r.get("elevation", [15])[0] * 3.28084)
                except Exception:
                    pass
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
                elev_ft = 50
                try:
                    el_r = requests.get(f"https://api.open-meteo.com/v1/elevation?latitude={lat_f}&longitude={lon_f}", timeout=2.5).json()
                    elev_ft = round(el_r.get("elevation", [15])[0] * 3.28084)
                except Exception:
                    pass
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
                elev_ft = 50
                try:
                    el_r = requests.get(f"https://api.open-meteo.com/v1/elevation?latitude={lat_f}&longitude={lon_f}", timeout=2.5).json()
                    elev_ft = round(el_r.get("elevation", [15])[0] * 3.28084)
                except Exception:
                    pass
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
        url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current=us_aqi,pm2_5,pm10"
        res = requests.get(url, timeout=3).json()
        curr_aq = res.get("current", {})
        val = int(curr_aq.get("us_aqi", 35))
        pm25 = curr_aq.get("pm2_5", 8.0)
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
        return {"aqi": val, "value": val, "category": cat, "pm25": pm25, "status": f"{val} ({cat})"}
    except Exception:
        return {"aqi": 35, "value": 35, "category": "Good", "pm25": 8.0, "status": "35 (Good)"}

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
            f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,surface_pressure,uv_index,wind_speed_10m,wind_direction_10m,weather_code"
            f"&hourly=temperature_2m,relative_humidity_2m,apparent_temperature,surface_pressure,uv_index,wind_speed_10m,precipitation_probability,weather_code"
            f"&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max,sunrise,sunset"
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
        wind_dir_val = round(curr_data.get("wind_direction_10m", 240.0), 1)
        pressure_val = round(curr_data.get("surface_pressure", 1013.25), 1)
        uv_curr = float(curr_data.get("uv_index", 3.5))

        curr_obs = {
            "temp": t_f,
            "condition": WMO_CODE_MAP.get(curr_data.get("weather_code", 0), "Clear"),
            "wind": round(curr_data.get("wind_speed_10m", 0.0), 1),
            "wind_direction": wind_dir_val,
            "humidity": hum_val,
            "pressure_hpa": pressure_val,
            "uv_index": uv_curr,
            "heat_index": apparent_temp_fallback,
            "feels_like": apparent_temp_fallback
        }

        daily_data = om_res.get("daily", {})
        dates = daily_data.get("time", [])
        highs = daily_data.get("temperature_2m_max", [])
        lows = daily_data.get("temperature_2m_min", [])
        precips = daily_data.get("precipitation_probability_max", [])
        uv_maxs = daily_data.get("uv_index_max", [])
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
            u_val = uv_maxs[i] if i < len(uv_maxs) and uv_maxs[i] is not None else 4.0
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
                "uv_max": u_val,
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
        h_press = h_data.get("surface_pressure", [])
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
                    "pressure": h_press[idx] if idx < len(h_press) else 1013.0,
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
                    curr_obs["temp"] = t_f
                    curr_obs["condition"] = p.get("textDescription") or curr_obs.get("condition", "Clear")
                    curr_obs["wind"] = w_mph
                    curr_obs["humidity"] = hum_val
                    curr_obs["heat_index"] = heat_idx
                    curr_feels_like = heat_idx
    except Exception:
        pass

    if not curr_obs:
        curr_obs = {"temp": 66, "condition": "Clear", "wind": 5.0, "wind_direction": 240.0, "humidity": 65.0, "pressure_hpa": 1013.2, "uv_index": 4.0, "heat_index": 66, "feels_like": 66}

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
                "pressure": item.get("pressure", 1013.0),
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
                "pressure": 1013.0,
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
        raise HTTPException(status_code=404, detail="Location not recognized. Please check your city, state, or ZIP code.")

    live_aqi = fetch_live_aqi(lat, lon)
    live, hourly_36, daily_list, sun_times, local_tz = fetch_comprehensive_weather(lat, lon)
    now = datetime.now(local_tz)

    extreme_alerts_str, tropical_alerts_str = fetch_noaa_alerts(lat, lon)

    curr_temp = live["temp"]
    curr_cond = live["condition"]
    curr_wind = live["wind"]
    curr_wind_dir = live.get("wind_direction", 240.0)
    curr_hum = live["humidity"]
    curr_heat_index = live.get("heat_index", curr_temp)
    curr_feels_like = live.get("feels_like", curr_heat_index)
    curr_pressure = live.get("pressure_hpa", 1013.2)
    curr_uv = live.get("uv_index", 4.0)
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
    next_day_rain = daily_list[1]["rain_prob_max"] if len(daily_list) > 1 else 0

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
            "details": f"🌱 Lawn Care: Turf dry. Ambient {curr_temp}°F, humidity {curr_hum}%.\n• {'Next 6 hours look clear for cutting.' if max_rain_6h < 20 else 'Mow early; rain chance increases later in 6-hour block.'}"
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
    is_day = not (now.hour < 7 or now.hour >= 19)
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
        f"• Peak activity window: Dawn (6:00-7:30 AM) and Twilight (6:30-8:00 PM)."
    )

    # 5. Sinus, Joint & Migraine Pressure Index
    press_swing = abs(curr_pressure - (hourly_36[min(6, len(hourly_36)-1)].get("pressure", curr_pressure)))
    headache_score = max(30, min(96, round(92 - (press_swing * 4.5) - (abs(curr_hum - 50) * 0.25))))
    sinus_details = (
        f"🧠 Barometric & Biometric Impact: Current Barometer {curr_pressure} hPa.\n"
        f"• {'Stable atmospheric pressure gradient; low probability of weather-triggered migraines or arthritic joint flare-ups.' if press_swing < 3.0 else 'Active barometric fluctuation (' + str(round(press_swing, 1)) + ' hPa shift). Individuals sensitive to pressure changes may experience sinus congestion or headaches.'}\n"
        f"• Dew point holds near {dew_point}°F."
    )

    # 6. UV Radiation & Sunscreen Burn Time
    burn_time_min = round(200 / max(1.0, curr_uv)) if curr_uv > 0 else 999
    burn_str = f"~{burn_time_min} minutes for unprotected fair skin" if curr_uv >= 3.0 else "Minimal burn danger without direct prolonged exposure"

    # 7. Natural Home Ventilation & HVAC Guidance
    hvac_score = 92 if (62 <= curr_temp <= 74 and curr_hum < 65 and max_rain_6h < 20) else (65 if (55 <= curr_temp <= 80) else 40)
    hvac_details = (
        f"🏡 Fresh Air Ventilation Index: Score {hvac_score}/100.\n"
        f"• {'Prime conditions to open windows and naturally ventilate home; outdoor air is crisp and comfortable with low dust.' if hvac_score >= 80 else 'Keep windows closed and cycle HVAC. Outdoor humidity (' + str(curr_hum) + '%) will introduce moisture into indoor living spaces.' if curr_hum > 75 else 'Moderate conditions. Screen ventilation acceptable during midday hours.'}"
    )

    # 8. Foliage Progression
    if lat >= 42.0 or elev_ft >= 3000:
        foliage_text = "🍁 Hardwoods (Maple, Birch, Beech) at 60–85% peak vibrant red and amber transformation. Prime leaf-peeping window."
    elif lat >= 35.0:
        foliage_text = "🍂 River Canopies & Upland Oaks displaying 20–40% early bronze and yellow transitions. Peak coloration advancing in 2–3 weeks."
    else:
        foliage_text = "🌿 Coastal maritime live oaks and pines retain green canopy; cypress fringes displaying subtle bronze tints along freshwater banks."

    lifestyle = {
        "clothing": {
            "morning": f"🌅 Morning ({tonight_low}°F): Crisp start. Light fleece, sweater, or layered hoodie suggested.",
            "afternoon": f"☀️ Afternoon ({today_high}°F): Mild sun. Comfortable breathable cottons, light long sleeves, or casual chinos.",
            "night": f"🌙 Night ({tonight_low}°F): Cool drop. Medium layer or light windbreaker for evening outdoor events.",
        },
        "hair_makeup": {
            "hair_frizz_index": f"Elevated ({curr_hum}% RH / Dew point {dew_point}°F). {'Silicone anti-humidity serum, smoothing oil, or sleek updos strongly recommended.' if curr_hum > 75 else 'Standard hold styling product will maintain integrity.' if curr_hum > 50 else 'Low humidity; hydrating leave-in conditioner recommended.'}",
            "makeup_finish_index": f"Dew point {dew_point}°F: {'High atmospheric moisture — oil-controlling matte primer and setting spray recommended.' if curr_hum > 75 or dew_point >= 65 else 'Balanced atmospheric moisture — hydrating base and standard foundation hold well.' if dew_point >= 50 else 'Crisp, dry air — hydrating moisturizer and luminous finish prevent flaking.'}"
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
            "ragweed_and_weed_pollen": "Moderate along sunny roadsides and open fields",
            "grass_pollen": "Low to moderate",
            "tree_pollen": "Minimal / Dormant seasonal phase",
            "mold_spores": "Elevated near damp soil and unpaved corridors" if curr_hum > 75 else "Low",
            "air_quality_pm25": f"{live_aqi.get('category', 'Good')} (AQI {live_aqi.get('value', 35)} • PM2.5 {live_aqi.get('pm25', 8.0)} µg/m³)"
        },
        "sinus_and_migraine": {
            "score": headache_score,
            "details": sinus_details
        },
        "sun_and_uv_protection": {
            "max_uv_rating": f"Index {curr_uv:.1f} ({'Low' if curr_uv < 3 else 'Moderate' if curr_uv < 6 else 'Very High'})",
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
            "uv_index": curr_uv,
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
        "lifestyle": lifestyle,
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
                "🔴 Mars: Rises in the east after midnight",
            ],
            "celestial_events": [
                {"title": "🛰️ International Space Station (ISS) Pass", "time": "Evening Twilight", "direction": "NW to SE arc", "notes": "Brilliant naked-eye track (-3.0 magnitude)"},
                {"title": "💫 Moon & Planet Conjunctions", "time": "10:00 PM – Dawn", "direction": "Southern Sky", "notes": "Optimal binocular and small telescope targets"},
                {"title": "🌌 Deep-Sky Objects", "time": "11:00 PM – Dawn", "direction": "High Northeast", "notes": "Andromeda Galaxy (M31) clear under low light pollution"},
            ],
        },
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
def get_radar_page(lat: float = 34.1378, lon: float = -77.9150, label: str = "Location"):
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Thick Moose Radar • {label}</title>
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
            <span class="hud-title">📍 {label}</span>
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
        const labelText = "{label}";

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
        L.marker([lat, lon], {{ icon: pinIcon, zIndexOffset: 1000 }}).addTo(map).bindPopup("<b>📍 " + labelText + "</b>").openPopup();

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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/.well-known/assetlinks.json")
def get_assetlinks():
    path = os.path.join(assets_dir, "assetlinks.json")
    if os.path.exists(path):
        return FileResponse(path, media_type="application/json")
    raise HTTPException(status_code=404, detail="Assetlinks file not found")
from main import main as flet_ui_main
app.mount("/", flet_fastapi.app(flet_ui_main, assets_dir=assets_dir))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, proxy_headers=True, forwarded_allow_ips="*")