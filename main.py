import flet as ft
import requests

def main(page: ft.Page):
    page.title = "AeroCast Weather & Climate"
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.scroll = ft.ScrollMode.ADAPTIVE
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 20

    # Live Render Backend Endpoint
    API_BASE = "https://weather-app-nrpc.onrender.com"

    # Built-in Sports Directory for Instant Frontend Matching
    SPORTS_CATALOG = {
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

    # --- State Variables ---
    latest_weather_data = {}
    current_selected_category = ["weather_climate"]
    is_widget_mode = [False]

    # --- 2x2 Realistic Widget Controls ---
    widget_loc_text = ft.Text("Wilmington, NC (28401)", size=13, weight=ft.FontWeight.W_600, color="amber200")
    widget_condition_text = ft.Text("Clear Sky", size=14, color="grey300", weight=ft.FontWeight.W_500)
    widget_temp_text = ft.Text("75°", size=54, weight=ft.FontWeight.BOLD, color="white")
    widget_hl_text = ft.Text("H: 88°  L: 69°", size=13, weight=ft.FontWeight.BOLD, color="amber100")
    widget_rain_badge = ft.Text("💧 20% Precip", size=11, color="cyan200", weight=ft.FontWeight.BOLD)
    widget_uv_badge = ft.Text("☀️ UV 5", size=11, color="orange200", weight=ft.FontWeight.BOLD)
    widget_aqi_badge = ft.Text("🍃 AQI 35 (Good)", size=11, color="green300", weight=ft.FontWeight.BOLD)

    # --- Full App Controls ---
    location_input = ft.TextField(
        label="Location (ZIP or City/State)",
        value="28412",
        width=280,
        border_color="amber300",
        focused_border_color="amber200",
    )

    condition_text = ft.Text("Loading weather data...", size=18, weight=ft.FontWeight.BOLD, color="amber200")
    hero_weather_icon = ft.Icon(ft.Icons.WB_SUNNY, size=64, color="amber300")
    curr_temp_text = ft.Text("--°F", size=48, weight=ft.FontWeight.BOLD, color="white")
    feels_like_text = ft.Text("Feels Like: --°F", size=14, color="grey300")
    humidity_text = ft.Text("Humidity: --%", size=13, color="cyan200")
    wind_text = ft.Text("Wind: -- mph", size=13, color="cyan200")
    uv_badge = ft.Text("UV: --", size=13, color="green300", weight=ft.FontWeight.BOLD)
    aqi_badge = ft.Text("AQI: --", size=13, color="green300", weight=ft.FontWeight.BOLD)
    
    # Sun and Moon Metrics Controls
    sunrise_text = ft.Text("🌅 Sunrise: --:-- AM", size=13, color="amber200", weight=ft.FontWeight.W_600)
    sunset_text = ft.Text("🌇 Sunset: --:-- PM", size=13, color="amber200", weight=ft.FontWeight.W_600)
    moonrise_text = ft.Text("🌕 Moonrise: --:-- PM", size=13, color="cyan200", weight=ft.FontWeight.W_600)
    moonset_text = ft.Text("🌑 Moonset: --:-- AM", size=13, color="cyan200", weight=ft.FontWeight.W_600)

    current_precip_text = ft.Text(
        "Precip Now: --% | Next 24h: --%", 
        size=14, 
        color="cyan300", 
        weight=ft.FontWeight.BOLD, 
        text_align=ft.TextAlign.CENTER
    )
    rain_duration_text = ft.Text(
        "No immediate rain expected.", 
        size=13, 
        color="amber100", 
        text_align=ft.TextAlign.CENTER
    )

    # --- Hourly & 5-Day Horizontal Containers ---
    hourly_row = ft.Row([], spacing=10, scroll=ft.ScrollMode.ADAPTIVE)
    hourly_container = ft.Container(
        content=hourly_row,
        padding=10,
        height=175,
        bgcolor="surfaceContainerHigh",
        border_radius=10,
    )

    forecast_row = ft.Row([], alignment=ft.MainAxisAlignment.START, spacing=14, scroll=ft.ScrollMode.ADAPTIVE)
    forecast_container = ft.Container(
        content=forecast_row,
        padding=12,
        height=370,
        bgcolor="surfaceContainerHigh",
        border_radius=10,
    )

    # --- Detailed Activity Category Cards ---
    category_cards_row = ft.Row(
        wrap=True, 
        spacing=14, 
        run_spacing=14,
        vertical_alignment=ft.CrossAxisAlignment.START
    )
    category_display_container = ft.Container(
        content=category_cards_row,
        padding=15,
        bgcolor="surfaceContainerHigh",
        border_radius=10,
    )

    def create_subcat_cards(data_dict, category_key=""):
        cards = []
        if not data_dict or not isinstance(data_dict, dict):
            return [ft.Text("No data available for this category.", color="grey400", size=13)]

        data_to_render = dict(data_dict)
        
        # Moon Timing Box
        if "moon_rise" in data_to_render or "moon_set" in data_to_render:
            m_rise = data_to_render.pop("moon_rise", "--")
            m_set = data_to_render.pop("moon_set", "--")
            cards.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text("Moon Timing", size=14, weight=ft.FontWeight.BOLD, color="amber300"),
                        ft.Divider(height=6, color="grey800"),
                        ft.Row([
                            ft.Text("🌕 Rise:", size=13, color="cyan200", weight=ft.FontWeight.W_500),
                            ft.Text(str(m_rise), size=13, color="white", weight=ft.FontWeight.BOLD),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([
                            ft.Text("🌑 Set:", size=13, color="cyan200", weight=ft.FontWeight.W_500),
                            ft.Text(str(m_set), size=13, color="white", weight=ft.FontWeight.BOLD),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ], spacing=6),
                    bgcolor="#252830",
                    border_radius=8,
                    padding=14,
                    width=250,
                )
            )

        for key, val in data_to_render.items():
            title = key.replace("_", " ").title()

            # 1. Custom High-Readability Formatter for Fishing
            if key == "fishing" and isinstance(val, dict):
                f_score = val.get("score", "--")
                f_details = val.get("details", "")
                lines = [seg.strip() for seg in f_details.split(".") if seg.strip()]
                
                fishing_controls = [
                    ft.Row([
                        ft.Icon(ft.Icons.PHISHING, size=18, color="cyan300"),
                        ft.Text("Fishing Outlook", size=14, weight=ft.FontWeight.BOLD, color="amber300"),
                    ], spacing=8),
                    ft.Divider(height=6, color="grey800"),
                    ft.Container(
                        content=ft.Row([
                            ft.Text("Activity Score:", size=12, color="grey300", weight=ft.FontWeight.W_500),
                            ft.Text(f"{f_score}/100 (Prime)", size=13, color="green300", weight=ft.FontWeight.BOLD),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        bgcolor="#1c1f26",
                        padding=8,
                        border_radius=6
                    ),
                    ft.Divider(height=4, color="transparent")
                ]
                for l in lines:
                    fishing_controls.append(
                        ft.Row([
                            ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=13, color="amber200"),
                            ft.Text(l, size=12, color="white", expand=True),
                        ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.START)
                    )

                cards.append(
                    ft.Container(
                        content=ft.Column(fishing_controls, spacing=6),
                        bgcolor="#252830",
                        border_radius=8,
                        padding=14,
                        width=320,
                    )
                )

            # 2. Sporting Events with Smart Team Lookup
            elif (key == "events" or category_key == "sporting_event") and isinstance(val, list):
                def add_custom_team(e):
                    team_raw = team_input.value.strip().lower()
                    if team_raw:
                        matched = False
                        for catalog_k, info in SPORTS_CATALOG.items():
                            if catalog_k in team_raw or team_raw in catalog_k:
                                val.append({
                                    "title": info[0],
                                    "venue": info[1],
                                    "time": info[2],
                                    "conditions": info[3]
                                })
                                matched = True
                                break
                        
                        if not matched:
                            val.append({
                                "title": team_input.value.strip().title(),
                                "venue": "Regional Stadium / Arena",
                                "time": "Upcoming Matchup",
                                "conditions": f"{latest_weather_data.get('current', {}).get('temp', 75)}°F, {latest_weather_data.get('current', {}).get('condition', 'Fair')}"
                            })

                        team_input.value = ""
                        render_active_category()

                team_input = ft.TextField(
                    hint_text="Add Team (e.g. Duke, Panthers, Braves)",
                    width=220,
                    height=38,
                    text_size=12,
                    content_padding=8,
                    on_submit=add_custom_team
                )
                add_btn = ft.IconButton(
                    icon=ft.Icons.ADD_CIRCLE, 
                    icon_color="amber300", 
                    on_click=add_custom_team,
                    tooltip="Add Team"
                )

                event_controls = [
                    ft.Row([
                        ft.Icon(ft.Icons.SPORTS_FOOTBALL, size=18, color="amber300"),
                        ft.Text("Tracked Sports Teams", size=14, weight=ft.FontWeight.BOLD, color="amber300"),
                    ], spacing=8),
                    ft.Row([team_input, add_btn], spacing=4),
                    ft.Divider(height=6, color="grey800"),
                ]
                for ev in val:
                    if isinstance(ev, dict):
                        ev_title = ev.get("title", "Game Event")
                        ev_venue = ev.get("venue", "--")
                        ev_time = ev.get("time", "--")
                        ev_cond = ev.get("conditions", "--")
                        
                        event_box = ft.Container(
                            content=ft.Column([
                                ft.Row([
                                    ft.Text(f"🏆 {ev_title}", size=13, weight=ft.FontWeight.BOLD, color="amber200"),
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Text(f"📍 Venue: {ev_venue}", size=12, color="white"),
                                ft.Text(f"⏰ Schedule: {ev_time}", size=12, color="cyan200"),
                                ft.Text(f"🌤 Game Weather: {ev_cond}", size=12, color="green200", weight=ft.FontWeight.W_500),
                            ], spacing=3),
                            bgcolor="#1c1f26",
                            padding=10,
                            border_radius=6,
                        )
                        event_controls.append(event_box)
                    else:
                        event_controls.append(ft.Text(f"• {str(ev)}", size=12, color="white"))

                cards.append(
                    ft.Container(
                        content=ft.Column(event_controls, spacing=8),
                        bgcolor="#252830",
                        border_radius=8,
                        padding=14,
                        width=320,
                    )
                )

            # 3. Planting & Harvest
            elif ("planting" in key or "harvest" in key) and isinstance(val, list):
                plant_controls = [
                    ft.Row([
                        ft.Icon(ft.Icons.GRASS, size=18, color="green300"),
                        ft.Text(title, size=14, weight=ft.FontWeight.BOLD, color="amber300"),
                    ], spacing=8),
                    ft.Divider(height=6, color="grey800"),
                ]
                for p_item in val:
                    if isinstance(p_item, dict):
                        c_name = p_item.get("item", "Plant")
                        c_act = p_item.get("action", "")
                        c_tim = p_item.get("timing", "")
                        
                        plant_controls.append(
                            ft.Container(
                                content=ft.Column([
                                    ft.Text(f"🌱 {c_name}", size=13, weight=ft.FontWeight.BOLD, color="green200"),
                                    ft.Text(f"• Action: {c_act}", size=12, color="white"),
                                    ft.Text(f"• Window: {c_tim}", size=11, color="amber100"),
                                ], spacing=2),
                                bgcolor="#1c1f26",
                                padding=8,
                                border_radius=6,
                            )
                        )
                    else:
                        plant_controls.append(ft.Text(f"• {str(p_item)}", size=12, color="white"))
                
                cards.append(
                    ft.Container(
                        content=ft.Column(plant_controls, spacing=8),
                        bgcolor="#252830",
                        border_radius=8,
                        padding=14,
                        width=300,
                    )
                )

            # 4. Celestial Events
            elif key == "celestial_events" and isinstance(val, list):
                event_controls = [
                    ft.Text("Celestial Events", size=15, weight=ft.FontWeight.BOLD, color="amber300"),
                    ft.Divider(height=6, color="grey800"),
                ]
                for idx, ev in enumerate(val):
                    if isinstance(ev, dict):
                        ev_title = ev.get("title", f"Event #{idx+1}")
                        ev_win = ev.get("window", "--")
                        ev_dir = ev.get("direction", "--")
                        ev_notes = ev.get("notes", "")
                        
                        event_box = ft.Container(
                            content=ft.Column([
                                ft.Text(ev_title, size=13, weight=ft.FontWeight.BOLD, color="amber200"),
                                ft.Text(f"⏰ Window: {ev_win}", size=12, color="white"),
                                ft.Text(f"🧭 Direction: {ev_dir}", size=12, color="grey300"),
                                ft.Text(f"📝 Notes: {ev_notes}", size=11, color="cyan100") if ev_notes else ft.Container(),
                            ], spacing=2),
                            bgcolor="#1c1f26",
                            padding=10,
                            border_radius=6,
                        )
                        event_controls.append(event_box)
                    else:
                        event_controls.append(ft.Text(f"• {str(ev)}", size=12, color="white"))
                
                cards.append(
                    ft.Container(
                        content=ft.Column(event_controls, spacing=8),
                        bgcolor="#252830",
                        border_radius=8,
                        padding=14,
                        width=360,
                    )
                )

            # 5. Visible Planets
            elif key == "visible_planets" and isinstance(val, list):
                planet_items = [
                    ft.Text("Visible Planets", size=14, weight=ft.FontWeight.BOLD, color="amber300"),
                    ft.Divider(height=6, color="grey800"),
                ]
                for p in val:
                    planet_items.append(
                        ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.Icons.BRIGHTNESS_LOW, size=14, color="amber200"),
                                ft.Text(str(p), size=12, color="white", weight=ft.FontWeight.W_500),
                            ], spacing=6),
                            padding=ft.Padding(0, 2, 0, 2)
                        )
                    )
                cards.append(
                    ft.Container(
                        content=ft.Column(planet_items, spacing=4),
                        bgcolor="#252830",
                        border_radius=8,
                        padding=14,
                        width=280,
                    )
                )

            # 6. Nested Activity/Lifestyle Dictionaries (High Readability)
            elif isinstance(val, dict):
                content_col = [
                    ft.Text(title, size=14, weight=ft.FontWeight.BOLD, color="amber300"),
                    ft.Divider(height=6, color="grey800")
                ]
                for sub_k, sub_v in val.items():
                    sub_title = sub_k.replace("_", " ").title()
                    if isinstance(sub_v, dict):
                        content_col.append(ft.Text(f"{sub_title}:", size=12, color="amber100", weight=ft.FontWeight.BOLD))
                        for kk, vv in sub_v.items():
                            content_col.append(ft.Text(f"  • {kk.replace('_', ' ').title()}: {vv}", size=11, color="white"))
                    elif isinstance(sub_v, list):
                        content_col.append(ft.Text(f"{sub_title}:", size=12, color="amber100", weight=ft.FontWeight.BOLD))
                        for item in sub_v:
                            content_col.append(ft.Text(f"  • {item}", size=11, color="white"))
                    else:
                        str_val = str(sub_v)
                        if len(str_val) > 20 or sub_k.lower() in ["details", "description", "summary", "notes", "conditions"]:
                            content_col.append(
                                ft.Column([
                                    ft.Text(f"{sub_title}:", size=12, color="cyan200", weight=ft.FontWeight.BOLD),
                                    ft.Text(str_val, size=12, color="white", weight=ft.FontWeight.W_400),
                                ], spacing=2)
                            )
                        else:
                            content_col.append(
                                ft.Row([
                                    ft.Text(f"{sub_title}:", size=12, color="grey300", weight=ft.FontWeight.W_500),
                                    ft.Text(str_val, size=12, color="white", weight=ft.FontWeight.BOLD),
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                            )
                            
                cards.append(
                    ft.Container(
                        content=ft.Column(content_col, spacing=6),
                        bgcolor="#252830",
                        border_radius=8,
                        padding=14,
                        width=300,
                    )
                )

            # 7. Standard Text Cards
            else:
                cards.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Text(title, size=13, weight=ft.FontWeight.BOLD, color="amber200"),
                            ft.Divider(height=6, color="grey800"),
                            ft.Text(str(val), size=13, color="white", selectable=True),
                        ], spacing=4),
                        bgcolor="#252830",
                        border_radius=8,
                        padding=14,
                        width=270,
                    )
                )

        return cards

    def render_active_category():
        key = current_selected_category[0]
        cat_data = latest_weather_data.get(key, {})
        category_cards_row.controls = create_subcat_cards(cat_data, category_key=key)
        category_cards_row.update()

    def on_category_click(cat_key):
        current_selected_category[0] = cat_key
        for chip in category_buttons_row.controls:
            is_active = (chip.data == cat_key)
            chip.bgcolor = "amber400" if is_active else "#252830"
            chip_text = chip.content.controls[1]
            chip_icon = chip.content.controls[0]
            chip_text.color = "black" if is_active else "white"
            chip_icon.color = "black" if is_active else "amber200"
            chip.update()
        render_active_category()

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
            on_click=lambda e, k=key: on_category_click(k),
            ink=True,
            padding=ft.Padding(16, 10, 16, 10),
            border_radius=20,
            bgcolor="amber400" if is_active else "#252830",
            content=ft.Row([
                ft.Icon(icon, size=18, color="black" if is_active else "amber200"),
                ft.Text(label, size=13, weight=ft.FontWeight.BOLD, color="black" if is_active else "white"),
            ], spacing=8, alignment=ft.MainAxisAlignment.CENTER),
        )
        category_chips.append(chip)

    category_buttons_row = ft.Row(controls=category_chips, spacing=10, scroll=ft.ScrollMode.ADAPTIVE)

    # 5-Day Details Popup Dialog
    def open_day_details(e, day_data):
        def close_dlg(e):
            dlg.open = False
            page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Detailed Outlook: {day_data.get('date', 'Forecast')}"),
            content=ft.Column([
                ft.Text(f"High: {day_data.get('high', '--')}°F | Low: {day_data.get('low', '--')}°F", weight=ft.FontWeight.BOLD, color="amber200"),
                ft.Divider(),
                ft.Text(f"Daytime: {day_data.get('day_summary', 'No summary available')} (Precip: {day_data.get('day_rain_prob', 0)}%)"),
                ft.Text(f"Nighttime: {day_data.get('night_summary', 'No summary available')} (Precip: {day_data.get('night_rain_prob', 0)}%)"),
                ft.Divider(),
                ft.Row([
                    ft.Text(f"🌅 Rise: {day_data.get('sunrise', '--')}", size=12, color="amber200"),
                    ft.Text(f"🌇 Set: {day_data.get('sunset', '--')}", size=12, color="amber200"),
                ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                ft.Row([
                    ft.Text(f"🌕 Rise: {day_data.get('moon_rise', '--')}", size=12, color="cyan200"),
                    ft.Text(f"🌑 Set: {day_data.get('moon_set', '--')}", size=12, color="cyan200"),
                ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
            ], height=240, scroll=ft.ScrollMode.ADAPTIVE),
            actions=[ft.TextButton("Close", on_click=close_dlg)]
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    # --- Mode Switcher (Widget <-> Full App) ---
    def switch_to_full_app(e=None):
        widget_wrapper.visible = False
        full_dashboard.visible = True
        is_widget_mode[0] = False
        page.update()

    def switch_to_widget_only(e=None):
        widget_wrapper.visible = True
        full_dashboard.visible = False
        is_widget_mode[0] = True
        page.update()

    # --- Load Data from Render Backend ---
    def load_weather(e=None):
        loc = location_input.value.strip() or "28401"
        try:
            response = requests.get(f"{API_BASE}/weather?query={loc}", timeout=15)
            
            if response.status_code == 200:
                res = response.json()
                latest_weather_data.clear()
                latest_weather_data.update(res)

                curr = res.get("current", {})
                condition = curr.get("condition", "Clear")
                
                temp_raw = curr.get('temp')
                t_val = temp_raw.get('val', '--') if isinstance(temp_raw, dict) else (temp_raw if temp_raw is not None else '--')

                feels_raw = curr.get('feels_like')
                if isinstance(feels_raw, dict):
                    f_val = feels_raw.get('temp', feels_raw.get('val', curr.get('temp', '--')))
                elif feels_raw is not None:
                    f_val = str(feels_raw)
                else:
                    f_val = curr.get('temp', '--')

                # Dynamic Sun vs Moon icon based on is_night
                is_night_time = curr.get("is_night", False) or datetime.now().hour < 7 or datetime.now().hour >= 19
                if is_night_time:
                    hero_weather_icon.name = ft.Icons.NIGHTLIGHT_ROUND
                    hero_weather_icon.color = "cyan200"
                else:
                    hero_weather_icon.name = ft.Icons.WB_SUNNY
                    hero_weather_icon.color = "amber300"

                # Update Full App Current Status
                condition_text.value = condition
                curr_temp_text.value = f"{t_val}°F"
                feels_like_text.value = f"Feels Like: {f_val}°F"
                humidity_text.value = f"Humidity: {curr.get('humidity', '--')}%"
                wind_text.value = f"Wind: {curr.get('wind', '--')} mph"
                uv_badge.value = f"UV: {curr.get('uv_index', '--')}"
                
                # Render Clean Sunrise, Sunset, Moonrise, and Moonset
                s_rise_val = curr.get("sunrise") or res.get("astronomy", {}).get("sunrise", "06:57 AM")
                s_set_val = curr.get("sunset") or res.get("astronomy", {}).get("sunset", "07:12 PM")
                m_rise_val = curr.get("moon_rise") or res.get("astronomy", {}).get("moon_rise", "07:20 PM")
                m_set_val = curr.get("moon_set") or res.get("astronomy", {}).get("moon_set", "06:35 AM")

                sunrise_text.value = f"🌅 Sunrise: {s_rise_val}"
                sunset_text.value = f"🌇 Sunset: {s_set_val}"
                moonrise_text.value = f"🌕 Moonrise: {m_rise_val}"
                moonset_text.value = f"🌑 Moonset: {m_set_val}"

                aqi_data = res.get("aqi", {})
                aqi_val = aqi_data.get('aqi', '--') if isinstance(aqi_data, dict) else str(aqi_data)
                aqi_cat = aqi_data.get('category', 'Good') if isinstance(aqi_data, dict) else ""
                aqi_badge.value = f"AQI: {aqi_val} ({aqi_cat})"

                precip_sum = curr.get("precip_summary")
                rain_dur = curr.get("rain_duration")
                current_precip_text.value = precip_sum if precip_sum else "Precip Now: 0% | Next 24h: 0%"
                rain_duration_text.value = rain_dur if rain_dur else "No immediate rain expected."

                # Update 2x2 Realistic Widget Controls
                widget_loc_text.value = res.get("location_name", f"Wilmington, NC ({loc})")
                widget_condition_text.value = condition
                widget_temp_text.value = f"{t_val}°"
                widget_uv_badge.value = f"☀️ UV {curr.get('uv_index', '--')}"
                widget_aqi_badge.value = f"🍃 AQI {aqi_val}"

                daily_data = res.get("daily") or res.get("forecast") or []
                if daily_data:
                    first_day = daily_data[0]
                    widget_hl_text.value = f"H: {first_day.get('high', '--')}°  L: {first_day.get('low', '--')}°"
                    widget_rain_badge.value = f"💧 {first_day.get('rain_prob_max', '0')}% Precip"

                # 1. Build Hourly Cards
                hourly_data = res.get("hourly_36", [])
                hour_cards = []
                for item in hourly_data:
                    h_time = item.get("time") or item.get("hour") or "--"
                    h_temp = item.get("temp", "--")
                    h_pop = item.get("rain_chance", item.get("pop", 0))
                    pop_val = int(h_pop) if str(h_pop).isdigit() else 0
                    pop_color = "cyan300" if pop_val >= 30 else "grey400"

                    is_night = item.get("is_night", False) or ("PM" in str(h_time) and int(str(h_time).split()[0]) >= 7) or ("AM" in str(h_time) and int(str(h_time).split()[0]) <= 6)
                    h_icon = ft.Icons.NIGHTLIGHT_ROUND if is_night else ft.Icons.WB_SUNNY
                    h_icon_color = "cyan200" if is_night else "amber300"

                    hour_cards.append(
                        ft.Container(
                            content=ft.Column([
                                ft.Text(str(h_time), size=12, color="amber200", weight=ft.FontWeight.BOLD),
                                ft.Icon(h_icon, size=22, color=h_icon_color),
                                ft.Text(f"{h_temp}°", size=14, weight=ft.FontWeight.BOLD, color="white"),
                                ft.Row([
                                    ft.Icon(ft.Icons.WATER_DROP, size=11, color=pop_color),
                                    ft.Text(f"{h_pop}%", size=11, color=pop_color),
                                ], alignment=ft.MainAxisAlignment.CENTER),
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                            width=85,
                            height=140,
                            padding=8,
                            border_radius=8,
                            bgcolor="#252830",
                        )
                    )
                hourly_row.controls = hour_cards

                # 2. Build Proportional, Balanced 5-Day Cards
                day_cards = []
                for day in daily_data:
                    rain_pct = day.get("rain_prob_max", 0)
                    prob_color = "cyan300" if rain_pct >= 30 else "grey400"
                    
                    day_rain = day.get("day_rain_prob", rain_pct)
                    night_rain = day.get("night_rain_prob", max(5, round(rain_pct * 0.4)))
                    day_rain_color = "cyan300" if day_rain >= 30 else "grey400"
                    night_rain_color = "cyan300" if night_rain >= 30 else "grey400"
                    
                    d_sunrise = day.get("sunrise", s_rise_val)
                    d_sunset = day.get("sunset", s_set_val)
                    d_moonrise = day.get("moon_rise", "--")
                    d_moonset = day.get("moon_set", "--")

                    day_cards.append(
                        ft.Container(
                            on_click=lambda e, d=day: open_day_details(e, d),
                            ink=True,
                            content=ft.Column([
                                # Date Title
                                ft.Text(day.get("date", ""), size=13, weight=ft.FontWeight.BOLD, color="amber200", text_align=ft.TextAlign.CENTER),
                                
                                # High & Low Temperatures
                                ft.Container(
                                    content=ft.Row([
                                        ft.Row([
                                            ft.Icon(ft.Icons.ARROW_UPWARD, size=13, color="red400"),
                                            ft.Text(f"{day.get('high', '--')}°", size=14, weight=ft.FontWeight.BOLD, color="red300"),
                                        ], spacing=3),
                                        ft.Row([
                                            ft.Icon(ft.Icons.ARROW_DOWNWARD, size=13, color="blue400"),
                                            ft.Text(f"{day.get('low', '--')}°", size=14, weight=ft.FontWeight.BOLD, color="blue300"),
                                        ], spacing=3),
                                    ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                                    bgcolor="#1c1f26",
                                    padding=ft.Padding(10, 5, 10, 5),
                                    border_radius=6,
                                ),

                                # Sun & Moon Timing Box
                                ft.Container(
                                    content=ft.Column([
                                        ft.Row([
                                            ft.Text(f"🌅 {d_sunrise}", size=11, color="amber100", weight=ft.FontWeight.W_500),
                                            ft.Text(f"🌇 {d_sunset}", size=11, color="amber100", weight=ft.FontWeight.W_500),
                                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                        ft.Row([
                                            ft.Text(f"🌕 {d_moonrise}", size=11, color="cyan200", weight=ft.FontWeight.W_500),
                                            ft.Text(f"🌑 {d_moonset}", size=11, color="cyan200", weight=ft.FontWeight.W_500),
                                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                    ], spacing=3),
                                    bgcolor="#1c1f26",
                                    padding=ft.Padding(8, 5, 8, 5),
                                    border_radius=6,
                                ),

                                # Day Section: Description + Day Precip %
                                ft.Column([
                                    ft.Row([
                                        ft.Row([
                                            ft.Icon(ft.Icons.WB_SUNNY, size=14, color="amber300"),
                                            ft.Text("Daytime", size=11, weight=ft.FontWeight.BOLD, color="amber200"),
                                        ], spacing=4),
                                        ft.Row([
                                            ft.Icon(ft.Icons.WATER_DROP, size=11, color=day_rain_color),
                                            ft.Text(f"{day_rain}%", size=11, color=day_rain_color, weight=ft.FontWeight.BOLD),
                                        ], spacing=2),
                                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                    ft.Text(f"{day.get('day_summary', '')}", size=11, color="grey200"),
                                ], spacing=3),

                                # Night Section: Description + Night Precip %
                                ft.Column([
                                    ft.Row([
                                        ft.Row([
                                            ft.Icon(ft.Icons.NIGHTLIGHT_ROUND, size=14, color="cyan200"),
                                            ft.Text("Nighttime", size=11, weight=ft.FontWeight.BOLD, color="cyan200"),
                                        ], spacing=4),
                                        ft.Row([
                                            ft.Icon(ft.Icons.WATER_DROP, size=11, color=night_rain_color),
                                            ft.Text(f"{night_rain}%", size=11, color=night_rain_color, weight=ft.FontWeight.BOLD),
                                        ], spacing=2),
                                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                    ft.Text(f"{day.get('night_summary', '')}", size=11, color="grey300"),
                                ], spacing=3),

                                ft.Divider(height=2, color="transparent"),

                                # Anchored 24h Total Rain Badge
                                ft.Container(
                                    content=ft.Row([
                                        ft.Icon(ft.Icons.UMBRELLA, size=13, color=prob_color),
                                        ft.Text(f"Total 24-Hour Rain Chance: {rain_pct}%", size=11, color=prob_color, weight=ft.FontWeight.BOLD),
                                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=5),
                                    bgcolor="#1c1f26",
                                    padding=ft.Padding(8, 5, 8, 5),
                                    border_radius=6,
                                ),

                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                            width=240,
                            padding=12,
                            border_radius=10,
                            bgcolor="#252830",
                        )
                    )
                forecast_row.controls = day_cards

                # 3. Populate Categories
                cat_key = current_selected_category[0]
                category_cards_row.controls = create_subcat_cards(res.get(cat_key, {}), category_key=cat_key)

                page.update()
            else:
                condition_text.value = f"Server Error: Status {response.status_code}"
                page.update()
        except Exception as ex:
            condition_text.value = f"Connection Error: {ex}"
            page.update()
    location_input.on_submit = load_weather

    # --- 2x2 Photorealistic Widget Component ---
    photorealistic_2x2_widget = ft.Container(
        on_click=switch_to_full_app,
        ink=True,
        width=320,
        height=320,
        border_radius=28,
        padding=20,
        gradient=ft.LinearGradient(
            begin=ft.Alignment(-0.8, -1.0),
            end=ft.Alignment(1.0, 1.0),
            colors=[
                "#1a2639",
                "#16202c",
                "#2b211a",
            ]
        ),
        border=ft.Border(
            top=ft.BorderSide(1.5, "rgba(255, 255, 255, 0.25)"),
            left=ft.BorderSide(1.5, "rgba(255, 255, 255, 0.20)"),
            right=ft.BorderSide(1.0, "rgba(255, 255, 255, 0.10)"),
            bottom=ft.BorderSide(1.0, "rgba(255, 255, 255, 0.08)"),
        ),
        shadow=ft.BoxShadow(
            spread_radius=2,
            blur_radius=25,
            color="rgba(0, 0, 0, 0.65)",
            offset=ft.Offset(0, 10),
        ),
        content=ft.Column([
            ft.Row([
                ft.Column([
                    widget_loc_text,
                    widget_condition_text,
                ], spacing=2),
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.NEAR_ME, size=12, color="amber300"),
                        ft.Text("LIVE", size=10, weight=ft.FontWeight.BOLD, color="amber300"),
                    ], spacing=4),
                    bgcolor="rgba(255, 193, 7, 0.15)",
                    padding=ft.Padding(8, 4, 8, 4),
                    border_radius=12,
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

            ft.Divider(height=10, color=ft.Colors.TRANSPARENT),

            ft.Row([
                widget_temp_text,
                ft.Container(
                    content=ft.Icon(ft.Icons.WB_TWILIGHT, size=62, color="amber300"),
                    padding=10,
                    border_radius=50,
                    bgcolor="rgba(255, 193, 7, 0.12)",
                    shadow=ft.BoxShadow(
                        blur_radius=30,
                        color="rgba(255, 179, 0, 0.35)",
                    )
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),

            widget_hl_text,

            ft.Divider(height=10, color=ft.Colors.TRANSPARENT),

            ft.Row([
                ft.Container(
                    content=widget_rain_badge,
                    bgcolor="rgba(0, 229, 255, 0.12)",
                    padding=ft.Padding(8, 4, 8, 4),
                    border_radius=10,
                ),
                ft.Container(
                    content=widget_uv_badge,
                    bgcolor="rgba(255, 152, 0, 0.12)",
                    padding=ft.Padding(8, 4, 8, 4),
                    border_radius=10,
                ),
                ft.Container(
                    content=widget_aqi_badge,
                    bgcolor="rgba(76, 175, 80, 0.12)",
                    padding=ft.Padding(8, 4, 8, 4),
                    border_radius=10,
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

            ft.Divider(height=4, color=ft.Colors.TRANSPARENT),

            ft.Row([
                ft.Icon(ft.Icons.TOUCH_APP, size=13, color="grey400"),
                ft.Text("Tap to open full AeroCast suite", size=11, color="grey400", weight=ft.FontWeight.W_500),
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=4)
        ], spacing=4)
    )

    widget_wrapper = ft.Column([
        ft.Text("AeroCast 2x2 Photorealistic Home Widget", size=15, weight=ft.FontWeight.BOLD, color="amber200"),
        ft.Text("Matches Android 2x2 grid dimension • Tap card to open full app", size=12, color="grey400"),
        ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
        photorealistic_2x2_widget,
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER)

    # --- Full Dashboard Container ---
    search_bar = ft.Row([
        location_input,
        ft.Row([
            ft.IconButton(icon=ft.Icons.SEARCH, on_click=load_weather, icon_color="amber300", tooltip="Search location"),
            ft.IconButton(icon=ft.Icons.WIDGETS, on_click=switch_to_widget_only, icon_color="cyan300", tooltip="Switch to 2x2 Widget Mode"),
        ], spacing=4)
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    current_weather_card = ft.Container(
        content=ft.Column([
            ft.Column([
                condition_text,
                ft.Row([
                    hero_weather_icon,
                    curr_temp_text,
                ], spacing=20, alignment=ft.MainAxisAlignment.CENTER),
                feels_like_text,
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5),
            
            ft.Divider(height=12, color=ft.Colors.TRANSPARENT),
            # Metrics Row 1: Humidity, Wind, AQI, UV
            ft.Row([humidity_text, wind_text, aqi_badge, uv_badge], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            
            ft.Divider(height=6, color=ft.Colors.TRANSPARENT),
            # Metrics Row 2: Sun & Moon Timings
            ft.Row([sunrise_text, sunset_text], alignment=ft.MainAxisAlignment.CENTER, spacing=25),
            ft.Row([moonrise_text, moonset_text], alignment=ft.MainAxisAlignment.CENTER, spacing=25),
            
            ft.Divider(height=8, color=ft.Colors.TRANSPARENT),
            
            ft.Column([
                ft.Row([current_precip_text], alignment=ft.MainAxisAlignment.CENTER),
                ft.Row([rain_duration_text], alignment=ft.MainAxisAlignment.CENTER),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
        ]),
        padding=20,
        border_radius=10,
        bgcolor="surfaceContainerHigh"
    )

    full_dashboard = ft.Column([
        search_bar,
        ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
        current_weather_card,
        ft.Divider(height=15, color=ft.Colors.TRANSPARENT),
        ft.Text("Hourly Forecast (Next 36 Hours)", size=16, weight=ft.FontWeight.BOLD, color="amber200"),
        hourly_container,
        ft.Divider(height=15, color=ft.Colors.TRANSPARENT),
        ft.Text("5-Day Forecast (Click any card for detailed metrics)", size=16, weight=ft.FontWeight.BOLD, color="amber200"),
        ft.Row([forecast_container], alignment=ft.MainAxisAlignment.START),
        ft.Divider(height=15, color=ft.Colors.TRANSPARENT),
        ft.Text("Detailed Activity & Lifestyle Indices", size=16, weight=ft.FontWeight.BOLD, color="amber200"),
        category_buttons_row,
        ft.Divider(height=5, color=ft.Colors.TRANSPARENT),
        category_display_container,
    ], visible=True)

    page.add(
        widget_wrapper,
        ft.Divider(height=25, color="grey800"),
        ft.Container(
            content=full_dashboard,
            width=850,
            alignment=ft.Alignment(0, 0),
        ),
    )

    load_weather()

if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.WEB_BROWSER)