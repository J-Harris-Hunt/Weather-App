"""
astro.py - small, dependency-free astronomy helpers for Thick Moose Weather.

Everything here is computed from orbital elements (Paul Schlyter's low-precision
method), so it needs no network and no extra packages. Accuracy is roughly:
  * Moon phase / illumination: within ~1 %
  * Moonrise / moonset: within a few minutes
  * Planet altitude / direction: within about a degree (plenty for "is it up?")
Sunrise/sunset shown elsewhere in the app still come from Open-Meteo.
"""
import math
from datetime import datetime, timedelta, timezone

_RAD = math.pi / 180.0

PLANET_NAMES = ["Mercury", "Venus", "Mars", "Jupiter", "Saturn"]

# Orbital elements: (N0, N1, i0, i1, w0, w1, a, e0, e1, M0, M1), value = v0 + v1*d
_ELEMENTS = {
    "Mercury": (48.3313, 3.24587e-5, 7.0047, 5.00e-8, 29.1241, 1.01444e-5, 0.387098, 0.205635, 5.59e-10, 168.6562, 4.0923344368),
    "Venus":   (76.6799, 2.46590e-5, 3.3946, 2.75e-8, 54.8910, 1.38374e-5, 0.723330, 0.006773, -1.302e-9, 48.0052, 1.6021302244),
    "Mars":    (49.5574, 2.11081e-5, 1.8497, -1.78e-8, 286.5016, 2.92961e-5, 1.523688, 0.093405, 2.516e-9, 18.6021, 0.5240207766),
    "Jupiter": (100.4542, 2.76854e-5, 1.3030, -1.557e-7, 273.8777, 1.64505e-5, 5.20256, 0.048498, 4.469e-9, 19.8950, 0.0830853001),
    "Saturn":  (113.6634, 2.38980e-5, 2.4886, -1.081e-7, 339.3939, 2.97661e-5, 9.55475, 0.055546, -9.499e-9, 316.9670, 0.0334442282),
}

# Typical annual meteor-shower peaks: (name, month, day, approx. peak rate per hour, note)
_METEOR_SHOWERS = [
    ("Quadrantids", 1, 3, 80, "Short, sharp peak; best before dawn"),
    ("Lyrids", 4, 22, 18, "Best after midnight"),
    ("Eta Aquariids", 5, 6, 30, "Best before dawn (stronger in the south)"),
    ("Perseids", 8, 12, 100, "Best after midnight"),
    ("Orionids", 10, 21, 20, "Best after midnight"),
    ("Leonids", 11, 17, 15, "Best after midnight"),
    ("Geminids", 12, 14, 120, "Strong from about 10 PM onward"),
]


def _sind(x):
    return math.sin(x * _RAD)


def _cosd(x):
    return math.cos(x * _RAD)


def _atan2d(y, x):
    return math.atan2(y, x) / _RAD


def _rev(x):
    return x % 360.0


def _julian_day(dt_utc):
    return dt_utc.timestamp() / 86400.0 + 2440587.5


def _day_number(dt_utc):
    """Days since 1999-12-31 00:00 UT (the epoch used by the formulas)."""
    return _julian_day(dt_utc) - 2451543.5


def _kepler(M, e):
    E = M + (180.0 / math.pi) * e * _sind(M) * (1.0 + e * _cosd(M))
    for _ in range(8):
        dE = (E - (180.0 / math.pi) * e * _sind(E) - M) / (1.0 - e * _cosd(E))
        E -= dE
        if abs(dE) < 1e-6:
            break
    return E


def _sun(d):
    """Returns (xs, ys, r, ecliptic longitude, mean anomaly, argument of perihelion)."""
    w = 282.9404 + 4.70935e-5 * d
    e = 0.016709 - 1.151e-9 * d
    M = _rev(356.0470 + 0.9856002585 * d)
    E = _kepler(M, e)
    xv = _cosd(E) - e
    yv = math.sqrt(1.0 - e * e) * _sind(E)
    v = _atan2d(yv, xv)
    r = math.hypot(xv, yv)
    lon = _rev(v + w)
    return r * _cosd(lon), r * _sind(lon), r, lon, M, w


def _ecl_to_equ(x, y, z, d):
    ecl = 23.4393 - 3.563e-7 * d
    ye = y * _cosd(ecl) - z * _sind(ecl)
    ze = y * _sind(ecl) + z * _cosd(ecl)
    ra = _rev(_atan2d(ye, x))
    dec = _atan2d(ze, math.hypot(x, ye))
    return ra, dec, math.sqrt(x * x + ye * ye + ze * ze)


def _moon_ecliptic(d):
    """Geocentric ecliptic (lon, lat, distance in Earth radii) of the Moon."""
    N = _rev(125.1228 - 0.0529538083 * d)
    i = 5.1454
    w = _rev(318.0634 + 0.1643573223 * d)
    a = 60.2666
    e = 0.054900
    M = _rev(115.3654 + 13.0649929509 * d)
    E = _kepler(M, e)
    xv = a * (_cosd(E) - e)
    yv = a * math.sqrt(1.0 - e * e) * _sind(E)
    v = _atan2d(yv, xv)
    r = math.hypot(xv, yv)
    xh = r * (_cosd(N) * _cosd(v + w) - _sind(N) * _sind(v + w) * _cosd(i))
    yh = r * (_sind(N) * _cosd(v + w) + _cosd(N) * _sind(v + w) * _cosd(i))
    zh = r * (_sind(v + w) * _sind(i))
    lon = _rev(_atan2d(yh, xh))
    lat = _atan2d(zh, math.hypot(xh, yh))

    _, _, _, _, Ms, ws = _sun(d)
    Ls = Ms + ws
    Lm = M + w + N
    D = Lm - Ls
    F = Lm - N
    lon += (-1.274 * _sind(M - 2 * D) + 0.658 * _sind(2 * D) - 0.186 * _sind(Ms)
            - 0.059 * _sind(2 * M - 2 * D) - 0.057 * _sind(M - 2 * D + Ms)
            + 0.053 * _sind(M + 2 * D) + 0.046 * _sind(2 * D - Ms) + 0.041 * _sind(M - Ms)
            - 0.035 * _sind(D) - 0.031 * _sind(M + Ms) - 0.015 * _sind(2 * F - 2 * D)
            + 0.011 * _sind(M - 4 * D))
    lat += (-0.173 * _sind(F - 2 * D) - 0.055 * _sind(M - F - 2 * D) - 0.046 * _sind(M + F - 2 * D)
            + 0.033 * _sind(F + 2 * D) + 0.017 * _sind(2 * M + F))
    r += -0.58 * _cosd(M - 2 * D) - 0.46 * _cosd(2 * D)
    return _rev(lon), lat, r


def _moon_equatorial(d):
    lon, lat, r = _moon_ecliptic(d)
    x = r * _cosd(lon) * _cosd(lat)
    y = r * _sind(lon) * _cosd(lat)
    z = r * _sind(lat)
    ra, dec, dist = _ecl_to_equ(x, y, z, d)
    return ra, dec, dist


def _planet_equatorial(name, d):
    N0, N1, i0, i1, w0, w1, a, e0, e1, M0, M1 = _ELEMENTS[name]
    N = N0 + N1 * d
    i = i0 + i1 * d
    w = w0 + w1 * d
    e = e0 + e1 * d
    M = _rev(M0 + M1 * d)
    E = _kepler(M, e)
    xv = a * (_cosd(E) - e)
    yv = a * math.sqrt(1.0 - e * e) * _sind(E)
    v = _atan2d(yv, xv)
    r = math.hypot(xv, yv)
    xh = r * (_cosd(N) * _cosd(v + w) - _sind(N) * _sind(v + w) * _cosd(i))
    yh = r * (_sind(N) * _cosd(v + w) + _cosd(N) * _sind(v + w) * _cosd(i))
    zh = r * (_sind(v + w) * _sind(i))

    if name in ("Jupiter", "Saturn"):
        Mj = _rev(19.8950 + 0.0830853001 * d)
        Ms_ = _rev(316.9670 + 0.0334442282 * d)
        lon = _atan2d(yh, xh)
        lat = _atan2d(zh, math.hypot(xh, yh))
        rr = math.sqrt(xh * xh + yh * yh + zh * zh)
        if name == "Jupiter":
            lon += (-0.332 * _sind(2 * Mj - 5 * Ms_ - 67.6) - 0.056 * _sind(2 * Mj - 2 * Ms_ + 21)
                    + 0.042 * _sind(3 * Mj - 5 * Ms_ + 21) - 0.036 * _sind(Mj - 2 * Ms_)
                    + 0.022 * _cosd(Mj - Ms_) + 0.023 * _sind(2 * Mj - 3 * Ms_ + 52)
                    - 0.016 * _sind(Mj - 5 * Ms_ - 69))
        else:
            lon += (0.812 * _sind(2 * Mj - 5 * Ms_ - 67.6) - 0.229 * _cosd(2 * Mj - 4 * Ms_ - 2)
                    + 0.119 * _sind(Mj - 2 * Ms_ - 3) + 0.046 * _sind(2 * Mj - 6 * Ms_ - 69)
                    + 0.014 * _sind(Mj - 3 * Ms_ + 32))
            lat += -0.020 * _cosd(2 * Mj - 4 * Ms_ - 2) + 0.018 * _sind(2 * Mj - 6 * Ms_ - 49)
        xh = rr * _cosd(lon) * _cosd(lat)
        yh = rr * _sind(lon) * _cosd(lat)
        zh = rr * _sind(lat)

    xs, ys, _, _, _, _ = _sun(d)
    return _ecl_to_equ(xh + xs, yh + ys, zh, d)


def _alt_az(ra, dec, lat, lon_east, dt_utc):
    jd = _julian_day(dt_utc)
    lst = _rev(280.46061837 + 360.98564736629 * (jd - 2451545.0) + lon_east)
    H = lst - ra
    sin_alt = _sind(lat) * _sind(dec) + _cosd(lat) * _cosd(dec) * _cosd(H)
    alt = math.asin(max(-1.0, min(1.0, sin_alt))) / _RAD
    az = _rev(_atan2d(_sind(H), _cosd(H) * _sind(lat) - math.tan(dec * _RAD) * _cosd(lat)) + 180.0)
    return alt, az


def sun_altitude(lat, lon, dt_utc):
    d = _day_number(dt_utc)
    xs, ys, _, _, _, _ = _sun(d)
    ra, dec, _ = _ecl_to_equ(xs, ys, 0.0, d)
    return _alt_az(ra, dec, lat, lon, dt_utc)[0]


def moon_altitude(lat, lon, dt_utc):
    d = _day_number(dt_utc)
    ra, dec, dist = _moon_equatorial(d)
    return _alt_az(ra, dec, lat, lon, dt_utc)[0]


def _moon_alt_minus_h0(lat, lon, dt_utc):
    d = _day_number(dt_utc)
    ra, dec, dist = _moon_equatorial(d)
    alt, _ = _alt_az(ra, dec, lat, lon, dt_utc)
    parallax = math.asin(1.0 / dist) / _RAD
    return alt - (0.7275 * parallax - 0.5667)


def planet_alt_az(name, lat, lon, dt_utc):
    d = _day_number(dt_utc)
    ra, dec, _ = _planet_equatorial(name, d)
    return _alt_az(ra, dec, lat, lon, dt_utc)


def planet_elongation(name, dt_utc):
    """Signed angle from the Sun along the ecliptic-ish sky: 0..360 (east of Sun is 0..180)."""
    d = _day_number(dt_utc)
    _, _, _, sun_lon, _, _ = _sun(d)
    ra, dec, _ = _planet_equatorial(name, d)
    sra, sdec, _ = _ecl_to_equ(*(_sun(d)[0:2]), 0.0, d)
    # Use right ascension difference for a simple east/west test, angular separation for size.
    cos_sep = _sind(dec) * _sind(sdec) + _cosd(dec) * _cosd(sdec) * _cosd(ra - sra)
    sep = math.acos(max(-1.0, min(1.0, cos_sep))) / _RAD
    east = _rev(ra - sra) < 180.0
    return sep if east else -sep


def _find_crossings(func, t0, t1, step_minutes=10):
    """Find times in [t0, t1] where func changes sign. Returns list of (time, 'up'|'down')."""
    out = []
    step = timedelta(minutes=step_minutes)
    ta = t0
    fa = func(ta)
    while ta < t1:
        tb = min(ta + step, t1)
        fb = func(tb)
        if (fa < 0 <= fb) or (fa > 0 >= fb):
            lo, hi, flo = ta, tb, fa
            for _ in range(24):
                mid = lo + (hi - lo) / 2
                fm = func(mid)
                if (flo < 0 <= fm) or (flo > 0 >= fm):
                    hi = mid
                else:
                    lo, flo = mid, fm
            out.append((hi, "up" if fb > fa else "down"))
        ta, fa = tb, fb
    return out


def _local_day_bounds_utc(day, tz):
    start = datetime(day.year, day.month, day.day, tzinfo=tz)
    nxt = day + timedelta(days=1)
    end = datetime(nxt.year, nxt.month, nxt.day, tzinfo=tz)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def _fmt_local(dt_utc, tz):
    return dt_utc.astimezone(tz).strftime("%I:%M %p").lstrip("0")


def moon_times(lat, lon, day, tz):
    """(moonrise, moonset) strings for the local calendar date `day`; '—' when none that day."""
    start, end = _local_day_bounds_utc(day, tz)
    crossings = _find_crossings(lambda t: _moon_alt_minus_h0(lat, lon, t), start, end, 10)
    rise = next((t for t, kind in crossings if kind == "up"), None)
    sets = next((t for t, kind in crossings if kind == "down"), None)
    return (_fmt_local(rise, tz) if rise else "—", _fmt_local(sets, tz) if sets else "—")


def _moon_elongation(dt_utc):
    d = _day_number(dt_utc)
    lon, _, _ = _moon_ecliptic(d)
    sun_lon = _sun(d)[3]
    return _rev(lon - sun_lon)


def moon_phase(dt_utc):
    """Returns (phase name, illuminated percent)."""
    e = _moon_elongation(dt_utc)
    illum = round((1.0 - _cosd(e)) / 2.0 * 100.0)
    if e < 12 or e >= 348:
        name = "New Moon"
    elif e < 78:
        name = "Waxing Crescent"
    elif e < 102:
        name = "First Quarter"
    elif e < 168:
        name = "Waxing Gibbous"
    elif e < 192:
        name = "Full Moon"
    elif e < 258:
        name = "Waning Gibbous"
    elif e < 282:
        name = "Last Quarter"
    else:
        name = "Waning Crescent"
    return name, illum


def next_moon_phase(dt_utc, target):
    """Next time (UTC) the Moon's elongation reaches `target` degrees (0 = new, 180 = full)."""
    def f(t):
        return ((_moon_elongation(t) - target + 180.0) % 360.0) - 180.0

    step = timedelta(hours=6)
    t0 = dt_utc
    f0 = f(t0)
    for _ in range(140):
        t1 = t0 + step
        f1 = f(t1)
        if f0 < 0 <= f1 and (f1 - f0) < 90:
            lo, hi = t0, t1
            for _ in range(24):
                mid = lo + (hi - lo) / 2
                if f(mid) < 0:
                    lo = mid
                else:
                    hi = mid
            return hi
        t0, f0 = t1, f1
    return None


def _compass(az):
    names = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return names[int((az + 11.25) // 22.5) % 16]


def _planets_at(lat, lon, dt_utc, min_alt=5.0):
    visible = []
    for name in PLANET_NAMES:
        try:
            alt, az = planet_alt_az(name, lat, lon, dt_utc)
            if alt >= min_alt and abs(planet_elongation(name, dt_utc)) >= 12.0:
                visible.append((name, alt, az))
        except Exception:
            continue
    visible.sort(key=lambda x: -x[1])
    return visible


def _night_window(lat, lon, now_utc, tz):
    """Return (sunset_utc, next_sunrise_utc, darkness_start_utc, darkness_end_utc) for 'tonight'."""
    local_now = now_utc.astimezone(tz)
    base_day = local_now.date() if local_now.hour >= 12 else (local_now - timedelta(days=1)).date()
    noon0 = datetime(base_day.year, base_day.month, base_day.day, 12, tzinfo=tz).astimezone(timezone.utc)
    noon1 = noon0 + timedelta(hours=24)
    sun_fn = lambda t: sun_altitude(lat, lon, t) + 0.833
    dark_fn = lambda t: sun_altitude(lat, lon, t) + 18.0
    sunsets = [t for t, k in _find_crossings(sun_fn, noon0, noon1, 10) if k == "down"]
    sunrises = [t for t, k in _find_crossings(sun_fn, noon0, noon1, 10) if k == "up"]
    d_start = [t for t, k in _find_crossings(dark_fn, noon0, noon1, 10) if k == "down"]
    d_end = [t for t, k in _find_crossings(dark_fn, noon0, noon1, 10) if k == "up"]
    return (sunsets[0] if sunsets else None, sunrises[0] if sunrises else None,
            d_start[0] if d_start else None, d_end[0] if d_end else None)


def upcoming_showers(now_utc, tz, days_ahead=60, limit=2):
    local_today = now_utc.astimezone(tz).date()
    found = []
    for name, month, day, zhr, note in _METEOR_SHOWERS:
        for year in (local_today.year, local_today.year + 1):
            try:
                peak = datetime(year, month, day).date()
            except ValueError:
                continue
            delta = (peak - local_today).days
            if 0 <= delta <= days_ahead:
                midnight = datetime(peak.year, peak.month, peak.day, 23, 59, tzinfo=tz).astimezone(timezone.utc)
                _, illum = moon_phase(midnight)
                found.append((delta, name, peak, zhr, note, illum))
                break
    found.sort()
    return found[:limit]


def astronomy_summary(lat, lon, now_utc, tz, cloud_cover_night=None):
    """Everything the Astronomy tab needs, all computed locally. Raises on bad input."""
    local_now = now_utc.astimezone(tz)
    phase, illum = moon_phase(now_utc)
    m_rise, m_set = moon_times(lat, lon, local_now.date(), tz)

    sunset, sunrise_next, dark_start, dark_end = _night_window(lat, lon, now_utc, tz)
    if dark_start and dark_end:
        darkness = f"{_fmt_local(dark_start, tz)} to {_fmt_local(dark_end, tz)} (sky fully dark)"
    elif sunset and sunrise_next:
        darkness = "No full astronomical darkness tonight (twilight lasts all night at this latitude/season)"
    else:
        darkness = "Unavailable"

    planets = []
    if sunset:
        evening = _planets_at(lat, lon, sunset + timedelta(minutes=60))
        text = "; ".join(f"{n} {a:.0f}° up, {_compass(z)}" for n, a, z in evening) if evening else "none above 5°"
        planets.append(f"Evening (about 1 hr after sunset): {text}")
    if sunrise_next:
        morning = _planets_at(lat, lon, sunrise_next - timedelta(minutes=60))
        text = "; ".join(f"{n} {a:.0f}° up, {_compass(z)}" for n, a, z in morning) if morning else "none above 5°"
        planets.append(f"Pre-dawn (about 1 hr before sunrise): {text}")
    if not planets:
        planets = ["Planet visibility unavailable"]

    moon_up_dark = False
    if dark_start and dark_end:
        mid = dark_start + (dark_end - dark_start) / 2
        moon_up_dark = moon_altitude(lat, lon, mid) > 0
    stargazing = None
    if cloud_cover_night is not None:
        penalty = illum * (0.30 if moon_up_dark else 0.08)
        score = int(max(0, min(100, round(100 - cloud_cover_night * 0.8 - penalty))))
        label = "Excellent" if score >= 85 else "Good" if score >= 65 else "Fair" if score >= 40 else "Poor"
        stargazing = (f"{score}/100 ({label}) — estimate from ~{round(cloud_cover_night)}% overnight cloud cover "
                      f"and a {illum}% illuminated Moon{' above the horizon' if moon_up_dark else ''}")

    events = []
    nf = next_moon_phase(now_utc, 180.0)
    nn = next_moon_phase(now_utc, 0.0)
    for title, when in (("🌕 Next Full Moon", nf), ("🌑 Next New Moon", nn)):
        if when:
            events.append({
                "title": title,
                "time": when.astimezone(tz).strftime("%a %b %d, %I:%M %p %Z").replace(" 0", " "),
                "direction": "",
                "notes": "Computed from lunar orbital elements",
            })
    for delta, name, peak, zhr, note, m_illum in upcoming_showers(now_utc, tz):
        moon_note = "dark skies (Moon barely lit)" if m_illum < 25 else "moonlight will wash out fainter meteors" if m_illum > 60 else "some moonlight"
        when = "tonight" if delta == 0 else f"in {delta} days"
        events.append({
            "title": f"☄️ {name} meteor shower",
            "time": f"Peak ~{peak.strftime('%b %d').replace(' 0', ' ')} ({when})",
            "direction": "",
            "notes": f"Up to ~{zhr}/hr under ideal skies; {note}. Moon {m_illum}% lit — {moon_note}.",
        })

    return {
        "moon_phase": f"{phase} ({illum}% illuminated)",
        "moon_rise": m_rise,
        "moon_set": m_set,
        "darkness_window": darkness,
        "stargazing_rating": stargazing or "Unavailable (no cloud-cover forecast for tonight)",
        "visible_planets": planets,
        "celestial_events": events,
    }
