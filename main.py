import flet as ft
from datetime import datetime

async def main(page: ft.Page):
    page.title = "AeroCast Weather & Climate"
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.scroll = ft.ScrollMode.ADAPTIVE
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 16

    latest_weather_data = {}
    current_selected_category = ["weather_climate"]

    # 2x2 Realistic Widget Controls
    widget_loc_text = ft.Text("Wilmington (28412 / Lords Creek), NC", size=13, weight=ft.FontWeight.W_600, color="amber200")
    widget_condition_text = ft.Text("Clear", size=14, color="grey300", weight=ft.FontWeight.W_500)
    widget_hero_icon = ft.Icon(ft.Icons.WB_SUNNY, size=62, color="amber300")
    widget_temp_text = ft.Text("74°", size=54, weight=ft.FontWeight.BOLD, color="white")
    widget_hl_text = ft.Text("H: 82°  L: 68°", size=13, weight=ft.FontWeight.BOLD, color="amber100")
    widget_rain_badge = ft.Text("💧 10% Precip", size=11, color="cyan200", weight=ft.FontWeight.BOLD)
    widget_uv_badge = ft.Text("☀️ UV 5", size=11, color="orange200", weight=ft.FontWeight.BOLD)
    widget_aqi_badge = ft.Text("🍃 AQI 32 (Good)", size=11, color="green300", weight=ft.FontWeight.BOLD)

    # Main App Controls
    location_input = ft.TextField(
        label="Location (ZIP or City/State)",
        value="28412",
        width=260,
        border_color="amber300",
        focused_border_color="amber200",
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

    current_precip_text = ft.Text("Precip Now: --% | Next 24h: --%", size=14, color="cyan300", weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)
    rain_duration_text = ft.Text("No immediate rain expected.", size=13, color="amber100", text_align=ft.TextAlign.CENTER)

    hourly_row = ft.Row([], spacing=10, scroll=ft.ScrollMode.ADAPTIVE)
    hourly_container = ft.Container(content=hourly_row, padding=10, height=175, bgcolor="surfaceContainerHigh", border_radius=10)

    forecast_row = ft.Row([], alignment=ft.MainAxisAlignment.START, spacing=14, scroll=ft.ScrollMode.ADAPTIVE)
    forecast_container = ft.Container(content=forecast_row, padding=12, height=390, bgcolor="surfaceContainerHigh", border_radius=10)

    category_cards_row = ft.Row(wrap=True, spacing=14, run_spacing=14, vertical_alignment=ft.CrossAxisAlignment.START)
    category_display_container = ft.Container(content=category_cards_row, padding=15, bgcolor="surfaceContainerHigh", border_radius=10)

    # 5-Day Detailed Click Modal
    detail_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Detailed Day Outlook", size=16, weight=ft.FontWeight.BOLD, color="amber300"),
        content=ft.Container(width=340, content=ft.Text("No details available")),
        actions=[
            ft.TextButton("Close", on_click=lambda e: close_dialog(e))
        ],
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
                    ft.Text(f"Max Rain: {day_info.get('rain_prob_max')}%", size=14, color="cyan300", weight=ft.FontWeight.BOLD),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(height=10, color="grey800"),
                ft.Text("☀️ Daytime Outlook", size=13, weight=ft.FontWeight.BOLD, color="amber200"),
                ft.Text(f"Rain Chance: {day_info.get('day_rain_prob')}%", size=12, color="cyan200"),
                ft.Text(day_info.get("day_summary", "Partly cloudy with pleasant temperatures."), size=12, color="white"),
                ft.Divider(height=10, color="grey800"),
                ft.Text("🌙 Nighttime Outlook", size=13, weight=ft.FontWeight.BOLD, color="cyan200"),
                ft.Text(f"Rain Chance: {day_info.get('night_rain_prob')}%", size=12, color="cyan200"),
                ft.Text(day_info.get("night_summary", "Calm and clear skies overnight."), size=12, color="white"),
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

    def create_subcat_cards(data_dict, category_key=""):
        cards = []
        if not data_dict or not isinstance(data_dict, dict):
            return [ft.Text("No data available for this category.", color="grey400", size=13)]

        data_to_render = dict(data_dict)
        if "moon_rise" in data_to_render or "moon_set" in data_to_render:
            m_rise = data_to_render.pop("moon_rise", "--")
            m_set = data_to_render.pop("moon_set", "--")
            cards.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text("Moon Timing", size=14, weight=ft.FontWeight.BOLD, color="amber300"),
                        ft.Divider(height=6, color="grey800"),
                        ft.Row([ft.Text("🌕 Rise:", size=13, color="cyan200"), ft.Text(str(m_rise), size=13, color="white", weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([ft.Text("🌑 Set:", size=13, color="cyan200"), ft.Text(str(m_set), size=13, color="white", weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ], spacing=6),
                    bgcolor="#252830", border_radius=8, padding=14, width=280,
                )
            )

        for key, val in data_to_render.items():
            title = key.replace("_", " ").title()
            if key == "fishing" and isinstance(val, dict):
                f_score = val.get("score", "--")
                lines = [seg.strip() for seg in val.get("details", "").split(".") if seg.strip()]
                fishing_controls = [
                    ft.Row([ft.Icon(ft.Icons.PHISHING, size=18, color="cyan300"), ft.Text("Fishing Outlook", size=14, weight=ft.FontWeight.BOLD, color="amber300")], spacing=8),
                    ft.Divider(height=6, color="grey800"),
                    ft.Container(
                        content=ft.Row([ft.Text("Activity Score:", size=12, color="grey300"), ft.Text(f"{f_score}/100 (Prime)", size=13, color="green300", weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        bgcolor="#1c1f26", padding=8, border_radius=6
                    ),
                ]
                for l in lines:
                    fishing_controls.append(ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=13, color="amber200"), ft.Text(l, size=12, color="white", expand=True)], spacing=6))
                cards.append(ft.Container(content=ft.Column(fishing_controls, spacing=6), bgcolor="#252830", border_radius=8, padding=14, width=320))
            elif isinstance(val, list):
                list_items = [ft.Text(title, size=14, weight=ft.FontWeight.BOLD, color="amber300"), ft.Divider(height=6, color="grey800")]
                for item in val:
                    if isinstance(item, dict):
                        item_box = ft.Container(
                            content=ft.Column([
                                ft.Text(f"• {item.get('title', item.get('item', 'Item'))}", size=13, weight=ft.FontWeight.BOLD, color="amber200"),
                                ft.Text(f"  {item.get('venue', item.get('action', ''))}", size=12, color="white"),
                                ft.Text(f"  {item.get('time', item.get('timing', item.get('notes', '')))}", size=11, color="cyan200"),
                            ], spacing=2),
                            bgcolor="#1c1f26", padding=6, border_radius=6
                        )
                        list_items.append(item_box)
                    else:
                        list_items.append(ft.Text(f"• {str(item)}", size=12, color="white"))
                cards.append(ft.Container(content=ft.Column(list_items, spacing=6), bgcolor="#252830", border_radius=8, padding=14, width=320))
            elif isinstance(val, dict):
                content_col = [ft.Text(title, size=14, weight=ft.FontWeight.BOLD, color="amber300"), ft.Divider(height=6, color="grey800")]
                for sk, sv in val.items():
                    content_col.append(ft.Row([ft.Text(f"{sk.replace('_', ' ').title()}:", size=12, color="grey300"), ft.Text(str(sv), size=12, color="white", weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN))
                cards.append(ft.Container(content=ft.Column(content_col, spacing=6), bgcolor="#252830", border_radius=8, padding=14, width=300))
            else:
                cards.append(ft.Container(content=ft.Column([ft.Text(title, size=13, weight=ft.FontWeight.BOLD, color="amber200"), ft.Divider(height=6, color="grey800"), ft.Text(str(val), size=13, color="white")], spacing=4), bgcolor="#252830", border_radius=8, padding=14, width=280))
        return cards

    def render_active_category():
        key = current_selected_category[0]
        cat_data = latest_weather_data.get(key, {})
        category_cards_row.controls = create_subcat_cards(cat_data, category_key=key)
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
        try:
            import server
            res = server.get_full_weather_data(loc)
            name = res.get("location_name", loc)

            latest_weather_data.clear()
            latest_weather_data.update(res)

            location_display_text.value = f"📍 {name}"
            curr = res.get("current", {})
            condition = curr.get("condition", "Clear")
            t_val = curr.get("temp", 74)

            is_night = curr.get("is_night", False) or datetime.now().hour < 7 or datetime.now().hour >= 19
            hero_weather_icon.name = ft.Icons.NIGHTLIGHT_ROUND if is_night else ft.Icons.WB_SUNNY
            hero_weather_icon.color = "cyan200" if is_night else "amber300"
            widget_hero_icon.name = ft.Icons.NIGHTLIGHT_ROUND if is_night else ft.Icons.WB_SUNNY
            widget_hero_icon.color = "cyan200" if is_night else "amber300"

            condition_text.value = condition
            curr_temp_text.value = f"{t_val}°F"
            feels_like_text.value = f"Feels Like: {t_val}°F"
            humidity_text.value = f"Humidity: {curr.get('humidity', 65)}%"
            wind_text.value = f"Wind: {curr.get('wind', 6)} mph"
            uv_badge.value = f"UV: {curr.get('uv_index', 5.0)}"

            s_rise = curr.get("sunrise", "06:58 AM")
            s_set = curr.get("sunset", "07:10 PM")
            m_rise = curr.get("moon_rise", "07:20 PM")
            m_set = curr.get("moon_set", "06:35 AM")

            sunrise_text.value = f"🌅 Sunrise: {s_rise}"
            sunset_text.value = f"🌇 Sunset: {s_set}"
            moonrise_text.value = f"🌕 Moonrise: {m_rise}"
            moonset_text.value = f"🌑 Moonset: {m_set}"

            current_precip_text.value = curr.get("precip_summary", "Precip Now: 0% | Next 24h: 5%")
            rain_duration_text.value = curr.get("rain_duration", "No immediate heavy rain expected.")

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
                h_is_night = item.get("is_night", False)
                hourly_cards.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Text(str(item.get("time")), size=11, color="amber200", weight=ft.FontWeight.BOLD),
                            ft.Icon(ft.Icons.NIGHTLIGHT_ROUND if h_is_night else ft.Icons.WB_SUNNY, size=20, color="cyan200" if h_is_night else "amber300"),
                            ft.Text(f"{item.get('temp')}°", size=13, weight=ft.FontWeight.BOLD, color="white"),
                            ft.Row([ft.Icon(ft.Icons.WATER_DROP, size=10, color="cyan300"), ft.Text(f"{item.get('rain_chance')}%", size=10, color="cyan300")], alignment=ft.MainAxisAlignment.CENTER),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                        width=75, height=130, padding=6, border_radius=8, bgcolor="#252830",
                    )
                )
            hourly_row.controls = hourly_cards

            # Clickable 5-Day Forecast Cards with Tap Indicator
            day_cards = []
            for day in daily_data:
                day_cards.append(
                    ft.Container(
                        data=day,
                        on_click=lambda e: show_day_details(e.control.data),
                        ink=True,
                        tooltip="Tap for full day & night breakdown",
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

    # 2x2 Photorealistic Widget Component
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
        ft.Row([location_input, ft.IconButton(icon=ft.Icons.SEARCH, on_click=load_weather, icon_color="amber300")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
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
    ], width=850)

    page.add(full_dashboard)
    await load_weather()

if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.WEB_BROWSER)
    