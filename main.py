import flet as ft
import requests

def main(page: ft.Page):
    page.title = "AeroCast Weather & Climate Dashboard"
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.scroll = ft.ScrollMode.ADAPTIVE
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 20

    # --- UI Components & State Controls ---
    location_input = ft.TextField(
        label="Location (ZIP or City/State)",
        value="28401",
        width=300,
        border_color="amber300",
        focused_border_color="amber200"
    )

    condition_text = ft.Text("Loading weather data...", size=18, weight=ft.FontWeight.BOLD, color="amber200")
    curr_temp_text = ft.Text("--°F", size=48, weight=ft.FontWeight.BOLD, color="white")
    feels_like_text = ft.Text("Feels Like: --°F", size=14, color="grey300")
    humidity_text = ft.Text("Humidity: --%", size=13, color="cyan200")
    wind_text = ft.Text("Wind: -- mph", size=13, color="cyan200")
    uv_badge = ft.Text("UV: --", size=13, color="green300", weight=ft.FontWeight.BOLD)
    aqi_badge = ft.Text("AQI: --", size=13, color="green300", weight=ft.FontWeight.BOLD)
    
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

    # --- Hourly Forecast Carousel Layout ---
    hourly_row = ft.Row(
        [],
        spacing=10,
        scroll=ft.ScrollMode.ADAPTIVE,
    )
    hourly_container = ft.Container(
        content=hourly_row,
        padding=10,
        height=180,
        bgcolor="surfaceContainerHigh",
        border_radius=10,
    )

    # --- 5-Day Forecast Row Layout ---
    forecast_row = ft.Row(
        [],
        alignment=ft.MainAxisAlignment.START,
        spacing=12,
        scroll=ft.ScrollMode.ADAPTIVE,
    )
    forecast_container = ft.Container(
        content=forecast_row,
        padding=10,
        height=370,
        bgcolor="surfaceContainerHigh",
        border_radius=10,
    )

    # --- Category Data & Views ---
    latest_weather_data = {}
    current_selected_category = ["weather_climate"]

    # All category cards snap flush to the top edge
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
        
        # 1. Combine Moon Rise & Set if in Astronomy
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

            # Case 1: Sporting Events (List of game/match dictionaries)
            if key == "events" and isinstance(val, list):
                event_controls = [
                    ft.Row([
                        ft.Icon(ft.Icons.SPORTS_FOOTBALL, size=18, color="amber300"),
                        ft.Text("Sporting Events", size=14, weight=ft.FontWeight.BOLD, color="amber300"),
                    ], spacing=8),
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
                                ft.Text(f"🏆 {ev_title}", size=13, weight=ft.FontWeight.BOLD, color="amber200"),
                                ft.Text(f"📍 Venue: {ev_venue}", size=12, color="white"),
                                ft.Text(f"⏰ Time: {ev_time}", size=12, color="cyan200"),
                                ft.Text(f"🌤 Weather: {ev_cond}", size=12, color="green200", weight=ft.FontWeight.W_500),
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

            # Case 2: Planting & Harvest
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

            # Case 3: Celestial Events (Astronomy)
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

            # Case 4: Visible Planets (Astronomy)
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

            # Case 5: Nested Dictionaries (Outdoor Activities, Sports, Clothing, etc.)
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
                                    ft.Text(f"{sub_title}:", size=12, color="grey300", weight=ft.FontWeight.W_500),
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
                        width=280,
                    )
                )

            # Case 6: Standard Text / Value Cards
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
                        width=250,
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

    category_buttons_row = ft.Row(
        controls=category_chips,
        spacing=10,
        scroll=ft.ScrollMode.ADAPTIVE
    )

    # --- Popup Dialog for 5-Day Detailed Outlook ---
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
                ft.Text(f"Daytime: {day_data.get('day_summary', 'No summary available')}"),
                ft.Text(f"Nighttime: {day_data.get('night_summary', 'No summary available')}"),
                ft.Divider(),
                ft.Text("• Barometric Pressure: 30.15 inHg (Stable)"),
                ft.Text("• Dew Point: 58°F (Comfortable Humidity)"),
                ft.Row([
                    ft.Text(f"🌅 Rise: {day_data.get('sunrise', '--')}", size=12, color="amber200"),
                    ft.Text(f"🌇 Set: {day_data.get('sunset', '--')}", size=12, color="amber200"),
                ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                ft.Row([
                    ft.Text(f"🌕 Rise: {day_data.get('moon_rise', '--')}", size=12, color="cyan200"),
                    ft.Text(f"🌑 Set: {day_data.get('moon_set', '--')}", size=12, color="cyan200"),
                ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
            ], height=260, scroll=ft.ScrollMode.ADAPTIVE),
            actions=[
                ft.TextButton("Close", on_click=close_dlg)
            ]
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    # --- Backend Communication / Data Fetching ---
    def load_weather(e=None):
        loc = location_input.value.strip() or "28401"
        try:
            response = requests.get(f"http://127.0.0.1:8000/weather?query={loc}", timeout=5)
            
            if response.status_code == 200:
                res = response.json()
                latest_weather_data.clear()
                latest_weather_data.update(res)

                curr = res.get("current", {})
                
                condition_text.value = curr.get("condition", "Clear")
                
                temp_raw = curr.get('temp')
                t_val = temp_raw.get('val', '--') if isinstance(temp_raw, dict) else (temp_raw if temp_raw is not None else '--')
                curr_temp_text.value = f"{t_val}°F"

                feels_raw = curr.get('feels_like')
                f_val = feels_raw.get('val', '--') if isinstance(feels_raw, dict) else (feels_raw if feels_raw is not None else '--')
                feels_like_text.value = f"Feels Like: {f_val}°F"

                humidity_text.value = f"Humidity: {curr.get('humidity', '--')}%"
                wind_text.value = f"Wind: {curr.get('wind', '--')} mph"
                uv_badge.value = f"UV: {curr.get('uv_index', '--')}"
                
                aqi_data = res.get("aqi", {})
                aqi_badge.value = f"AQI: {aqi_data.get('aqi', '--')} ({aqi_data.get('category', 'Good')})" if isinstance(aqi_data, dict) else f"AQI: {aqi_data}"

                precip_sum = curr.get("precip_summary")
                rain_dur = curr.get("rain_duration")
                current_precip_text.value = precip_sum if precip_sum else "Precip Now: 0% | Next 24h: 0%"
                rain_duration_text.value = rain_dur if rain_dur else "No immediate rain expected."

                # 1. Build Hourly Forecast Cards
                hourly_data = res.get("hourly_36", [])
                hour_cards = []
                for item in hourly_data:
                    h_time = item.get("time") or item.get("hour") or "--"
                    h_temp = item.get("temp", "--")
                    h_pop = item.get("pop", item.get("precip_prob", item.get("rain_prob", 0)))
                    
                    pop_color = "cyan300" if int(h_pop or 0) >= 30 else "grey500"

                    hour_card = ft.Container(
                        content=ft.Column([
                            ft.Text(str(h_time), size=12, color="amber200", weight=ft.FontWeight.BOLD),
                            ft.Icon(ft.Icons.WB_SUNNY, size=22, color="amber300"),
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
                    hour_cards.append(hour_card)
                
                hourly_row.controls = hour_cards

                # 2. Build 5-Day Horizontal Forecast Cards
                daily_data = res.get("daily") or res.get("forecast") or []
                day_cards = []
                for day in daily_data:
                    rain_pct = day.get("rain_prob_max", 0)
                    prob_color = "cyan300" if rain_pct >= 30 else "grey400"
                    
                    card_content = ft.Container(
                        on_click=lambda e, d=day: open_day_details(e, d),
                        ink=True,
                        content=ft.Column([
                            ft.Text(day.get("date", ""), size=14, weight=ft.FontWeight.BOLD, color="amber200", text_align=ft.TextAlign.CENTER),
                            ft.Divider(height=4, color=ft.Colors.TRANSPARENT),
                            ft.Row([
                                ft.Icon(ft.Icons.ARROW_UPWARD, size=13, color="red400"),
                                ft.Text(f"{day.get('high', '--')}°", size=13, weight=ft.FontWeight.BOLD, color="red300"),
                                ft.Icon(ft.Icons.ARROW_DOWNWARD, size=13, color="blue400"),
                                ft.Text(f"{day.get('low', '--')}°", size=13, weight=ft.FontWeight.BOLD, color="blue300"),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Row([
                                ft.Icon(ft.Icons.WATER_DROP, size=13, color=prob_color),
                                ft.Text(f"{rain_pct}%", size=13, color=prob_color, weight=ft.FontWeight.BOLD),
                            ], alignment=ft.MainAxisAlignment.CENTER),
                            ft.Divider(height=4, color=ft.Colors.TRANSPARENT),
                            ft.Column([
                                ft.Icon(ft.Icons.WB_SUNNY, size=24, color="amber300"),
                                ft.Text(f"Day: {day.get('day_summary', '')}", size=11, color="grey200", text_align=ft.TextAlign.CENTER),
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                            ft.Divider(height=4, color=ft.Colors.TRANSPARENT),
                            ft.Column([
                                ft.Icon(ft.Icons.NIGHTLIGHT_ROUND, size=24, color="lightblue"),
                                ft.Text(f"Night: {day.get('night_summary', '')}", size=11, color="grey200", text_align=ft.TextAlign.CENTER),
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                            ft.Divider(height=4, color=ft.Colors.TRANSPARENT),
                            
                            ft.Row([
                                ft.Text(f"🌅 {day.get('sunrise', '--')}", size=10, color="amber100"),
                                ft.Text(f"🌇 {day.get('sunset', '--')}", size=10, color="amber100"),
                            ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                            ft.Row([
                                ft.Text(f"🌕 {day.get('moon_rise', '--')}", size=10, color="cyan100"),
                                ft.Text(f"🌑 {day.get('moon_set', '--')}", size=10, color="cyan100"),
                            ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                        width=210,
                        padding=10,
                        border_radius=8,
                        bgcolor="#252830",
                    )
                    day_cards.append(card_content)

                forecast_row.controls = day_cards

                # 3. Populate Category cards
                cat_key = current_selected_category[0]
                category_cards_row.controls = create_subcat_cards(res.get(cat_key, {}), category_key=cat_key)

                condition_text.update()
                curr_temp_text.update()
                feels_like_text.update()
                humidity_text.update()
                wind_text.update()
                aqi_badge.update()
                uv_badge.update()
                current_precip_text.update()
                rain_duration_text.update()
                hourly_row.update()
                forecast_row.update()
                category_cards_row.update()
                page.update()
            else:
                condition_text.value = f"Server Error: Status {response.status_code}"
                page.update()
        except Exception as ex:
            condition_text.value = f"Connection Error: {ex}"
            page.update()

    # --- Main Dashboard Layout ---
    search_bar = ft.Row([
        location_input,
        ft.IconButton(icon=ft.Icons.SEARCH, on_click=load_weather, icon_color="amber300")
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    current_weather_card = ft.Container(
        content=ft.Column([
            ft.Column([
                condition_text,
                ft.Row([
                    ft.Icon(ft.Icons.WB_SUNNY, size=64, color="amber300"),
                    curr_temp_text,
                ], spacing=20, alignment=ft.MainAxisAlignment.CENTER),
                feels_like_text,
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5),
            
            ft.Divider(height=15, color=ft.Colors.TRANSPARENT),
            ft.Row([humidity_text, wind_text, aqi_badge, uv_badge], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
            
            # Precipitation stack centered horizontally
            ft.Column([
                ft.Row([current_precip_text], alignment=ft.MainAxisAlignment.CENTER),
                ft.Row([rain_duration_text], alignment=ft.MainAxisAlignment.CENTER),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
        ]),
        padding=20,
        border_radius=10,
        bgcolor="surfaceContainerHigh"
    )

    page.add(
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
    )

    load_weather()

if __name__ == "__main__":
    ft.run(main)