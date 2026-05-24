import os
import json
import time
import threading
import requests
import anthropic
from datetime import datetime, timedelta, timezone, date
from flask import Flask, jsonify, render_template

app = Flask(__name__)

# ---------------------------------------------------------------------------
# River configuration
# ---------------------------------------------------------------------------

RIVERS = [
    {
        "id": "09188500",
        "name": "Green River",
        "full_name": "Green River near Warren Bridge, WY",
        "lat": 42.93,
        "lon": -109.97,
        "image_file": "green-river.jpg",
        "photo_gradient": "linear-gradient(160deg, #1a3a2e 0%, #2a6b52 50%, #1a4f6e 100%)",
    },
    {
        "id": "09205000",
        "name": "New Fork River",
        "full_name": "New Fork River near Big Piney, WY",
        "lat": 42.62,
        "lon": -110.11,
        "image_file": "new-fork.jpg",
        "photo_gradient": "linear-gradient(160deg, #2a2e1a 0%, #4a5830 50%, #3a4a3a 100%)",
    },
    {
        "id": "09211200",
        "name": "Seedskadee",
        "full_name": "Green River below Fontenelle Dam, WY",
        "lat": 41.97,
        "lon": -109.57,
        "image_file": "seedskadee.jpg",
        "photo_gradient": "linear-gradient(160deg, #1a3a4a 0%, #2a6868 50%, #1e4a3a 100%)",
    },
]

RIVER_MAP = {r["id"]: r for r in RIVERS}

# ---------------------------------------------------------------------------
# Static river guide & hatch data
# ---------------------------------------------------------------------------

HATCH_CHART = {
    "09188500": {  # Green River at Warren Bridge
        1:  ["Midge #18-22"],
        2:  ["Midge #18-22", "BWO #18-22"],
        3:  ["BWO #18-22", "Midge #18-22"],
        4:  ["BWO #18-22", "Midge #18-22", "Skwala #8-10"],
        5:  ["Salmonfly #4-8", "Golden Stone #6-8", "BWO #18-22", "Caddis #14-16"],
        6:  ["Salmonfly #4-8", "Golden Stone #6-8", "PMD #16-18", "Caddis #14-16", "Yellow Sally #14-16"],
        7:  ["PMD #16-18", "Hopper #4-10", "Caddis #14-16", "Yellow Sally #14-16", "Trico #20-22"],
        8:  ["Hopper #4-10", "Trico #20-22", "Beetle #14-18", "Ant #14-18", "Caddis #14-16"],
        9:  ["BWO #18-22", "Hopper #4-10", "Trico #20-22", "Midge #18-22"],
        10: ["BWO #18-22", "Midge #18-22"],
        11: ["Midge #18-22", "BWO #18-22"],
        12: ["Midge #18-22"],
    },
    "09205000": {  # New Fork River
        1:  ["Midge #18-22"],
        2:  ["Midge #18-22", "BWO #18-22"],
        3:  ["BWO #18-22", "Midge #18-22"],
        4:  ["BWO #18-22", "Midge #18-22"],
        5:  ["Salmonfly #4-8", "Golden Stone #6-8", "Caddis #14-16", "BWO #18-22"],
        6:  ["Golden Stone #6-8", "PMD #16-18", "Caddis #14-16", "Yellow Sally #14-16"],
        7:  ["PMD #16-18", "Hopper #4-10", "Caddis #14-16", "Trico #20-22"],
        8:  ["Hopper #4-10", "Trico #20-22", "Beetle #14-18", "Ant #14-18"],
        9:  ["BWO #18-22", "Hopper #4-10", "Midge #18-22"],
        10: ["BWO #18-22", "Midge #18-22"],
        11: ["Midge #18-22", "BWO #18-22"],
        12: ["Midge #18-22"],
    },
    "09211200": {  # Seedskadee / Green River below Fontenelle Dam
        1:  ["Midge #18-22", "BWO #20-22"],
        2:  ["Midge #18-22", "BWO #20-22"],
        3:  ["BWO #20-22", "Midge #18-22"],
        4:  ["BWO #20-22", "Midge #18-22", "Caddis #14-16"],
        5:  ["PMD #16-18", "Caddis #14-16", "BWO #20-22"],
        6:  ["PMD #16-18", "Caddis #14-16", "Yellow Sally #14-16"],
        7:  ["PMD #16-18", "Hopper #4-10", "Caddis #14-16", "Trico #20-22"],
        8:  ["Hopper #4-10", "Trico #20-22", "Beetle #14-18", "Caddis #14-16"],
        9:  ["BWO #20-22", "Midge #18-22", "Hopper #4-10"],
        10: ["BWO #20-22", "Midge #18-22"],
        11: ["Midge #18-22", "BWO #20-22"],
        12: ["Midge #18-22"],
    },
}

ROAD_ACCESS = {
    "09188500": {
        "access_road": "US-191 north from Pinedale to Warren Bridge",
        "agency": "Wyoming Game & Fish / BLM Pinedale Field Office",
        "conditions_url": "https://www.blm.gov/office/pinedale-field-office",
    },
    "09205000": {
        "access_road": "US-189 south from Pinedale toward Big Piney",
        "agency": "Wyoming Game & Fish",
        "conditions_url": "https://wgfd.wyo.gov",
    },
    "09211200": {
        "access_road": "WY-28 west from Farson, then north to Seedskadee NWR",
        "agency": "Seedskadee National Wildlife Refuge / USFWS",
        "conditions_url": "https://www.fws.gov/refuge/seedskadee",
    },
}

RIVER_GUIDE = {
    "09188500": {
        "character": "Freestone river flowing through high desert sagebrush. Famous for prolific salmonfly and golden stonefly hatches in late May/June. Cold, clear water with good populations of wild browns and rainbows. Accessible via Warren Bridge — walk upstream or downstream from access points.",
        "techniques": "Dry fly during salmonfly/golden stone hatch (late May–June) with large attractors. Summer: hopper-dropper and PMD dries during afternoon hatches. Spring/fall: nymphing with stonefly and BWO patterns. Fish seams and cut banks for big browns.",
        "species": "Wild brown trout, rainbow trout",
        "notes": "Access via Warren Bridge. Check WGFD for current regulations. High runoff typically April–June.",
    },
    "09205000": {
        "character": "Classic Wyoming freestone river through open meadows and canyon sections. Less crowded than the Green River. Strong golden stone and caddis hatches. Good brown trout fishery with some large fish in slower pools.",
        "techniques": "Nymph during runoff with heavy stonefly rigs. Summer: hoppers and PMDs. Fish slower pools and undercut banks for big browns. Streamer fishing effective in fall.",
        "species": "Brown trout, rainbow trout",
        "notes": "Running low but fishing well in spring. Check WGFD regulations.",
    },
    "09211200": {
        "character": "Tailwater below Fontenelle Dam through the Seedskadee National Wildlife Refuge. Consistent cold flows year-round. Exceptional sight fishing for large wild browns in clear water. Remote and lightly pressured.",
        "techniques": "Technical dry fly and nymph fishing. Midges and BWOs year-round. Summer PMDs and caddis. Sight fishing to rising fish. Long leaders and fine tippets (5x-6x). Streamer fishing in fall for big browns.",
        "species": "Wild brown trout, rainbow trout",
        "notes": "Access through Seedskadee NWR — free entry. Primitive roads, high-clearance vehicle recommended. Solid fishing below dam.",
    },
}

# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

_cache = {}
RIVER_TTL   = 15 * 60        # 15 minutes
WEATHER_TTL = 60 * 60        # 60 minutes
REPORT_TTL  = 24 * 60 * 60   # 24 hours
ROAD_TTL    = 60 * 60        # 1 hour

REPORT_CACHE_FILE = "/tmp/wyoming_report_cache.json"

def _load_report_file_cache():
    try:
        with open(REPORT_CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def _save_report_file_cache(cache):
    try:
        with open(REPORT_CACHE_FILE, "w") as f:
            json.dump(cache, f)
    except Exception:
        pass

_report_file_cache = _load_report_file_cache()

def cached(key, ttl, fetch_fn):
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"]) < ttl:
        return entry["data"]
    data = fetch_fn()
    _cache[key] = {"ts": time.time(), "data": data}
    return data

def cached_report(site_id):
    entry = _report_file_cache.get(site_id)
    if entry and (time.time() - entry["ts"]) < REPORT_TTL:
        return entry["data"]
    data = generate_report(site_id)
    _report_file_cache[site_id] = {"ts": time.time(), "data": data}
    _save_report_file_cache(_report_file_cache)
    return data

def _prewarm_reports():
    time.sleep(8)
    for river in RIVERS:
        try:
            cached_report(river["id"])
        except Exception as e:
            print(f"Prewarm failed for {river['id']}: {e}")

threading.Thread(target=_prewarm_reports, daemon=True).start()


# ---------------------------------------------------------------------------
# USGS river flow
# ---------------------------------------------------------------------------

def fetch_usgs():
    site_ids = ",".join(r["id"] for r in RIVERS)
    url = (
        "https://waterservices.usgs.gov/nwis/iv/"
        f"?sites={site_ids}&parameterCd=00060,00010&format=json&period=P7D"
    )
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    raw = resp.json()

    result = {}
    for series in raw.get("value", {}).get("timeSeries", []):
        site_id = series["sourceInfo"]["siteCode"][0]["value"]
        param = series["variable"]["variableCode"][0]["value"]
        values = series["values"][0]["value"]

        parsed = []
        for v in values:
            try:
                parsed.append({"t": v["dateTime"], "v": float(v["value"])})
            except (ValueError, TypeError):
                continue

        if site_id not in result:
            result[site_id] = {}

        if param == "00060":
            result[site_id]["flow"] = parsed
            result[site_id]["current_cfs"] = parsed[-1]["v"] if parsed else None
        elif param == "00010":
            if parsed and parsed[-1]["v"] is not None:
                result[site_id]["water_temp_f"] = round(parsed[-1]["v"] * 9 / 5 + 32, 1)

    return result


# ---------------------------------------------------------------------------
# NWS weather & barometric pressure
# ---------------------------------------------------------------------------

def fetch_weather(site_id):
    river = RIVER_MAP[site_id]
    lat, lon = river["lat"], river["lon"]
    headers = {"User-Agent": "fishing-dashboard/1.0"}

    r = requests.get(f"https://api.weather.gov/points/{lat},{lon}", headers=headers, timeout=15)
    r.raise_for_status()
    props = r.json()["properties"]

    r = requests.get(props["forecastGridData"], headers=headers, timeout=30)
    r.raise_for_status()
    grid = r.json()["properties"]

    def parse_vals(key, convert=None):
        out = []
        for v in grid.get(key, {}).get("values", []):
            val = v.get("value")
            if val is not None:
                out.append(convert(val) if convert else val)
        return out

    temps_f    = parse_vals("temperature",               lambda c: round(c * 9/5 + 32, 1))
    winds_mph  = parse_vals("windSpeed",                 lambda k: round(k * 0.621371, 1))
    precips_in = parse_vals("quantitativePrecipitation", lambda mm: mm * 0.0393701)

    stations_r = requests.get(props["observationStations"], headers=headers, timeout=15)
    stations_r.raise_for_status()
    station_id = stations_r.json()["features"][0]["properties"]["stationIdentifier"]

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=7)
    obs_url = (
        f"https://api.weather.gov/stations/{station_id}/observations"
        f"?start={start.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        f"&end={end.strftime('%Y-%m-%dT%H:%M:%SZ')}&limit=168"
    )
    obs_r = requests.get(obs_url, headers=headers, timeout=15)
    obs_r.raise_for_status()
    observations = list(reversed(obs_r.json()["features"]))

    press_inhg, times = [], []
    for obs in observations:
        p = obs["properties"].get("barometricPressure", {}).get("value")
        t = obs["properties"].get("timestamp")
        if p is not None and t:
            press_inhg.append(round(p * 0.0002953, 2))
            times.append(t)

    current_pressure = press_inhg[-1] if press_inhg else None
    trend = "Steady"
    if len(press_inhg) >= 4:
        diff = press_inhg[-1] - press_inhg[-4]
        if diff > 0.02:
            trend = "Rising"
        elif diff < -0.02:
            trend = "Falling"

    return {
        "times": times,
        "pressure_inhg": press_inhg,
        "current_pressure_inhg": current_pressure,
        "pressure_trend": trend,
        "temp_min_f": round(min(temps_f), 1) if temps_f else None,
        "temp_max_f": round(max(temps_f), 1) if temps_f else None,
        "precip_total_in": round(sum(precips_in), 2) if precips_in else 0,
        "wind_avg_mph": round(sum(winds_mph) / len(winds_mph), 1) if winds_mph else None,
    }


# ---------------------------------------------------------------------------
# AI fishing report generation
# ---------------------------------------------------------------------------

def generate_report(site_id):
    river = RIVER_MAP[site_id]
    guide = RIVER_GUIDE.get(site_id, {})
    month = datetime.now().month
    month_name = datetime.now().strftime("%B")
    hatches = HATCH_CHART.get(site_id, {}).get(month, [])

    try:
        usgs = fetch_usgs()
        river_data = usgs.get(site_id, {})
        flow = river_data.get("current_cfs")
        water_temp = river_data.get("water_temp_f")
    except Exception:
        flow, water_temp = None, None

    try:
        weather = fetch_weather(site_id)
        pressure = weather.get("current_pressure_inhg")
        pressure_trend = weather.get("pressure_trend")
        temp_min = weather.get("temp_min_f")
        temp_max = weather.get("temp_max_f")
        precip = weather.get("precip_total_in", 0)
        wind = weather.get("wind_avg_mph")
    except Exception:
        pressure = pressure_trend = temp_min = temp_max = wind = None
        precip = 0

    prompt = f"""You are an expert fly fishing guide writing a current fishing report for {river['full_name']}.

Current conditions:
- Flow: {flow} CFS
- Water temperature: {water_temp}°F
- Air temp range (past 7 days): {temp_min}–{temp_max}°F
- Barometric pressure: {pressure} inHg ({pressure_trend})
- Precipitation (past 7 days): {precip} inches
- Wind avg: {wind} mph
- Month: {month_name}
- Active hatches: {', '.join(hatches) if hatches else 'None listed'}

River character: {guide.get('character', '')}
Recommended techniques: {guide.get('techniques', '')}
Species: {guide.get('species', '')}
Notes: {guide.get('notes', '')}

Write a 3–4 sentence fishing report in the style of a knowledgeable local guide. Be specific about current flows, expected hatches, recommended flies, and tactics. Keep it practical and concise."""

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )

    return {
        "text": response.content[0].text,
        "source": "AI Report",
        "date": datetime.now().strftime("%B %-d, %Y"),
        "url": None,
    }


# ---------------------------------------------------------------------------
# Road access info
# ---------------------------------------------------------------------------

def get_road_info(site_id):
    access = ROAD_ACCESS.get(site_id, {})
    return {
        "text": f"Access via {access.get('access_road', 'N/A')}. Managed by {access.get('agency', 'N/A')}.",
        "access_road": access.get("access_road"),
        "agency": access.get("agency"),
        "conditions_url": access.get("conditions_url"),
    }


# ---------------------------------------------------------------------------
# Flask routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html", rivers=RIVERS)


@app.route("/api/rivers")
def api_rivers():
    try:
        usgs = cached("usgs_all", RIVER_TTL, fetch_usgs)
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    result = []
    for river in RIVERS:
        site_id = river["id"]
        data = usgs.get(site_id, {})
        result.append({
            "id": site_id,
            "name": river["name"],
            "full_name": river["full_name"],
            "current_cfs": data.get("current_cfs"),
            "water_temp_f": data.get("water_temp_f"),
            "flow_history": data.get("flow", []),
        })

    return jsonify(result)


@app.route("/api/weather/<site_id>")
def api_weather(site_id):
    if site_id not in RIVER_MAP:
        return jsonify({"error": "Unknown site"}), 404
    try:
        data = cached(f"weather_{site_id}", WEATHER_TTL, lambda: fetch_weather(site_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 502
    return jsonify(data)


@app.route("/api/weather-all")
def api_weather_all():
    result = {}
    for river in RIVERS:
        site_id = river["id"]
        try:
            data = cached(f"weather_{site_id}", WEATHER_TTL, lambda s=site_id: fetch_weather(s))
            result[site_id] = data
        except Exception as e:
            result[site_id] = {"error": str(e)}
    return jsonify(result)


@app.route("/api/reports/<site_id>")
def api_reports(site_id):
    if site_id not in RIVER_MAP:
        return jsonify({"error": "Unknown site"}), 404

    try:
        live_report = cached_report(site_id)
    except Exception as e:
        print(f"Report generation error ({site_id}): {e}")
        live_report = None

    month = datetime.now().month
    return jsonify({
        "live_report": live_report,
        "current_hatch": HATCH_CHART.get(site_id, {}).get(month, []),
        "guide": RIVER_GUIDE.get(site_id, {}),
        "month_name": datetime.now().strftime("%B"),
        "regulations": {"is_closed": False, "reg_sections": []},
    })


@app.route("/api/road-access/<site_id>")
def api_road_access(site_id):
    if site_id not in RIVER_MAP:
        return jsonify({"error": "Unknown site"}), 404
    data = cached(f"road_{site_id}", ROAD_TTL, lambda: get_road_info(site_id))
    return jsonify(data)


if __name__ == "__main__":
    app.run(debug=False, port=5001)
