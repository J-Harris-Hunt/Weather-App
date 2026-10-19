import asyncio
import re
import inspect
import urllib.parse
import logging
import flet as ft
try:
    import flet_geolocator as ftg
except Exception:          # the app still runs (with typed locations) if the package is missing
    ftg = None
from datetime import datetime
import server

# Replace these with your live Stripe Payment Links from dashboard.stripe.com/payment-links
DONATION_LINKS = {
    "1": "https://buy.stripe.com/dRm4gBcyAfh1dw46u3g3601",
    "3": "https://buy.stripe.com/fZubJ34246KveA89Gfg3605",
    "5": "https://buy.stripe.com/dRm5kF8ik2ufbnW5pZg3606",
    "10": "https://buy.stripe.com/aFa00l0PS7ozfEc05Fg3604",
}

# ---- look & feel: one small palette, defined once ----
CARD = "#242a36"          # main card background
CARD_INNER = "#1b212c"    # rows nested inside a card
BORDER = "#323b4d"        # hairline borders and bar tracks
MUTED = "#9aa7bd"         # secondary text


def ico(*names):
    """First icon name that exists in this Flet version (so a renamed icon can never crash the app)."""
    for n in names:
        v = getattr(ft.Icons, n, None)
        if v is not None:
            return v
    return ft.Icons.PETS


_MOONS = {"new moon": "🌑", "waxing crescent": "🌒", "first quarter": "🌓", "waxing gibbous": "🌔",
          "full moon": "🌕", "waning gibbous": "🌖", "last quarter": "🌗", "waning crescent": "🌘"}


def moon_emoji(phase_text):
    """The Moon picture for tonight's phase name (the server sends e.g. 'Waxing Gibbous (74% illuminated)')."""
    p = (phase_text or "").lower()
    for name, face in _MOONS.items():
        if name in p:
            return face
    return "🌙"


# Background photos for the main card, by weather. Edit these links to change the pictures.
# If a link ever fails to load, the card simply keeps its colour gradient.
_PHOTO = "https://images.unsplash.com/photo-{}?auto=format&fit=crop&w=900&q=70"
CONDITION_PHOTOS = {
    "sunny": _PHOTO.format("1601297183305-6df142704ea2"),
    "clear": _PHOTO.format("1506744038136-46273834b3fb"),
    "cloudy": _PHOTO.format("1534088568595-a066f410bcda"),
    "rain": _PHOTO.format("1515694346937-94d85e41e6f0"),
    "thunderstorm": _PHOTO.format("1605727216801-e27ce1d0cc28"),
}


def hero_photo(condition, is_night=False):
    c = (condition or "").lower()
    if any(w in c for w in ("thunder", "storm")):
        return CONDITION_PHOTOS["thunderstorm"]
    if any(w in c for w in ("rain", "shower", "drizzle")):
        return CONDITION_PHOTOS["rain"]
    if any(w in c for w in ("snow", "sleet", "flurr", "freezing", "hail", "fog", "mist", "haze", "smoke")):
        return None
    if "cloud" in c or "overcast" in c:
        return CONDITION_PHOTOS["cloudy"]
    return None if is_night else CONDITION_PHOTOS["sunny"]


def condition_icon(condition, is_night=False):
    """(icon, colour) that actually matches the weather instead of always a sun or moon."""
    c = (condition or "").lower()
    if any(w in c for w in ("thunder", "storm", "lightning")):
        return ico("THUNDERSTORM", "FLASH_ON", "CLOUD"), "#ffd54f"
    if any(w in c for w in ("snow", "sleet", "flurr", "freezing", "wintry", "hail")):
        return ico("AC_UNIT", "CLOUD"), "#b3e5fc"
    if any(w in c for w in ("rain", "shower", "drizzle")):
        return ico("UMBRELLA", "WATER_DROP"), "#4fc3f7"
    if any(w in c for w in ("fog", "mist", "haze", "smoke")):
        return ico("FOGGY", "CLOUD"), "#b0bec5"
    if "overcast" in c or ("cloudy" in c and "partly" not in c and "mostly" not in c):
        return ico("CLOUD"), "#b0bec5"
    if "partly" in c or "mostly cloudy" in c or "few clouds" in c or "scattered clouds" in c:
        return (ico("NIGHTS_STAY", "NIGHTLIGHT_ROUND") if is_night else ico("WB_CLOUDY", "CLOUD")), "#cfd8dc"
    return (ico("NIGHTLIGHT_ROUND") if is_night else ico("WB_SUNNY")), ("#80deea" if is_night else "#ffca28")


def hero_gradient(condition, is_night=False):
    """Background of the main card shifts with the weather and time of day."""
    c = (condition or "").lower()
    if is_night:
        colors = ["#0d1526", "#16202c", "#1b1830"]
    elif any(w in c for w in ("thunder", "storm")):
        colors = ["#2a2733", "#16202c", "#2a1f1f"]
    elif any(w in c for w in ("rain", "shower", "drizzle", "snow", "sleet")):
        colors = ["#1c2a3d", "#16202c", "#10202e"]
    elif any(w in c for w in ("cloud", "overcast", "fog", "mist", "haze")):
        colors = ["#262f3b", "#16202c", "#1d2530"]
    else:
        colors = ["#1f3b5c", "#16202c", "#2b211a"]
    return ft.LinearGradient(begin=ft.Alignment(-0.8, -1.0), end=ft.Alignment(1.0, 1.0), colors=colors)


def icon_text(icon, text, color="amber300", size=15):
    content = text if not isinstance(text, str) else ft.Text(text, size=12, color="white")
    return ft.Row([ft.Icon(icon, size=size, color=color), content], spacing=6, tight=True)


def stat_chip(icon, text_control, tint, color):
    return ft.Container(
        content=ft.Row([ft.Icon(icon, size=14, color=color), text_control], spacing=5, tight=True),
        bgcolor=tint, padding=ft.Padding(10, 6, 10, 6), border_radius=12,
    )


def section_title(text):
    return ft.Container(content=ft.Text(text.upper(), size=12, weight=ft.FontWeight.BOLD, color=MUTED),
                        padding=ft.Padding(0, 8, 0, 2))


_TITLES = {
    "enso_index": "ENSO (El Niño / La Niña)", "extreme_weather_24h": "Alerts · Next 24 Hours",
    "tropical_updates": "Tropical Updates", "microclimate_memo": "Local Microclimate",
    "watershed_overview": "Nearby Waterway", "tides_and_hydrology": "Tides",
    "darkness_window": "Dark-Sky Window", "stargazing_rating": "Stargazing",
    "visible_planets": "Planets Tonight", "moon_phase": "Moon Phase", "moon_rise": "Moonrise", "moon_set": "Moonset",
    "max_uv_rating": "UV Index", "fair_skin_burn_time": "Fair-Skin Burn Time",
    "recommended_protection": "Recommended Protection", "pollen_counts": "Pollen",
    "mold_spore_risk": "Mold Spores", "air_quality": "Air Quality", "car_wash_index": "Car Wash",
    "sinus_and_migraine": "Sinus & Migraine", "home_and_energy": "Home Ventilation",
    "outdoor_dining": "Outdoor Dining", "mosquito_and_insect": "Mosquitoes & Insects",
    "dog_walking": "Dog Walking", "beach_and_sunbathing": "Beach & Sun", "swimming_and_water": "Swimming",
    "hiking_and_trails": "Hiking", "surfing_and_boardsports": "Surfing & Boardsports",
    "celestial_events": "Sky Events", "planting_harvest": "Planting & Harvest",
}


def pretty_title(key):
    return _TITLES.get(key) or str(key).replace("_", " ").title()


async def main(page: ft.Page):
    page.title = "Thick Moose Weather"
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.scroll = ft.ScrollMode.ADAPTIVE
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 12

    latest_weather_data = {}
    current_selected_category = ["weather_climate"]

    # ---- the phone's own GPS (no guessing from the network address) ----
    class LocationProblem(Exception):
        """A problem with a message that is safe and useful to show the person."""

    MAX_ACCURACY_M = 1500          # a fix rougher than ~1 mile is not 'hyper-local'; ask for a retry instead
    geolocator = None
    if ftg is not None:
        try:
            geolocator = ftg.Geolocator()
            try:
                page.services.append(geolocator)
            except Exception:
                page.overlay.append(geolocator)
        except Exception:
            logging.exception("Geolocator could not be created")
            geolocator = None

    def _perm_name(status):
        return str(getattr(status, "name", status)).lower().replace("_", "").replace(".", "")

    async def get_phone_location():
        """(latitude, longitude) from the phone, or raises LocationProblem with a plain-English reason."""
        if geolocator is None:
            raise LocationProblem("Location isn't available in this version of the app. Please type your city or ZIP.")
        try:
            if await asyncio.wait_for(geolocator.is_location_service_enabled(), 8) is False:
                raise LocationProblem("Location is turned off on this phone. Turn it on, then tap 📍 to try again.")
        except LocationProblem:
            raise
        except Exception:
            logging.debug("Location service check unsupported here", exc_info=True)   # asking for the position will tell us

        try:
            perm = _perm_name(await asyncio.wait_for(geolocator.get_permission_status(), 8))
        except Exception:
            perm = "unknown"
        if "forever" in perm:
            raise LocationProblem("Location access is blocked for this app. Allow it in the phone's settings for Thick Moose Weather (or the browser's site settings), then tap 📍.")
        if "denied" in perm or "unable" in perm or perm in ("", "unknown"):
            try:
                perm = _perm_name(await asyncio.wait_for(geolocator.request_permission(), 120))
            except Exception:
                logging.debug("Permission request failed", exc_info=True)
            if "denied" in perm:
                raise LocationProblem("Location permission was declined. Tap 📍 to try again, or type your city or ZIP.")

        cfg = None
        try:
            level = getattr(ftg.GeolocatorPositionAccuracy, "BEST", None) or getattr(ftg.GeolocatorPositionAccuracy, "HIGH", None)
            if level is not None:
                cfg = ftg.GeolocatorConfiguration(accuracy=level)
        except Exception:
            cfg = None
        try:
            call = geolocator.get_current_position(configuration=cfg) if cfg is not None else geolocator.get_current_position()
            pos = await asyncio.wait_for(call, 30)
        except asyncio.TimeoutError:
            raise LocationProblem("Couldn't get a GPS fix in time. Try again near a window or outdoors, or type your city or ZIP.")
        except Exception:
            logging.exception("get_current_position failed")
            raise LocationProblem("Couldn't read this phone's location. Tap 📍 to retry, or type your city or ZIP.")

        lat, lon = getattr(pos, "latitude", None), getattr(pos, "longitude", None)
        if lat is None or lon is None:
            raise LocationProblem("The phone didn't return a location. Tap 📍 to retry, or type your city or ZIP.")
        accuracy = getattr(pos, "accuracy", None)
        if isinstance(accuracy, (int, float)) and accuracy > MAX_ACCURACY_M:
            miles = round(accuracy / 1609.34, 1)
            raise LocationProblem(f"Can't get a precise location (only accurate to about {miles} mi). Tap 📍 to retry, or type your city or ZIP.")
        return float(lat), float(lon)

    gps_state = {"query": None, "label": "Current location"}

    def fmt(value, suffix=""):
        """Show '--' for missing data instead of 'None' or an invented number."""
        return "--" if value is None or value == "" else f"{value}{suffix}"

    # Saved settings. Flet 1.x keeps them in a SharedPreferences service; older Flet used
    # page.client_storage. Try the new one first, then the old one, and always keep an
    # in-memory copy so the app still behaves within a single visit if storage is unavailable.
    memory_store = {}
    prefs_service = None
    try:
        if hasattr(ft, "SharedPreferences"):
            prefs_service = ft.SharedPreferences()
    except Exception:
        logging.exception("SharedPreferences could not be created")
        prefs_service = None

    async def storage_get(key: str):
        if prefs_service is not None:
            try:
                res = await asyncio.wait_for(prefs_service.get(key), timeout=1.5)
                if res is not None:
                    return res
            except Exception:
                logging.debug("SharedPreferences.get failed for %s", key, exc_info=True)
        legacy = getattr(page, "client_storage", None)
        if legacy is not None:
            try:
                async def _inner():
                    if hasattr(legacy, "get_async"):
                        res = legacy.get_async(key)
                        if inspect.isawaitable(res):
                            res = await res
                        if res is not None:
                            return res
                    res = legacy.get(key)
                    if inspect.isawaitable(res):
                        res = await res
                    return res
                res = await asyncio.wait_for(_inner(), timeout=1.0)
                if res is not None:
                    return res
            except Exception:
                logging.debug("client_storage.get failed for %s", key, exc_info=True)
        return memory_store.get(key)

    async def storage_set(key: str, value: str):
        memory_store[key] = value
        if prefs_service is not None:
            try:
                await asyncio.wait_for(prefs_service.set(key, value), timeout=1.5)
                return
            except Exception:
                logging.debug("SharedPreferences.set failed for %s", key, exc_info=True)
        legacy = getattr(page, "client_storage", None)
        if legacy is not None:
            try:
                async def _inner():
                    if hasattr(legacy, "set_async"):
                        res = legacy.set_async(key, value)
                        if inspect.isawaitable(res):
                            await res
                        return
                    res = legacy.set(key, value)
                    if inspect.isawaitable(res):
                        await res
                await asyncio.wait_for(_inner(), timeout=1.0)
            except Exception:
                logging.debug("client_storage.set failed for %s", key, exc_info=True)

    app_header = ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Image(
                    src="/moose.jpg",
                    width=54,
                    height=54,
                    fit="cover",
                    border_radius=27,
                    error_content=ft.Icon(ft.Icons.PETS, color="amber300", size=30),
                ),
                border=ft.Border.all(2, "amber300"),
                border_radius=28,
            ),
            ft.Column([
                ft.Text("Thick Moose Weather", size=22, weight=ft.FontWeight.BOLD, color="amber300"),
                ft.Text("Hyper-Local Microclimate Intelligence", size=12, color="cyan200", weight=ft.FontWeight.W_500),
            ], spacing=2),
        ], alignment=ft.MainAxisAlignment.CENTER, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding(0, 10, 0, 12),
        alignment=ft.Alignment(0, 0)
    )

    # Donation Dialog Setup
    def open_donation(e):
        donation_dialog.open = True
        page.update()

    def close_donation(e):
        donation_dialog.open = False
        page.update()

    def make_donation_btn(label: str, key: str):
        return ft.Container(
            content=ft.Text(label, size=14, weight=ft.FontWeight.BOLD, color="black"),
            bgcolor="amber400",
            border_radius=10,
            padding=ft.Padding(16, 10, 16, 10),
            ink=True,
            url=DONATION_LINKS.get(key, "#"),
            alignment=ft.Alignment(0, 0)
        )

    donation_dialog = ft.AlertDialog(
        modal=True,
        content_padding=ft.Padding(18, 18, 18, 18),
        content=ft.Container(
            width=360,
            content=ft.Column([
                ft.Container(
                    content=ft.Image(
                        src="/donation_dog.jpg",
                        width=280,
                        height=280,
                        fit="cover",
                        border_radius=18,
                        error_content=ft.Icon(ft.Icons.PETS, size=80, color="amber300"),
                    ),
                    alignment=ft.Alignment(0, 0),
                    border=ft.Border.all(2, "amber400"),
                    border_radius=20,
                ),
                ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                ft.Text(
                    "Weather should be free! Sharing it with the world in a neat and tidy 1-stop-package, unfortunately, is not. "
                    "To keep this app AD FREE and with no Subscription or Purchase Price, please consider donating to the Thick Moose "
                    "so he can continue providing premium hyper-local weather free of charge and ugly, disruptive ads. "
                    "A percentage of your donation will go to help fund and scale emerging carbon removal technologies.",
                    size=12,
                    color="white",
                    text_align=ft.TextAlign.CENTER,
                    weight=ft.FontWeight.W_400,
                ),
                ft.Divider(height=12, color="grey800"),
                ft.Text("Select Contribution Amount", size=13, weight=ft.FontWeight.BOLD, color="amber300", text_align=ft.TextAlign.CENTER),
                ft.Row([
                    make_donation_btn("$1", "1"),
                    make_donation_btn("$3", "3"),
                    make_donation_btn("$5", "5"),
                    make_donation_btn("$10", "10"),
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6, scroll=ft.ScrollMode.ADAPTIVE),
        ),
        actions=[
            ft.TextButton("Maybe Later", on_click=close_donation)
        ],
        actions_alignment=ft.MainAxisAlignment.CENTER,
    )
    page.overlay.append(donation_dialog)

    # Clickable Banner / Pill Badge (Anchored in Footer)
    keep_weather_free_badge = ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Image(
                    src="/donation_dog.jpg",
                    width=42,
                    height=42,
                    fit="cover",
                    border_radius=21,
                    error_content=ft.Icon(ft.Icons.PETS, color="amber300", size=24),
                ),
                border=ft.Border.all(1.5, "amber300"),
                border_radius=22,
            ),
            ft.Column([
                ft.Text("Keep Weather Free!!!", size=14, weight=ft.FontWeight.BOLD, color="amber300"),
                ft.Text("Support Thick Moose & ad-free weather", size=10, color="grey300"),
            ], spacing=1),
            ft.Icon(ft.Icons.VOLUNTEER_ACTIVISM, size=20, color="amber300"),
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
        bgcolor="#18202d",
        border=ft.Border.all(1.5, "amber400"),
        border_radius=24,
        padding=ft.Padding(16, 8, 18, 8),
        ink=True,
        on_click=open_donation,
        tooltip="Support Thick Moose Weather — Keep it 100% Ad-Free",
    )

    widget_loc_text = ft.Text("No location selected", size=17, weight=ft.FontWeight.BOLD, color="white")
    widget_condition_text = ft.Text("Search a place or tap the location icon", size=14, color="grey300", weight=ft.FontWeight.W_500)
    widget_hero_icon = ft.Icon(ft.Icons.WB_SUNNY, size=72, color="amber300")
    widget_moon_text = ft.Text("🌙", size=72, visible=False)
    widget_temp_text = ft.Text("--°", size=72, weight=ft.FontWeight.BOLD, color="white")
    widget_hl_text = ft.Text("H: --°  L: --°", size=13, weight=ft.FontWeight.W_600, color="grey300")
    updated_badge_text = ft.Text("Updating…", size=10, weight=ft.FontWeight.BOLD, color="amber300")
    data_source_text = ft.Text("", size=10, color="grey300")
    widget_rain_badge = ft.Text("--% precip", size=12, color="cyan200", weight=ft.FontWeight.W_600)
    widget_uv_badge = ft.Text("UV --", size=12, color="orange200", weight=ft.FontWeight.W_600)
    widget_aqi_badge = ft.Text("AQI --", size=12, color="green300", weight=ft.FontWeight.W_600)

    location_input = ft.TextField(
        label="Location (Address, City, or ZIP)",
        hint_text="e.g. Wilmington, NC or 28412",
        value="",
        width=220,
        border_color="amber300",
        focused_border_color="amber200",
        dense=True,
        content_padding=ft.Padding(10, 10, 10, 10),
    )

    sports_input = ft.TextField(
        label="Add a team (e.g. Carolina Panthers)",
        value="Carolina Panthers, Atlanta Braves, NC State",
        expand=True,
        border_color="amber300",
        focused_border_color="amber200",
        dense=True,
        content_padding=ft.Padding(10, 10, 10, 10),
    )

    location_display_text = ft.Text("📍 Detecting local forecast...", size=12, color=MUTED, weight=ft.FontWeight.W_500, text_align=ft.TextAlign.CENTER)
    condition_text = ft.Text("Loading weather...", size=18, weight=ft.FontWeight.BOLD, color="amber200")
    hero_weather_icon = ft.Icon(ft.Icons.WB_SUNNY, size=64, color="amber300")
    curr_temp_text = ft.Text("--°F", size=48, weight=ft.FontWeight.BOLD, color="white")
    feels_like_text = ft.Text("Feels like --°", size=14, color="grey300")
    humidity_text = ft.Text("--% humidity", size=12, color="cyan200", weight=ft.FontWeight.W_600)
    wind_text = ft.Text("-- mph wind", size=12, color="cyan200", weight=ft.FontWeight.W_600)
    uv_badge = ft.Text("UV: --", size=13, color="green300", weight=ft.FontWeight.BOLD)
    aqi_badge = ft.Text("AQI: --", size=13, color="green300", weight=ft.FontWeight.BOLD)

    sunrise_text = ft.Text("Sunrise --", size=13, color="white", weight=ft.FontWeight.W_600)
    sunset_text = ft.Text("Sunset --", size=13, color="white", weight=ft.FontWeight.W_600)
    moonrise_text = ft.Text("Moonrise --", size=13, color="white", weight=ft.FontWeight.W_600)
    moonset_text = ft.Text("Moonset --", size=13, color="white", weight=ft.FontWeight.W_600)

    current_precip_text = ft.Text("Precip Now: --% | Next 24h Max: --%", size=14, color="cyan300", weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)
    rain_duration_text = ft.Text("Retrieving local radar & metrics...", size=13, color="amber100", text_align=ft.TextAlign.CENTER)

    radar_timestamp_text = ft.Text("Updated just now", size=11, color="green300", weight=ft.FontWeight.W_600)

    radar_button_widget = ft.Container(
        content=ft.Row([
            ft.Icon(ft.Icons.RADAR, color="black", size=18),
            ft.Text("Open radar map", color="black", weight=ft.FontWeight.BOLD, size=13),
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
        bgcolor="amber400",
        border_radius=10,
        padding=ft.Padding(16, 10, 16, 10),
        ink=True,
        url="/radar?lat=34.1378&lon=-77.9150&label=Location",
    )

    radar_container = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.SATELLITE_ALT, color="cyan300", size=18),
                ft.Text("Weather Radar: Rain & Storms Near You", size=14, weight=ft.FontWeight.BOLD, color="amber300"),
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=6),
            ft.Text("See where rain is falling and where it's heading. Shows the past 2 hours plus a short-term outlook, with your location pinned.", size=11, color="grey400", text_align=ft.TextAlign.CENTER),
            radar_timestamp_text,
            ft.Container(height=4),
            radar_button_widget,
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
        bgcolor="#18202c",
        border=ft.Border.all(1, "cyan800"),
        border_radius=12,
        padding=14,
        alignment=ft.Alignment(0, 0)
    )

    hourly_row = ft.Row([], spacing=10, scroll=ft.ScrollMode.ADAPTIVE)
    hourly_container = ft.Container(content=hourly_row, padding=10, height=150, bgcolor=CARD, border=ft.Border.all(1, BORDER), border_radius=16)

    forecast_row = ft.Row([], alignment=ft.MainAxisAlignment.START, spacing=14, scroll=ft.ScrollMode.ADAPTIVE)
    forecast_container = ft.Container(content=forecast_row, padding=12, height=310, bgcolor=CARD, border=ft.Border.all(1, BORDER), border_radius=16)

    category_cards_column = ft.Column([], spacing=14)
    category_display_container = ft.Container(content=category_cards_column, padding=15, bgcolor=CARD, border=ft.Border.all(1, BORDER), border_radius=16)

    detail_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Detailed Day Outlook", size=16, weight=ft.FontWeight.BOLD, color="amber300"),
        content=ft.Container(width=340, content=ft.Text("No details available")),
        actions=[ft.TextButton("Close", on_click=lambda e: close_dialog(e))],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.overlay.append(detail_dialog)

    def close_dialog(e):
        detail_dialog.open = False
        page.update()

    def tracked_teams():
        return [t.strip() for t in sports_input.value.split(",") if t.strip()]

    async def remove_team(team_name):
        teams = [t for t in tracked_teams() if t.lower() != team_name.lower()]
        sports_input.value = ", ".join(teams)
        await storage_set("tmw_saved_teams", sports_input.value)
        if location_input.value.strip():
            await refresh_sports()
        else:
            category_cards_column.controls = build_cards_for_category(current_selected_category[0])
            page.update()

    def team_chips():
        teams = tracked_teams()
        if not teams:
            return ft.Text("No teams tracked. Type a team name above and tap search.", size=12, color="grey400")
        row = ft.Row(wrap=True, spacing=8, run_spacing=8)
        for t in teams:
            row.controls.append(ft.Container(
                content=ft.Row([ft.Text(t, size=12, color="white"), ft.Icon(ft.Icons.CLOSE, size=14, color="grey400")], spacing=6, tight=True),
                bgcolor=CARD_INNER, border=ft.Border.all(1, BORDER), border_radius=16,
                padding=ft.Padding(10, 6, 8, 6), ink=True, tooltip=f"Stop tracking {t}",
                on_click=lambda e, name=t: page.run_task(remove_team, name),
            ))
        return row

    async def add_team_from_picker(team_name):
        current_val = sports_input.value.strip()
        teams = [t.strip() for t in current_val.split(",") if t.strip()]
        if team_name not in teams:
            teams.append(team_name)
        sports_input.value = ", ".join(teams)
        team_picker_dialog.open = False
        page.update()
        if location_input.value.strip():
            mode = await storage_get("tmw_location_mode")
            await load_weather(is_auto=(mode != "manual"))

    async def select_alt_team(alt_query):
        current_val = sports_input.value.strip()
        teams = [t.strip() for t in current_val.split(",") if t.strip()]
        replaced = False
        for idx, t in enumerate(teams):
            if t.lower() in alt_query.lower() or alt_query.lower() in t.lower():
                teams[idx] = alt_query
                replaced = True
                break
        if not replaced:
            teams.append(alt_query)
        sports_input.value = ", ".join(teams)
        page.update()
        if location_input.value.strip():
            mode = await storage_get("tmw_location_mode")
            await load_weather(is_auto=(mode != "manual"))

    popular_teams_data = [
        ("🏈 NFL", ["Carolina Panthers", "Dallas Cowboys", "Kansas City Chiefs", "Philadelphia Eagles"]),
        ("🎓 NCAA College", ["NC State", "UNC Tar Heels", "Duke Blue Devils", "Clemson", "Georgia Bulldogs"]),
        ("⚾ MLB", ["Atlanta Braves", "New York Yankees", "Los Angeles Dodgers", "Boston Red Sox"]),
        ("🏒 NHL & 🏀 NBA", ["Carolina Hurricanes", "Charlotte Hornets"]),
    ]

    team_picker_column = ft.Column([], spacing=10, scroll=ft.ScrollMode.ADAPTIVE)
    for cat_title, t_list in popular_teams_data:
        chips_row = ft.Row(wrap=True, spacing=6)
        for t_name in t_list:
            chips_row.controls.append(
                ft.Container(
                    content=ft.Text(t_name, size=11, color="white"),
                    bgcolor=CARD_INNER,
                    border=ft.Border.all(1, "cyan800"),
                    border_radius=14,
                    padding=ft.Padding(10, 5, 10, 5),
                    ink=True,
                    on_click=lambda e, name=t_name: page.run_task(add_team_from_picker, name)
                )
            )
        team_picker_column.controls.append(
            ft.Column([
                ft.Text(cat_title, size=13, weight=ft.FontWeight.BOLD, color="amber300"),
                chips_row
            ], spacing=4)
        )

    team_picker_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Quick Team Selector", size=16, weight=ft.FontWeight.BOLD, color="amber300"),
        content=ft.Container(width=340, height=360, content=team_picker_column),
        actions=[ft.TextButton("Done", on_click=lambda e: close_team_picker(e))],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.overlay.append(team_picker_dialog)

    def open_team_picker(e):
        team_picker_dialog.open = True
        page.update()

    def close_team_picker(e):
        team_picker_dialog.open = False
        page.update()

    def show_day_details(day_info):
        detail_dialog.title = ft.Text(day_info.get("date", "Day Forecast"), size=16, weight=ft.FontWeight.BOLD, color="amber300")
        detail_dialog.content = ft.Container(
            width=360,
            content=ft.Column([
                ft.Row([
                    ft.Text(f"High: {fmt(day_info.get('high'))}°F", size=15, color="red300", weight=ft.FontWeight.BOLD),
                    ft.Text(f"Low: {fmt(day_info.get('low'))}°F", size=15, color="blue300", weight=ft.FontWeight.BOLD),
                    ft.Text(f"Rain: {fmt(day_info.get('rain_prob_max'), '%')}", size=14, color="cyan300", weight=ft.FontWeight.BOLD),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(height=10, color="grey800"),
                ft.Text("☀️ Daytime Conditions", size=13, weight=ft.FontWeight.BOLD, color="amber200"),
                ft.Text(day_info.get("day_summary", ""), size=12, color="white"),
                ft.Divider(height=10, color="grey800"),
                ft.Text("🌙 Overnight Conditions", size=13, weight=ft.FontWeight.BOLD, color="cyan200"),
                ft.Text(day_info.get("night_summary", ""), size=12, color="white"),
                ft.Divider(height=10, color="grey800"),
                ft.Row([
                    ft.Text(f"Sunrise {fmt(day_info.get('sunrise'))}", size=11, color="amber100"),
                    ft.Text(f"Sunset {fmt(day_info.get('sunset'))}", size=11, color="amber100"),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([
                    ft.Text(f"Moonrise {fmt(day_info.get('moon_rise'))}", size=11, color="cyan200"),
                    ft.Text(f"Moonset {fmt(day_info.get('moon_set'))}", size=11, color="cyan200"),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ], spacing=6, tight=True)
        )
        detail_dialog.open = True
        page.update()

    def build_cards_for_category(category_key):
        cards = []
        cat_data = latest_weather_data.get(category_key, {})

        if category_key == "sporting_event":
            search_box = ft.Container(
                content=ft.Row([
                    sports_input,
                    ft.IconButton(icon=ft.Icons.SEARCH, on_click=lambda e: page.run_task(refresh_sports), icon_color="amber300", tooltip="Search Teams"),
                    ft.IconButton(icon=ft.Icons.TUNE, on_click=open_team_picker, icon_color="cyan300", tooltip="Choose from Team List")
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=4),
                bgcolor=CARD_INNER, padding=8, border_radius=8
            )
            cards.append(search_box)
            cards.append(team_chips())

        if not cat_data or not isinstance(cat_data, dict):
            if latest_weather_data:
                msg = "No data for this category right now. Try refreshing in a moment."
            else:
                msg = "Awaiting location to generate environmental insight."
            cards.append(ft.Text(msg, color="grey400", size=13))
            return cards

        for key, val in cat_data.items():
            title = pretty_title(key)

            if key == "clothing" and isinstance(val, dict):
                clothing_rows = [
                    ft.Text("Clothing Recommendations", size=15, weight=ft.FontWeight.BOLD, color="amber300"),
                    ft.Divider(height=6, color="grey800")
                ]
                for time_slot, suggestion in val.items():
                    clothing_rows.append(
                        ft.Container(
                            content=ft.Row([
                                ft.Container(
                                    content=ft.Text(time_slot.capitalize(), size=11, weight=ft.FontWeight.BOLD, color="black"),
                                    bgcolor="amber300", padding=ft.Padding(8, 4, 8, 4), border_radius=6, width=90, alignment=ft.Alignment(0, 0)
                                ),
                                ft.Text(str(suggestion), size=12, color="white", expand=True)
                            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                            bgcolor=CARD_INNER, padding=8, border_radius=6
                        )
                    )
                cards.append(ft.Container(content=ft.Column(clothing_rows, spacing=8), bgcolor=CARD, border_radius=8, padding=12))

            elif key == "hair_makeup" and isinstance(val, dict):
                hm_items = [
                    ft.Text("Hair & Makeup Outlook", size=15, weight=ft.FontWeight.BOLD, color="amber300"),
                    ft.Divider(height=6, color="grey800")
                ]
                labels = {
                    "hair": ("💇 Hair Frizz Index", "amber300"),
                    "hair_frizz_index": ("💇 Hair Frizz Index", "amber300"),
                    "makeup": ("💄 Makeup Finish", "#ff80ab"),
                    "makeup_finish_index": ("💄 Makeup Finish", "#ff80ab"),
                }
                for subk, subv in val.items():
                    tag_name, tag_color = labels.get(subk, (subk.replace('_', ' ').title(), "amber300"))
                    hm_items.append(
                        ft.Container(
                            content=ft.Row([
                                ft.Container(
                                    content=ft.Text(tag_name, size=11, weight=ft.FontWeight.BOLD, color="black"),
                                    bgcolor=tag_color,
                                    padding=ft.Padding(8, 4, 8, 4),
                                    border_radius=6,
                                    width=150,
                                    alignment=ft.Alignment(0, 0)
                                ),
                                ft.Text(str(subv), size=12, color="white", expand=True)
                            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                            bgcolor=CARD_INNER, padding=8, border_radius=6
                        )
                    )
                cards.append(ft.Container(content=ft.Column(hm_items, spacing=8), bgcolor=CARD, border_radius=8, padding=12))

            elif isinstance(val, dict) and "score" in val:
                score = val.get("score", "--")
                details = val.get("details", "")
                try:
                    pct = int(max(0, min(100, round(float(score)))))
                except (TypeError, ValueError):
                    pct = None
                s_color = "#66bb6a" if (pct or 0) >= 70 else "#ffca28" if (pct or 0) >= 45 else "#ef5350"
                card_rows = [
                    ft.Row([
                        ft.Text(title, size=15, weight=ft.FontWeight.BOLD, color="white"),
                        ft.Text(f"{score}", size=22, weight=ft.FontWeight.BOLD, color=s_color),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ]
                if pct is not None:
                    card_rows.append(ft.Row([
                        ft.Container(expand=pct, height=6, bgcolor=s_color, border_radius=3),
                        ft.Container(expand=100 - pct, height=6, bgcolor=BORDER, border_radius=3),
                    ], spacing=0))
                card_rows.append(ft.Text(details, size=12, color="grey300"))
                cards.append(ft.Container(content=ft.Column(card_rows, spacing=8), bgcolor=CARD, border_radius=12, padding=14))

            elif key in ["allergens_and_pollen", "sun_and_uv_protection"] and isinstance(val, dict):
                sec_title = "Allergens & Pollen Spectrum" if key == "allergens_and_pollen" else "UV Radiation & Sun Protection"
                items = [
                    ft.Text(sec_title, size=15, weight=ft.FontWeight.BOLD, color="amber300"),
                    ft.Divider(height=6, color="grey800")
                ]
                for sk, sv in val.items():
                    clean_label = pretty_title(sk)
                    items.append(
                        ft.Row([
                            ft.Text(f"{clean_label}: ", size=12, weight=ft.FontWeight.BOLD, color="amber200"),
                            ft.Text(str(sv), size=12, color="white", expand=True)
                        ], vertical_alignment=ft.CrossAxisAlignment.START)
                    )
                cards.append(ft.Container(content=ft.Column(items, spacing=6), bgcolor=CARD, border_radius=8, padding=12))

            elif key == "leaf_change":
                cards.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Autumn Foliage Progression", size=15, weight=ft.FontWeight.BOLD, color="amber300"),
                            ft.Divider(height=6, color="grey800"),
                            ft.Text(str(val), size=12, color="white")
                        ], spacing=6),
                        bgcolor=CARD, border_radius=8, padding=12
                    )
                )

            elif key == "events" and isinstance(val, list):
                event_cards = [
                    ft.Text("Tracked Game Day Weather", size=15, weight=ft.FontWeight.BOLD, color="amber300"),
                    ft.Divider(height=6, color="grey800")
                ]
                for ev in val:
                    game_score = ev.get("score", "")
                    header_items = [
                        ft.Text(ev.get("title", "Matchup"), size=14, weight=ft.FontWeight.BOLD, color="amber200", expand=True),
                    ]
                    if game_score:
                        header_items.append(
                            ft.Container(
                                content=ft.Text(f"📊 {game_score}", size=11, weight=ft.FontWeight.BOLD, color="black"),
                                bgcolor="amber400",
                                border_radius=6,
                                padding=ft.Padding(6, 2, 6, 2)
                            )
                        )

                    card_content = [
                        ft.Row(header_items, alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ]
                    if ev.get("time"):
                        card_content.append(ft.Row([
                            ft.Icon(ft.Icons.SCHEDULE, size=14, color="cyan200"),
                            ft.Text(f"{ev.get('time', '')}", size=12, color="cyan200", weight=ft.FontWeight.W_500, expand=True)
                        ], spacing=6))
                    if ev.get("venue"):
                        card_content.append(ft.Row([
                            ft.Icon(ft.Icons.LOCATION_ON, size=14, color="grey400"),
                            ft.Text(ev.get('venue', ''), size=12, color="grey300", expand=True)
                        ], spacing=6))
                    if ev.get("conditions"):
                        card_content.append(ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.Icons.WB_SUNNY, size=14, color="green300"),
                                ft.Text(ev.get('conditions', ''), size=12, color="green200", weight=ft.FontWeight.W_500, expand=True)
                            ], spacing=6),
                            bgcolor="#16222f",
                            border=ft.Border.all(1, "cyan900"),
                            border_radius=6,
                            padding=ft.Padding(8, 6, 8, 6)
                        ))

                    alts = ev.get("alternatives", [])
                    if alts:
                        alt_row = ft.Row([ft.Text("Did you mean: ", size=11, color="grey400", weight=ft.FontWeight.W_600)], wrap=True, spacing=6)
                        for alt_item in alts:
                            alt_name = alt_item.get("name", "")
                            alt_q = alt_item.get("query", "")
                            alt_row.controls.append(
                                ft.Container(
                                    content=ft.Text(alt_name, size=10, color="cyan200"),
                                    bgcolor="#16222f",
                                    border=ft.Border.all(1, "cyan700"),
                                    border_radius=12,
                                    padding=ft.Padding(8, 4, 8, 4),
                                    ink=True,
                                    on_click=lambda e, q=alt_q: page.run_task(select_alt_team, q)
                                )
                            )
                        card_content.append(ft.Container(content=alt_row, padding=ft.Padding(0, 4, 0, 0)))

                    event_cards.append(
                        ft.Container(
                            content=ft.Column(card_content, spacing=6),
                            bgcolor=CARD_INNER, padding=10, border_radius=8
                        )
                    )
                cards.append(ft.Container(content=ft.Column(event_cards, spacing=8), bgcolor=CARD, border_radius=8, padding=12))

            elif key == "planting_harvest" and isinstance(val, list):
                plant_items = [
                    ft.Text("Planting & Harvest Calendar", size=15, weight=ft.FontWeight.BOLD, color="amber300"),
                    ft.Divider(height=6, color="grey800")
                ]
                for p in val:
                    plant_items.append(
                        ft.Container(
                            content=ft.Row([
                                ft.Column([
                                    ft.Text(f"🌱 {p.get('item', '')}", size=13, weight=ft.FontWeight.BOLD, color="amber200"),
                                    ft.Text(p.get("timing", ""), size=11, color="cyan200")
                                ], expand=True),
                                ft.Container(
                                    content=ft.Text(p.get("action", ""), size=11, color="white", weight=ft.FontWeight.BOLD),
                                    bgcolor="#102a18", border=ft.Border.all(1, "green400"), padding=ft.Padding(8, 4, 8, 4), border_radius=6
                                )
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            bgcolor=CARD_INNER, padding=8, border_radius=6
                        )
                    )
                cards.append(ft.Container(content=ft.Column(plant_items, spacing=8), bgcolor=CARD, border_radius=8, padding=12))

            elif key == "celestial_events" and isinstance(val, list):
                celest_items = [
                    ft.Text("Celestial Events & Passings", size=15, weight=ft.FontWeight.BOLD, color="amber300"),
                    ft.Divider(height=6, color="grey800")
                ]
                for c in val:
                    celest_items.append(
                        ft.Container(
                            content=ft.Column([
                                ft.Row([
                                    ft.Text(c.get("title", ""), size=13, weight=ft.FontWeight.BOLD, color="amber200", expand=True),
                                    ft.Text(f"⏰ {c.get('time', '')}", size=12, color="cyan200", weight=ft.FontWeight.BOLD)
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                *([ft.Text(f"🔭 Direction: {c.get('direction')}", size=11, color="grey300")] if c.get('direction') else []),
                                ft.Text(f"✨ {c.get('notes', '')}", size=11, color="green200")
                            ], spacing=3),
                            bgcolor=CARD_INNER, padding=8, border_radius=6
                        )
                    )
                cards.append(ft.Container(content=ft.Column(celest_items, spacing=8), bgcolor=CARD, border_radius=8, padding=12))

            elif isinstance(val, dict):
                col = [ft.Text(title, size=15, weight=ft.FontWeight.BOLD, color="amber300"), ft.Divider(height=6, color="grey800")]
                for sk, sv in val.items():
                    col.append(
                        ft.Row([
                            ft.Text(f"{pretty_title(sk)}: ", size=12, weight=ft.FontWeight.BOLD, color="grey400"),
                            ft.Text(str(sv), size=12, color="white", expand=True)
                        ], vertical_alignment=ft.CrossAxisAlignment.START)
                    )
                cards.append(ft.Container(content=ft.Column(col, spacing=6), bgcolor=CARD, border_radius=8, padding=12))

            elif isinstance(val, list):
                col = [ft.Text(title, size=15, weight=ft.FontWeight.BOLD, color="amber300"), ft.Divider(height=6, color="grey800")]
                for li in val:
                    col.append(ft.Text(f"• {str(li)}", size=12, color="white"))
                cards.append(ft.Container(content=ft.Column(col, spacing=6), bgcolor=CARD, border_radius=8, padding=12))

            else:
                cards.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Text(title, size=14, weight=ft.FontWeight.BOLD, color="amber200"),
                            ft.Divider(height=6, color="grey800"),
                            ft.Text(str(val), size=12, color="white")
                        ], spacing=4),
                        bgcolor=CARD, border_radius=8, padding=12,
                        border=ft.Border.all(1.5, "#ef5350") if str(val).startswith("⚠️") else None,
                    )
                )
        return cards

    def handle_category_click(e):
        cat_key = e.control.data
        current_selected_category[0] = cat_key
        for chip in category_buttons_row.controls:
            is_active = (chip.data == cat_key)
            chip.bgcolor = "amber400" if is_active else CARD
            chip.content.controls[1].color = "black" if is_active else "white"
            chip.content.controls[0].color = "black" if is_active else "amber200"
        category_cards_column.controls = build_cards_for_category(cat_key)
        page.update()

    categories_list = [
        ("weather_climate", "Weather & Climate", ft.Icons.THERMOSTAT),
        ("outdoor_activities", "Outdoor Activities", ft.Icons.DIRECTIONS_RUN),
        ("lifestyle", "Lifestyle", ft.Icons.LOCAL_CAFE),
        ("sporting_event", "Sporting Events", ft.Icons.SPORTS_SOCCER),
        ("astronomy", "Astronomy", ft.Icons.NIGHTLIGHT_ROUND),
    ]

    category_chips = []
    for key, label, icon in categories_list:
        is_active = (key == "weather_climate")
        chip = ft.Container(
            data=key,
            on_click=handle_category_click,
            ink=True,
            padding=ft.Padding(14, 8, 14, 8),
            border_radius=20,
            bgcolor="amber400" if is_active else CARD,
            content=ft.Row([
                ft.Icon(icon, size=16, color="black" if is_active else "amber200"),
                ft.Text(label, size=12, weight=ft.FontWeight.BOLD, color="black" if is_active else "white"),
            ], spacing=6),
        )
        category_chips.append(chip)

    category_buttons_row = ft.Row(controls=category_chips, spacing=8, scroll=ft.ScrollMode.ADAPTIVE)

    async def refresh_sports(e=None):
        """Re-run the forecast with the new team list WITHOUT changing the saved location mode."""
        if not location_input.value.strip():
            return
        mode = await storage_get("tmw_location_mode")
        await load_weather(is_auto=(mode != "manual"))

    async def handle_autodetect_click(e=None):
        await storage_set("tmw_location_mode", "auto")
        await storage_set("tmw_saved_location", "")
        await auto_detect_gps()

    async def load_weather_manual(e=None):
        val = location_input.value.strip()
        if val:
            await storage_set("tmw_location_mode", "manual")
            await storage_set("tmw_saved_location", val)
            await load_weather(is_auto=False)

    async def auto_detect_gps():
        location_display_text.value = "📍 Getting your precise location..."
        page.update()
        try:
            lat, lon = await get_phone_location()
        except LocationProblem as problem:
            location_display_text.value = f"📍 {problem}"
            page.update()
            return
        except Exception:
            logging.exception("Location detection failed")
            location_display_text.value = "📍 Couldn't get your location. Tap 📍 to retry, or type your city or ZIP."
            page.update()
            return
        gps_state["query"] = f"{lat:.5f},{lon:.5f}"
        gps_state["label"] = "Current location"
        location_input.value = gps_state["label"]
        page.update()
        await storage_set("tmw_location_mode", "auto")
        await load_weather(is_auto=True)

    async def load_weather(is_auto=False):
        loc = location_input.value.strip()
        teams = sports_input.value.strip()

        if not loc:
            condition_text.value = "Enter location or tap 📍"
            location_display_text.value = "📍 Please enter your location"
            page.update()
            return

        using_gps = bool(gps_state["query"]) and loc == gps_state["label"]
        query = gps_state["query"] if using_gps else loc
        if not is_auto:
            await storage_set("tmw_saved_location", loc)
        await storage_set("tmw_saved_teams", teams)

        try:
            res = await asyncio.to_thread(server.get_full_weather_data, query, teams)
            name = res.get("location_name", loc)
            if using_gps:
                gps_state["label"] = name
                location_input.value = name

            latest_weather_data.clear()
            latest_weather_data.update(res)

            location_display_text.value = f"📍 {name}"
            curr = res.get("current", {})
            condition = curr.get("condition") or "--"
            t_val = curr.get("temp")
            feels_val = curr.get("feels_like")
            if feels_val is None:
                feels_val = curr.get("heat_index")

            if "radar_url" in res:
                radar_button_widget.url = res["radar_url"]
            radar_time_val = res.get("radar_time", datetime.now().strftime("%I:%M %p").lstrip("0"))
            radar_timestamp_text.value = f"Weather updated at {radar_time_val}"
            updated_badge_text.value = f"Updated {radar_time_val}"
            data_source_text.value = f"Now: {curr.get('data_source')}" if curr.get("data_source") else ""

            is_night = curr.get("is_night", False)
            hero_icon_name, hero_icon_color = condition_icon(condition, is_night)
            hero_weather_icon.icon = hero_icon_name
            hero_weather_icon.color = hero_icon_color
            widget_hero_icon.icon = hero_icon_name
            widget_hero_icon.color = hero_icon_color
            # Clear night sky: show the Moon as it really looks tonight instead of an icon.
            sky = (condition or "").lower()
            clear_night = is_night and not any(w in sky for w in (
                "rain", "shower", "drizzle", "thunder", "storm", "snow", "sleet", "fog", "mist", "haze", "smoke", "cloud", "overcast"))
            phase_name = str((res.get("astronomy") or {}).get("moon_phase") or "")
            widget_moon_text.value = moon_emoji(phase_name)
            widget_moon_text.visible = bool(clear_night)
            widget_hero_icon.visible = not clear_night
            photorealistic_2x2_widget.gradient = hero_gradient(condition, is_night)
            photo_url = hero_photo(condition, is_night)
            if photo_url:
                hero_photo_img.src = photo_url
            hero_photo_layer.visible = bool(photo_url)
            hero_scrim.visible = bool(photo_url)

            condition_text.value = condition
            curr_temp_text.value = f"{fmt(t_val)}°F"
            feels_like_text.value = f"Feels like {fmt(feels_val)}°"
            humidity_text.value = f"{fmt(curr.get('humidity'), '%')} humidity"
            wind_text.value = f"{fmt(curr.get('wind'))} mph wind"
            uv_val = fmt(curr.get("uv_index"))
            uv_badge.value = f"UV: {uv_val}"

            aqi_obj = res.get("aqi", {})
            if isinstance(aqi_obj, dict):
                aqi_raw = aqi_obj.get("value", aqi_obj.get("aqi"))
                aqi_num = fmt(aqi_raw)
                aqi_cat = aqi_obj.get("category", "") if aqi_raw is not None else ""
                aqi_str = f"AQI: {aqi_num} ({aqi_cat})" if aqi_cat else f"AQI: {aqi_num}"
                widget_aqi_str = f"AQI {aqi_num} ({aqi_cat})" if aqi_cat else f"AQI {aqi_num}"
            else:
                aqi_str = f"AQI: {fmt(aqi_obj)}"
                widget_aqi_str = f"AQI {fmt(aqi_obj)}"

            aqi_badge.value = aqi_str
            widget_aqi_badge.value = widget_aqi_str
            widget_uv_badge.value = f"UV {uv_val}"

            sunrise_text.value = f"Sunrise {fmt(curr.get('sunrise'))}"
            sunset_text.value = f"Sunset {fmt(curr.get('sunset'))}"
            moonrise_text.value = f"Moonrise {fmt(curr.get('moon_rise'))}"
            moonset_text.value = f"Moonset {fmt(curr.get('moon_set'))}"

            current_precip_text.value = curr.get("precip_summary") or "Precip: --"
            rain_duration_text.value = curr.get("rain_duration") or ""

            widget_loc_text.value = name
            widget_condition_text.value = condition
            widget_temp_text.value = f"{fmt(t_val)}°"

            daily_data = res.get("daily", [])
            if daily_data:
                first = daily_data[0]
                widget_hl_text.value = f"H: {fmt(first.get('high'))}°  L: {fmt(first.get('low'))}°"
                widget_rain_badge.value = f"{fmt(first.get('rain_prob_max'), '%')} precip"

            hourly_cards = []
            for item in res.get("hourly_36", []):
                h_night = item.get("is_night", False)
                hourly_cards.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Text(str(item.get("time")), size=11, color="amber200", weight=ft.FontWeight.BOLD),
                            ft.Icon(condition_icon(item.get("condition"), h_night)[0], size=22, color=condition_icon(item.get("condition"), h_night)[1]),
                            ft.Text(f"{fmt(item.get('temp'))}°", size=13, weight=ft.FontWeight.BOLD, color="white"),
                            ft.Row([ft.Icon(ft.Icons.WATER_DROP, size=10, color="cyan300"), ft.Text(fmt(item.get('rain_chance'), '%'), size=10, color="cyan300")], alignment=ft.MainAxisAlignment.CENTER),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                        width=72, height=112, padding=6, border_radius=12, bgcolor=CARD_INNER,
                    )
                )
            if not hourly_cards:
                hourly_cards = [ft.Text("Hourly forecast unavailable right now.", size=12, color="grey400")]
            hourly_row.controls = hourly_cards

            day_cards = []
            for day in daily_data:
                day_cards.append(
                    ft.Container(
                        data=day,
                        on_click=lambda e: show_day_details(e.control.data),
                        ink=True,
                        tooltip="Tap for full details",
                        content=ft.Column([
                            ft.Row([
                                ft.Icon(condition_icon(day.get("day_summary"), False)[0], size=18, color=condition_icon(day.get("day_summary"), False)[1]),
                                ft.Text(day.get("date", ""), size=12, weight=ft.FontWeight.BOLD, color="white"),
                            ], alignment=ft.MainAxisAlignment.CENTER, spacing=6),
                            ft.Container(
                                content=ft.Row([
                                    ft.Text(f"↑ {fmt(day.get('high'))}°", size=13, color="red300", weight=ft.FontWeight.BOLD),
                                    ft.Text(f"↓ {fmt(day.get('low'))}°", size=13, color="blue300", weight=ft.FontWeight.BOLD),
                                ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                                bgcolor=CARD_INNER, padding=4, border_radius=6,
                            ),
                            ft.Container(
                                content=ft.Column([
                                    ft.Row([icon_text(ico("WB_TWILIGHT", "WB_SUNNY"), ft.Text(fmt(day.get('sunrise')), size=10, color="amber100"), "amber300", 12), icon_text(ico("WB_TWILIGHT", "WB_SUNNY"), ft.Text(fmt(day.get('sunset')), size=10, color="amber100"), "orange300", 12)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                    ft.Row([icon_text(ico("NIGHTLIGHT_ROUND"), ft.Text(fmt(day.get('moon_rise')), size=10, color="cyan200"), "cyan200", 12), icon_text(ico("NIGHTLIGHT_ROUND"), ft.Text(fmt(day.get('moon_set')), size=10, color="cyan200"), "grey500", 12)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ], spacing=2),
                                bgcolor=CARD_INNER, padding=4, border_radius=6,
                            ),
                            ft.Column([
                                ft.Row([ft.Text("Day", size=11, color="amber200", weight=ft.FontWeight.BOLD), ft.Text(f"💧 {fmt(day.get('day_rain_prob'), '%')}", size=11, color="cyan300", weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Text(day.get("day_summary", ""), size=11, color="grey300", max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                            ], spacing=2),
                            ft.Column([
                                ft.Row([ft.Text("Night", size=11, color="cyan200", weight=ft.FontWeight.BOLD), ft.Text(f"💧 {fmt(day.get('night_rain_prob'), '%')}", size=11, color="cyan300", weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Text(day.get("night_summary", ""), size=11, color="grey300", max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                            ], spacing=2),
                            ft.Container(
                                content=ft.Row([ft.Icon(ft.Icons.TOUCH_APP, size=12, color="amber300"), ft.Text("Tap for details", size=10, color="amber300", weight=ft.FontWeight.W_500)], alignment=ft.MainAxisAlignment.CENTER, spacing=4),
                                bgcolor=CARD_INNER, padding=4, border_radius=6,
                            )
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                        width=230, padding=10, border_radius=14, bgcolor=CARD_INNER,
                    )
                )
            forecast_row.controls = day_cards
            category_cards_column.controls = build_cards_for_category(current_selected_category[0])
            page.update()
        except server.HTTPException as ex:
            # Errors the server raised on purpose, with a message written for people.
            condition_text.value = "Location not found" if ex.status_code == 404 else "Weather unavailable"
            location_display_text.value = f"📍 {ex.detail}"
            page.update()
        except Exception:
            # A real bug (for example in how the screen is drawn): log it, and don't blame the location.
            logging.exception("Failed while loading or drawing weather")
            condition_text.value = "Something went wrong"
            location_display_text.value = "📍 The weather loaded but couldn't be displayed. Please try again."
            page.update()

    location_input.on_submit = load_weather_manual
    sports_input.on_submit = refresh_sports

    search_row = ft.Row([
        location_input,
        ft.IconButton(icon=ft.Icons.SEARCH, on_click=load_weather_manual, icon_color="amber300", tooltip="Search Location"),
        ft.IconButton(icon=ft.Icons.MY_LOCATION, on_click=handle_autodetect_click, icon_color="cyan300", tooltip="Auto-Detect My Location"),
    ], alignment=ft.MainAxisAlignment.CENTER, spacing=2)

    hero_photo_img = ft.Image(src=CONDITION_PHOTOS["sunny"], fit="cover", opacity=0.6, error_content=ft.Container())
    hero_photo_layer = ft.Container(content=hero_photo_img, left=0, top=0, right=0, bottom=0, visible=False)
    hero_scrim = ft.Container(bgcolor="rgba(8, 12, 20, 0.45)", left=0, top=0, right=0, bottom=0, visible=False)
    hero_content = ft.Column([
                ft.Row([
                    ft.Column([widget_loc_text, widget_condition_text], spacing=2, expand=True),
                    ft.Container(content=updated_badge_text, bgcolor="rgba(255, 193, 7, 0.15)", padding=ft.Padding(8, 4, 8, 4), border_radius=12)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.START),
                ft.Row([
                    ft.Column([widget_temp_text, feels_like_text, widget_hl_text], spacing=2),
                    ft.Container(content=ft.Column([widget_hero_icon, widget_moon_text], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER), padding=8)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row([
                    stat_chip(ico("WATER_DROP"), widget_rain_badge, "rgba(0, 229, 255, 0.12)", "cyan200"),
                    stat_chip(ico("WB_SUNNY"), widget_uv_badge, "rgba(255, 152, 0, 0.12)", "orange200"),
                    stat_chip(ico("ECO", "AIR"), widget_aqi_badge, "rgba(76, 175, 80, 0.12)", "green300"),
                    stat_chip(ico("OPACITY", "WATER_DROP"), humidity_text, "rgba(0, 229, 255, 0.08)", "cyan200"),
                    stat_chip(ico("AIR"), wind_text, "rgba(0, 229, 255, 0.08)", "cyan200"),
                ], wrap=True, spacing=8, run_spacing=8),
                data_source_text,
            ], spacing=14)
    hero_stack = ft.Stack([hero_photo_layer, hero_scrim, ft.Container(content=hero_content, padding=20)])

    photorealistic_2x2_widget = ft.Container(
        expand=True, border_radius=24, padding=0, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        gradient=ft.LinearGradient(
            begin=ft.Alignment(-0.8, -1.0), end=ft.Alignment(1.0, 1.0),
            colors=["#1f3b5c", "#16202c", "#2b211a"]
        ),
        border=ft.Border(
            top=ft.BorderSide(1.5, "rgba(255, 255, 255, 0.25)"),
            left=ft.BorderSide(1.5, "rgba(255, 255, 255, 0.20)"),
            right=ft.BorderSide(1.0, "rgba(255, 255, 255, 0.10)"),
            bottom=ft.BorderSide(1.0, "rgba(255, 255, 255, 0.08)"),
        ),
        content=hero_stack,
    )

    praise_mailto = "mailto:thickmooseweather@gmail.com?subject=Thick%20Moose%20Weather%20-%20Suggestions%20%26%20Praise"
    complaints_mailto = "mailto:thickmooseweather@gmail.com?subject=Thick%20Moose%20Weather%20-%20Problems%20%26%20Complaints"

    def feedback_card(icon_name, title, subtitle, color, url):
        return ft.Container(
            content=ft.Column([
                ft.Icon(icon_name, size=26, color=color),
                ft.Text(title, size=13, weight=ft.FontWeight.BOLD, color="white", text_align=ft.TextAlign.CENTER),
                ft.Text(subtitle, size=11, color="grey400", text_align=ft.TextAlign.CENTER),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
            bgcolor=CARD, border=ft.Border.all(1, BORDER), border_radius=14, padding=14,
            expand=True, ink=True, tooltip=title, url=url,
        )

    # ---- Rate / Share ----
    PLAY_STORE_URL = "https://play.google.com/store/apps/details?id=com.thickmooselabs.weather"
    SHARE_URL = "https://weather.thickmooselabs.com"
    SHARE_TEXT = "Try Thick Moose Weather: free, ad-free, hyper-local weather for exactly where you are. " + SHARE_URL
    share_sheet_busy = [False]

    async def _maybe_await(value):
        if inspect.isawaitable(value):
            return await value
        return value

    async def _notify(message):
        try:
            await _maybe_await(page.show_dialog(ft.SnackBar(ft.Text(message))))
        except Exception:
            logging.debug("snackbar unavailable", exc_info=True)

    async def share_app(e=None):
        """Native share sheet if this Flet build has one, else copy the link, else open an email draft."""
        if share_sheet_busy[0]:
            return
        share_sheet_busy[0] = True
        try:
            share_cls = getattr(ft, "Share", None)
            if share_cls is not None:
                try:
                    svc = share_cls()
                    await _maybe_await(svc.share_text(SHARE_TEXT, title="Thick Moose Weather"))
                    return
                except Exception:
                    logging.debug("native share unavailable", exc_info=True)
            clip_cls = getattr(ft, "Clipboard", None)
            try:
                if clip_cls is not None:
                    await _maybe_await(clip_cls().set(SHARE_TEXT))
                else:
                    await _maybe_await(page.set_clipboard(SHARE_TEXT))
                await _notify("Link copied. Paste it into a message to share.")
                return
            except Exception:
                logging.debug("clipboard unavailable", exc_info=True)
            mail = ("mailto:?subject=" + urllib.parse.quote("Thick Moose Weather")
                    + "&body=" + urllib.parse.quote(SHARE_TEXT))
            try:
                await _maybe_await(page.launch_url(mail))
            except Exception:
                logging.debug("mailto fallback failed", exc_info=True)
        finally:
            share_sheet_busy[0] = False

    def action_card(icon, title, subtitle, color, url=None, on_click=None):
        card = feedback_card(icon, title, subtitle, color, url or "")
        if url is None:
            card.url = None
        if on_click is not None:
            card.on_click = on_click
        return card

    feedback_section = ft.Container(
        content=ft.Column([
            ft.Row([
                action_card(ico("STAR_BORDER", "STAR"), "Rate this app", "Leave a review on Google Play", "amber300", url=PLAY_STORE_URL),
                action_card(ico("SHARE"), "Share with friends", "Send the link to someone", "blue300", on_click=share_app),
            ], spacing=12),
            ft.Row([
                feedback_card(ico("FAVORITE_BORDER", "FAVORITE"), "Send feedback", "Suggestions & praise", "green300", praise_mailto),
                feedback_card(ico("BUG_REPORT", "REPORT_PROBLEM"), "Report a problem", "Something look wrong?", "orange300", complaints_mailto),
            ], spacing=12),
        ], spacing=12),
        padding=ft.Padding(0, 10, 0, 30),
    )

    details_card = ft.Container(
        content=ft.Column([
            ft.Row([
                icon_text(ico("WB_TWILIGHT", "WB_SUNNY"), sunrise_text, "amber300"),
                icon_text(ico("WB_TWILIGHT", "WB_SUNNY"), sunset_text, "orange300"),
            ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
            ft.Row([
                icon_text(ico("NIGHTLIGHT_ROUND"), moonrise_text, "cyan200"),
                icon_text(ico("NIGHTLIGHT_ROUND"), moonset_text, "grey500"),
            ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
            ft.Divider(height=6, color=BORDER),
            current_precip_text,
            rain_duration_text,
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
        padding=16, border_radius=16, bgcolor=CARD, border=ft.Border.all(1, BORDER),
    )

    # ---- bottom tabs: Today / Forecast / Explore / More ----
    explore_info = {
        "weather_climate": ("Weather & Climate", ft.Icons.THERMOSTAT, "Alerts, tides, ENSO, local climate"),
        "outdoor_activities": ("Outdoor Activities", ft.Icons.DIRECTIONS_RUN, "Beach, hiking, boating, fishing and more"),
        "lifestyle": ("Lifestyle", ft.Icons.LOCAL_CAFE, "Clothing, UV, air, home, garden"),
        "sporting_event": ("Sporting Events", ft.Icons.SPORTS_SOCCER, "Your teams and game-time weather"),
        "astronomy": ("Astronomy", ft.Icons.NIGHTLIGHT_ROUND, "Moon, planets, dark skies, meteors"),
    }
    explore_title_text = ft.Text("", size=18, weight=ft.FontWeight.BOLD, color="amber300")

    async def scroll_top():
        try:
            await page.scroll_to(offset=0, duration=0)
        except Exception:
            logging.debug("scroll_to unavailable", exc_info=True)

    def open_category(key):
        current_selected_category[0] = key
        label = explore_info.get(key, (key,))[0]
        explore_title_text.value = label
        category_cards_column.controls = build_cards_for_category(key)
        explore_home.visible = False
        explore_detail.visible = True
        page.update()
        page.run_task(scroll_top)

    def close_category(e=None):
        explore_home.visible = True
        explore_detail.visible = False
        page.update()

    def explore_tile(key):
        label, icon, blurb = explore_info[key]
        return ft.Container(
            data=key, expand=True, ink=True, on_click=lambda e, k=key: open_category(k),
            bgcolor=CARD, border=ft.Border.all(1, BORDER), border_radius=16, padding=16,
            content=ft.Column([
                ft.Icon(icon, size=28, color="amber300"),
                ft.Text(label, size=14, weight=ft.FontWeight.BOLD, color="white"),
                ft.Text(blurb, size=11, color=MUTED),
            ], spacing=6),
        )

    _keys = list(explore_info.keys())
    _tile_rows = []
    for i in range(0, len(_keys), 2):
        pair = [explore_tile(k) for k in _keys[i:i + 2]]
        if len(pair) == 1:
            pair.append(ft.Container(expand=True))
        _tile_rows.append(ft.Row(pair, spacing=12))

    explore_home = ft.Column([section_title("Explore")] + _tile_rows, spacing=12, visible=True)
    explore_detail = ft.Column([
        ft.Row([
            ft.IconButton(icon=ico("ARROW_BACK", "KEYBOARD_ARROW_LEFT"), icon_color="amber300", on_click=close_category, tooltip="Back"),
            explore_title_text,
        ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        category_display_container,
    ], spacing=8, visible=False)

    tab_today = ft.Column([
        ft.Row([photorealistic_2x2_widget]),
        ft.Container(height=10),
        details_card,
        ft.Container(height=10),
        radar_container,
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, visible=True)

    tab_forecast = ft.Column([
        section_title("Hourly forecast · next 36 hours"),
        hourly_container,
        section_title("5-day forecast · tap a day for details"),
        forecast_container,
    ], visible=False)

    tab_explore = ft.Column([explore_home, explore_detail], visible=False)

    tab_more = ft.Column([
        ft.Container(height=10),
        ft.Row([keep_weather_free_badge], alignment=ft.MainAxisAlignment.CENTER),
        ft.Container(height=10),
        feedback_section,
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, visible=False)

    tab_views = [tab_today, tab_forecast, tab_explore, tab_more]

    async def on_tab_change(e):
        try:
            idx = int(e.control.selected_index)
        except Exception:
            idx = 0
        for i, view in enumerate(tab_views):
            view.visible = (i == idx)
        if idx == 2:
            explore_home.visible = True      # the Explore tab always opens on its list
            explore_detail.visible = False
        page.update()
        await scroll_top()

    try:
        page.navigation_bar = ft.NavigationBar(
            selected_index=0,
            on_change=on_tab_change,
            destinations=[
                ft.NavigationBarDestination(icon=ico("WB_SUNNY", "HOME"), label="Today"),
                ft.NavigationBarDestination(icon=ico("CALENDAR_MONTH", "SCHEDULE"), label="Forecast"),
                ft.NavigationBarDestination(icon=ico("EXPLORE", "APPS"), label="Explore"),
                ft.NavigationBarDestination(icon=ico("MORE_HORIZ", "MENU"), label="More"),
            ],
        )
    except Exception:
        # If the tab bar can't be built, fall back to one long page so nothing is hidden.
        logging.exception("Navigation bar could not be created")
        for view in tab_views:
            view.visible = True

    full_dashboard = ft.Column([
        app_header,
        search_row,
        location_display_text,
        ft.Container(height=6),
        tab_today,
        tab_forecast,
        tab_explore,
        tab_more,
        ft.Container(height=20),
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    page.add(full_dashboard)

    await asyncio.sleep(0.05)

    saved_teams = await storage_get("tmw_saved_teams")
    if saved_teams is not None:          # "" is a real choice: no teams tracked
        sports_input.value = saved_teams
        page.update()

    # Store builds (Google Play / App Store) open the site with ?app=android or ?app=ios. Their payment
    # rules don't allow outside tip links, so hide the tip badge there. The website keeps it.
    # Remember the marker too, in case a later launch comes in without the query string.
    try:
        seen = " ".join(str(getattr(page, n, "") or "") for n in ("url", "route", "query"))
        if re.search(r"app=(android|ios|store)", seen, re.I):
            await storage_set("tmw_store_app", "1")
        if (await storage_get("tmw_store_app")) == "1":
            keep_weather_free_badge.visible = False
            page.update()
    except Exception:
        logging.debug("Store-mode check failed", exc_info=True)

    loc_mode = await storage_get("tmw_location_mode")
    saved_loc = await storage_get("tmw_saved_location")

    if loc_mode == "manual" and saved_loc and saved_loc.strip():
        location_input.value = saved_loc.strip()
        page.update()
        await load_weather(is_auto=False)
    else:
        await auto_detect_gps()

if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.WEB_BROWSER)