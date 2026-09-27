import flet as ft
from datetime import datetime

async def main(page: ft.Page):
    page.title = "Thick Moose Weather"
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.scroll = ft.ScrollMode.ADAPTIVE
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 16

    latest_weather_data = {}
    current_selected_category = ["weather_climate"]

    # 2x2 Realistic Widget Controls
    widget_loc_text = ft.Text("Wilmington (28412 / Lords Creek), NC", size=13, weight=ft.FontWeight.W_600, color="amber200")
    widget_condition_text = ft.Text("Sunny", size=14, color="grey300", weight=ft.FontWeight.W_500)
    widget_hero_icon = ft.Icon(ft.Icons.WB_SUNNY, size=62, color="amber300")
    widget_temp_text = ft.Text("74°", size=54, weight=ft.FontWeight.BOLD, color="white")
    widget_hl_text = ft.Text("H: 80°  L: 53°", size=13, weight=ft.FontWeight.BOLD, color="amber100")
    widget_rain_badge = ft.Text("💧 0% Precip", size=11, color="cyan200", weight=ft.FontWeight.BOLD)
    widget_uv_badge = ft.Text("☀️ UV 4", size=11, color="orange200", weight=ft.FontWeight.BOLD)
    widget_aqi_badge = ft.Text("🍃 AQI 32 (Good)", size=11, color="green300", weight=ft.FontWeight.BOLD)

    # Location Input Bar
    location_input = ft.TextField(
        label="Location (ZIP or City)",
        value="28412",
        width=260,
        border_color="amber300",
        focused_border_color="amber200",
    )

    # Sports Custom Team Input Bar (Dedicated for Sporting Events Tab)
    sports_input = ft.TextField(
        label="Enter Teams (e.g. Panthers, Braves, Wolfpack)",
        value="Panthers, Braves",
        expand=True,
        border_color="amber300",
        focused_border_color="amber200",
        dense=True
    )

    location_display_text = ft.Text("📍 Wilmington (28412 / Lords Creek), NC", size=14, color="cyan200", weight=ft.FontWeight.W_600)
    condition_text = ft.Text("Loading weather data...", size=18, weight=ft.FontWeight.BOLD, color="amber200")
    hero_weather_icon = ft.Icon(ft.Icons.WB_SUNNY, size=64, color="amber300")
    curr_temp_text = ft.Text("--°F", size=48, weight=ft.FontWeight.BOLD, color="white")
    feels_like_text = ft.Text("Feels Like: --°F", size=14, color="grey300")
    humidity_text = ft.Text("Humidity: --%", size=13, color="cyan200")
    wind_text = ft.Text("Wind: -- mph", size=13, color="cyan200")
    uv_badge = ft.Text("UV: --", size=13, color="green300", weight=ft.FontWeight.BOLD)
    aqi_badge = ft.Text("AQI: --", size=13, color="green300", weight=ft.FontWeight.BOLD)

    sunrise_text = ft.Text("🌅 Sunrise: --:-- AM", size=13, color="amber200", weight=ft.FontWeight.W_600)
    sunset_text = ft.Text("🌇 Sunset: --:-- PM", size=13, color="amber200", weight=ft.FontWeight.W_600)
    moonrise_text = ft.Text("🌕 Moonrise: --:-- PM", size=13, color="cyan200", weight=ft.FontWeight.W_600)
    moonset_text = ft.Text("🌑 Moonset: --:-- AM", size=13, color="cyan200", weight=ft.FontWeight.W_600)

    current_precip_text = ft.Text("Precip Now: 0% | Next 24h Max: 0%", size=14, color="cyan300", weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)
    rain_duration_text = ft.Text("Zero precipitation expected.", size=13, color="amber100", text_align=ft.TextAlign.CENTER)

    hourly_row = ft.Row([], spacing=10, scroll=ft.ScrollMode.ADAPTIVE)
    hourly_container = ft.Container(content=hourly_row, padding=10, height=175, bgcolor="surfaceContainerHigh", border_radius=10)

    forecast_row = ft.Row([], alignment=ft.MainAxisAlignment.START, spacing=14, scroll=ft.ScrollMode.ADAPTIVE)
    forecast_container = ft.Container(content=forecast_row, padding=12, height=390, bgcolor="surfaceContainerHigh", border_radius=10)

    category_cards_column = ft.Column([], spacing=14)
    category_display_container = ft.Container(content=category_cards_column, padding=15, bgcolor="surfaceContainerHigh", border_radius=10)

    # 5-Day Detailed Pop-up Modal
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

    def show_day_details(day_info):
        detail_dialog.title = ft.Text(day_info.get("date", "Day Forecast"), size=16, weight=ft.FontWeight.BOLD, color="amber300")
        detail_dialog.content = ft.Container(
            width=360,
            content=ft.Column([
                ft.Row([
                    ft.Text(f"High: {day_info.get('high')}°F", size=15, color="red300", weight=ft.FontWeight.BOLD),
                    ft.Text(f"Low: {day_info.get('low')}°F", size=15, color="blue300", weight=ft.FontWeight.BOLD),
                    ft.Text(f"Rain: {day_info.get('rain_prob_max')}%", size=14, color="cyan300", weight=ft.FontWeight.BOLD),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(height=10, color="grey800"),
                ft.Text("☀️ Daytime Conditions", size=13, weight=ft.FontWeight.BOLD, color="amber200"),
                ft.Text(day_info.get("day_summary", ""), size=12, color="white"),
                ft.Divider(height=10, color="grey800"),
                ft.Text("🌙 Overnight Conditions", size=13, weight=ft.FontWeight.BOLD, color="cyan200"),
                ft.Text(day_info.get("night_summary", ""), size=12, color="white"),
                ft.Divider(height=10, color="grey800"),
                ft.Row([
                    ft.Text(f"🌅 Rise: {day_info.get('sunrise')}", size=11, color="amber100"),
                    ft.Text(f"🌇 Set: {day_info.get('sunset')}", size=11, color="amber100"),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([
                    ft.Text(f"🌕 Moon: {day_info.get('moon_rise')}", size=11, color="cyan200"),
                    ft.Text(f"🌑 Set: {day_info.get('moon_set')}", size=11, color="cyan200"),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ], spacing=6, tight=True)
        )
        detail_dialog.open = True
        page.update()

    def build_cards_for_category(category_key):
        cards = []
        cat_data = latest_weather_data.get(category_key, {})

        # If Sporting Events, add the team search bar at the very top of the category
        if category_key == "sporting_event":
            search_box = ft.Container(
                content=ft.Row([
                    sports_input,
                    ft.IconButton(icon=ft.Icons.SEARCH, on_click=load_weather, icon_color="amber300", tooltip="Search Team Weather")
                ], spacing=10),
                bgcolor="#1c1f26", padding=10, border_radius=8
            )
            cards.append(search_box)

        if not cat_data or not isinstance(cat_data, dict):
            cards.append(ft.Text("No data available for this category.", color="grey400", size=13))
            return cards

        for key, val in cat_data.items():
            title = key.replace("_", " ").title()

            # Outdoor Activities Cards (Score + Details with proper multiline wrap)
            if isinstance(val, dict) and "score" in val:
                score = val.get("score", "--")
                details = val.get("details", "")
                card = ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Text(title, size=15, weight=ft.FontWeight.BOLD, color="amber300"),
                            ft.Text(f"Score: {score}/100", size=13, weight=ft.FontWeight.BOLD, color="green300")
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Divider(height=6, color="grey800"),
                        ft.Row([
                            ft.Text("Details: ", size=12, weight=ft.FontWeight.BOLD, color="grey400"),
                            ft.Text(details, size=12, color="white", expand=True)
                        ], vertical_alignment=ft.CrossAxisAlignment.START)
                    ], spacing=6),
                    bgcolor="#252830", border_radius=8, padding=12
                )
                cards.append(card)

            # Clothing Recommendations Card (Clean badge per time of day)
            elif key == "clothing" and isinstance(val, dict):
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
                            bgcolor="#1c1f26", padding=8, border_radius=6
                        )
                    )
                cards.append(ft.Container(content=ft.Column(clothing_rows, spacing=8), bgcolor="#252830", border_radius=8, padding=12))

            # Hair & Makeup
            elif key == "hair_makeup" and isinstance(val, dict):
                hm_items = [
                    ft.Text("Hair & Makeup Outlook", size=15, weight=ft.FontWeight.BOLD, color="amber300"),
                    ft.Divider(height=6, color="grey800")
                ]
                for subk, subv in val.items():
                    hm_items.append(
                        ft.Row([
                            ft.Text(f"{subk.capitalize()}: ", size=12, weight=ft.FontWeight.BOLD, color="amber200"),
                            ft.Text(str(subv), size=12, color="white", expand=True)
                        ], vertical_alignment=ft.CrossAxisAlignment.START)
                    )
                cards.append(ft.Container(content=ft.Column(hm_items, spacing=6), bgcolor="#252830", border_radius=8, padding=12))

            # Sporting Events List
            elif key == "events" and isinstance(val, list):
                event_cards = [
                    ft.Text("Tracked Game Day Weather", size=15, weight=ft.FontWeight.BOLD, color="amber300"),
                    ft.Divider(height=6, color="grey800")
                ]
                for ev in val:
                    event_cards.append(
                        ft.Container(
                            content=ft.Column([
                                ft.Row([
                                    ft.Text(ev.get("title", "Matchup"), size=14, weight=ft.FontWeight.BOLD, color="amber200", expand=True),
                                    ft.Text(f"⏰ {ev.get('time', '')}", size=12, color="cyan200", weight=ft.FontWeight.W_600)
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Text(f"📍 {ev.get('venue', '')}", size=12, color="grey300"),
                                ft.Text(f"🌤️ {ev.get('conditions', '')}", size=12, color="green200", weight=ft.FontWeight.W_500),
                            ], spacing=4),
                            bgcolor="#1c1f26", padding=10, border_radius=6
                        )
                    )
                cards.append(ft.Container(content=ft.Column(event_cards, spacing=8), bgcolor="#252830", border_radius=8, padding=12))

            # Sowing & Planting Calendar
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
                            bgcolor="#1c1f26", padding=8, border_radius=6
                        )
                    )
                cards.append(ft.Container(content=ft.Column(plant_items, spacing=8), bgcolor="#252830", border_radius=8, padding=12))

            # Celestial Events List
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
                                ft.Text(f"🔭 Direction: {c.get('direction', '')}", size=11, color="grey300"),
                                ft.Text(f"✨ {c.get('notes', '')}", size=11, color="green200")
                            ], spacing=3),
                            bgcolor="#1c1f26", padding=8, border_radius=6
                        )
                    )
                cards.append(ft.Container(content=ft.Column(celest_items, spacing=8), bgcolor="#252830", border_radius=8, padding=12))

            # General Dicts / Strings
            elif isinstance(val, dict):
                col = [ft.Text(title, size=15, weight=ft.FontWeight.BOLD, color="amber300"), ft.Divider(height=6, color="grey800")]
                for sk, sv in val.items():
                    col.append(
                        ft.Row([
                            ft.Text(f"{sk.replace('_', ' ').title()}: ", size=12, weight=ft.FontWeight.BOLD, color="grey400"),
                            ft.Text(str(sv), size=12, color="white", expand=True)
                        ], vertical_alignment=ft.CrossAxisAlignment.START)
                    )
                cards.append(ft.Container(content=ft.Column(col, spacing=6), bgcolor="#252830", border_radius=8, padding=12))
            elif isinstance(val, list):
                col = [ft.Text(title, size=15, weight=ft.FontWeight.BOLD, color="amber300"), ft.Divider(height=6, color="grey800")]
                for li in val:
                    col.append(ft.Text(f"• {str(li)}", size=12, color="white"))
                cards.append(ft.Container(content=ft.Column(col, spacing=6), bgcolor="#252830", border_radius=8, padding=12))
            else:
                cards.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Text(title, size=14, weight=ft.FontWeight.BOLD, color="amber200"),
                            ft.Divider(height=6, color="grey800"),
                            ft.Text(str(val), size=12, color="white")
                        ], spacing=4),
                        bgcolor="#252830", border_radius=8, padding=12
                    )
                )
        return cards

    def render_active_category():
        key = current_selected_category[0]
        category_cards_column.controls = build_cards_for_category(key)
        page.update()

    def handle_category_click(e):
        cat_key = e.control.data
        current_selected_category[0] = cat_key
        for chip in category_buttons_row.controls:
            is_active = (chip.data == cat_key)
            chip.bgcolor = "amber400" if is_active else "#252830"
            chip.content.controls[1].color = "black" if is_active else "white"
            chip.content.controls[0].color = "black" if is_active else "amber200"
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
            on_click=handle_category_click,
            ink=True,
            padding=ft.Padding(14, 8, 14, 8),
            border_radius=20,
            bgcolor="amber400" if is_active else "#252830",
            content=ft.Row([
                ft.Icon(icon, size=16, color="black" if is_active else "amber200"),
                ft.Text(label, size=12, weight=ft.FontWeight.BOLD, color="black" if is_active else "white"),
            ], spacing=6),
        )
        category_chips.append(chip)

    category_buttons_row = ft.Row(controls=category_chips, spacing=8, scroll=ft.ScrollMode.ADAPTIVE)

    async def load_weather(e=None):
        loc = location_input.value.strip() or "28412"
        teams = sports_input.value.strip() or "Panthers, Braves"
        try:
            import server
            res = server.get_full_weather_data(query=loc, sport_team=teams)
            name = res.get("location_name", loc)

            latest_weather_data.clear()
            latest_weather_data.update(res)

            location_display_text.value = f"📍 {name}"
            curr = res.get("current", {})
            condition = curr.get("condition", "Sunny")
            t_val = curr.get("temp", 74)

            is_night = curr.get("is_night", False)
            hero_weather_icon.name = ft.Icons.NIGHTLIGHT_ROUND if is_night else ft.Icons.WB_SUNNY
            hero_weather_icon.color = "cyan200" if is_night else "amber300"
            widget_hero_icon.name = ft.Icons.NIGHTLIGHT_ROUND if is_night else ft.Icons.WB_SUNNY
            widget_hero_icon.color = "cyan200" if is_night else "amber300"

            condition_text.value = condition
            curr_temp_text.value = f"{t_val}°F"
            feels_like_text.value = f"Feels Like: {t_val}°F"
            humidity_text.value = f"Humidity: {curr.get('humidity', 51)}%"
            wind_text.value = f"Wind: {curr.get('wind', 7)} mph"
            uv_badge.value = f"UV: {curr.get('uv_index', 4.0)}"

            sunrise_text.value = f"🌅 Sunrise: {curr.get('sunrise')}"
            sunset_text.value = f"🌇 Sunset: {curr.get('sunset')}"
            moonrise_text.value = f"🌕 Moonrise: {curr.get('moon_rise')}"
            moonset_text.value = f"🌑 Moonset: {curr.get('moon_set')}"

            current_precip_text.value = curr.get("precip_summary", "Precip Now: 0% | Next 24h Max: 0%")
            rain_duration_text.value = curr.get("rain_duration", "Zero precipitation expected.")

            widget_loc_text.value = name
            widget_condition_text.value = condition
            widget_temp_text.value = f"{t_val}°"

            daily_data = res.get("daily", [])
            if daily_data:
                first = daily_data[0]
                widget_hl_text.value = f"H: {first.get('high')}°  L: {first.get('low')}°"
                widget_rain_badge.value = f"💧 {first.get('rain_prob_max')}% Precip"

            hourly_cards = []
            for item in res.get("hourly_36", []):
                h_night = item.get("is_night", False)
                hourly_cards.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Text(str(item.get("time")), size=11, color="amber200", weight=ft.FontWeight.BOLD),
                            ft.Icon(ft.Icons.NIGHTLIGHT_ROUND if h_night else ft.Icons.WB_SUNNY, size=20, color="cyan200" if h_night else "amber300"),
                            ft.Text(f"{item.get('temp')}°", size=13, weight=ft.FontWeight.BOLD, color="white"),
                            ft.Row([ft.Icon(ft.Icons.WATER_DROP, size=10, color="cyan300"), ft.Text(f"{item.get('rain_chance')}%", size=10, color="cyan300")], alignment=ft.MainAxisAlignment.CENTER),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                        width=75, height=130, padding=6, border_radius=8, bgcolor="#252830",
                    )
                )
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
                            ft.Text(day.get("date", ""), size=12, weight=ft.FontWeight.BOLD, color="amber200"),
                            ft.Container(
                                content=ft.Row([
                                    ft.Text(f"↑ {day.get('high')}°", size=13, color="red300", weight=ft.FontWeight.BOLD),
                                    ft.Text(f"↓ {day.get('low')}°", size=13, color="blue300", weight=ft.FontWeight.BOLD),
                                ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                                bgcolor="#1c1f26", padding=4, border_radius=6,
                            ),
                            ft.Container(
                                content=ft.Column([
                                    ft.Row([ft.Text(f"🌅 {day.get('sunrise')}", size=10, color="amber100"), ft.Text(f"🌇 {day.get('sunset')}", size=10, color="amber100")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                    ft.Row([ft.Text(f"🌕 {day.get('moon_rise')}", size=10, color="cyan200"), ft.Text(f"🌑 {day.get('moon_set')}", size=10, color="cyan200")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ], spacing=2),
                                bgcolor="#1c1f26", padding=4, border_radius=6,
                            ),
                            ft.Column([
                                ft.Row([ft.Text("Day", size=11, color="amber200", weight=ft.FontWeight.BOLD), ft.Text(f"💧 {day.get('day_rain_prob')}%", size=11, color="cyan300", weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Text(day.get("day_summary", ""), size=11, color="grey300", max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                            ], spacing=2),
                            ft.Column([
                                ft.Row([ft.Text("Night", size=11, color="cyan200", weight=ft.FontWeight.BOLD), ft.Text(f"💧 {day.get('night_rain_prob')}%", size=11, color="cyan300", weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Text(day.get("night_summary", ""), size=11, color="grey300", max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                            ], spacing=2),
                            ft.Container(
                                content=ft.Row([ft.Icon(ft.Icons.TOUCH_APP, size=12, color="amber300"), ft.Text("Tap for details", size=10, color="amber300", weight=ft.FontWeight.W_500)], alignment=ft.MainAxisAlignment.CENTER, spacing=4),
                                bgcolor="#1c1f26", padding=4, border_radius=6,
                            )
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                        width=230, padding=10, border_radius=10, bgcolor="#252830",
                    )
                )
            forecast_row.controls = day_cards
            render_active_category()
            page.update()
        except Exception as ex:
            condition_text.value = f"Error: {ex}"
            page.update()

    location_input.on_submit = load_weather
    sports_input.on_submit = load_weather

    photorealistic_2x2_widget = ft.Container(
        width=320, height=320, border_radius=28, padding=20,
        gradient=ft.LinearGradient(
            begin=ft.Alignment(-0.8, -1.0), end=ft.Alignment(1.0, 1.0),
            colors=["#1a2639", "#16202c", "#2b211a"]
        ),
        border=ft.Border(
            top=ft.BorderSide(1.5, "rgba(255, 255, 255, 0.25)"),
            left=ft.BorderSide(1.5, "rgba(255, 255, 255, 0.20)"),
            right=ft.BorderSide(1.0, "rgba(255, 255, 255, 0.10)"),
            bottom=ft.BorderSide(1.0, "rgba(255, 255, 255, 0.08)"),
        ),
        content=ft.Column([
            ft.Row([
                ft.Column([widget_loc_text, widget_condition_text], spacing=2),
                ft.Container(content=ft.Text("LIVE", size=10, weight=ft.FontWeight.BOLD, color="amber300"), bgcolor="rgba(255, 193, 7, 0.15)", padding=ft.Padding(8, 4, 8, 4), border_radius=12)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
            ft.Row([
                widget_temp_text,
                ft.Container(content=widget_hero_icon, padding=10, border_radius=50, bgcolor="rgba(255, 193, 7, 0.12)")
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            widget_hl_text,
            ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
            ft.Row([
                ft.Container(content=widget_rain_badge, bgcolor="rgba(0, 229, 255, 0.12)", padding=ft.Padding(8, 4, 8, 4), border_radius=10),
                ft.Container(content=widget_uv_badge, bgcolor="rgba(255, 152, 0, 0.12)", padding=ft.Padding(8, 4, 8, 4), border_radius=10),
                ft.Container(content=widget_aqi_badge, bgcolor="rgba(76, 175, 80, 0.12)", padding=ft.Padding(8, 4, 8, 4), border_radius=10),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ], spacing=4)
    )

    full_dashboard = ft.Column([
        photorealistic_2x2_widget,
        ft.Divider(height=15, color="grey800"),
        ft.Row([
            location_input,
            ft.IconButton(icon=ft.Icons.SEARCH, on_click=load_weather, icon_color="amber300")
        ], alignment=ft.MainAxisAlignment.CENTER),
        ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
        ft.Container(
            content=ft.Column([
                location_display_text,
                condition_text,
                ft.Row([hero_weather_icon, curr_temp_text], spacing=16, alignment=ft.MainAxisAlignment.CENTER),
                feels_like_text,
                ft.Divider(height=8, color=ft.Colors.TRANSPARENT),
                ft.Row([humidity_text, wind_text, aqi_badge, uv_badge], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(height=6, color=ft.Colors.TRANSPARENT),
                ft.Row([sunrise_text, sunset_text], alignment=ft.MainAxisAlignment.CENTER, spacing=20),
                ft.Row([moonrise_text, moonset_text], alignment=ft.MainAxisAlignment.CENTER, spacing=20),
                ft.Divider(height=6, color=ft.Colors.TRANSPARENT),
                current_precip_text,
                rain_duration_text,
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
            padding=16, border_radius=10, bgcolor="surfaceContainerHigh"
        ),
        ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
        ft.Text("Hourly Forecast (Next 36 Hours)", size=15, weight=ft.FontWeight.BOLD, color="amber200"),
        hourly_container,
        ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
        ft.Text("5-Day Forecast (Tap card for full details)", size=15, weight=ft.FontWeight.BOLD, color="amber200"),
        forecast_container,
        ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
        ft.Text("Activity & Lifestyle Outlook", size=15, weight=ft.FontWeight.BOLD, color="amber200"),
        category_buttons_row,
        ft.Divider(height=5, color=ft.Colors.TRANSPARENT),
        category_display_container,
    ], width=750)

    page.add(full_dashboard)
    await load_weather()

if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.WEB_BROWSER)