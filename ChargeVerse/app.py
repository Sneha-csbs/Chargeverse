"""
ChargeVerse — Autonomous EV Fleet Command Portal
================================================
Futuristic Green Cyber Energy Operations Center
NVIDIA Omniverse & Tesla Energy Inspired Multi-Agent Bidding Engine
"""

from __future__ import annotations

import json
import logging
import math
import time
from pathlib import Path
from typing import Any


# Resolve paths relative to this file so the app works regardless of CWD
_BASE_DIR            = Path(__file__).parent
_LOGO_PATH           = _BASE_DIR / "images" / "logo.png"
_STATIONS_DB_FILE    = _BASE_DIR / "stations_db.json"
_STATION_STATE_FILE  = _BASE_DIR / "station_state.json"

import streamlit as st
from PIL import Image
from geopy.distance import geodesic
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable, GeocoderRateLimited, GeocoderQuotaExceeded, GeopyError
from geopy.geocoders import Nominatim
from streamlit_geolocation import streamlit_geolocation

from fleet_agent import FacilityType, FleetEVTelemetry, GatePassRequest, StationConsoleState
from broker_agent import AuctionRequestPayload, BrokerAuctioneerAgent, ClearedBid
from dynamic_pricing_agent import DynamicPricingAgent, DynamicTariffOutput
from security_pass_agent import GatePassPayload, SecurityPassAgent
from fintech_agent import FinTechSettlementAgent, InvoiceBreakdown
from weather_agent import WeatherImpactAgent, WeatherImpactPayload
from reputation_agent import StationReputationAgent, ReputationScorePayload
from fleet_agent import YardHostPayload



# ── page config ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ChargeVerse — Autonomous Fleet Command",
    page_icon=Image.open(_LOGO_PATH),
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── custom expander CSS ───────────────────────────────────────────────
st.markdown("""
<style>
/* Streamlit Expander Cyberpunk Theme Fix */
div[data-testid="stExpander"] {
    background-color: rgba(14, 26, 18, 0.85) !important;
    border: 1.5px solid rgba(0, 255, 136, 0.30) !important;
    border-radius: 14px !important;
    margin-bottom: 16px !important;
}

div[data-testid="stExpander"] details summary {
    background-color: rgba(14, 26, 18, 0.95) !important;
    border-radius: 12px !important;
    padding: 12px 16px !important;
}

div[data-testid="stExpander"] details summary span p,
div[data-testid="stExpander"] details summary span,
div[data-testid="stExpander"] details summary div,
div[data-testid="stExpander"] details summary * {
    color: #00FF88 !important;
    font-weight: 700 !important;
}

div[data-testid="stExpander"] details summary:hover {
    background-color: rgba(0, 255, 136, 0.12) !important;
}

div[data-testid="stExpander"] details summary:hover span p,
div[data-testid="stExpander"] details summary:hover span {
    color: #00FF88 !important;
}
</style>
""", unsafe_allow_html=True)

# ── demo credentials ──────────────────────────────────────────────────
CREDENTIALS: dict[str, dict[str, str]] = {
    "driver": {
        "password": "driver123",
        "role": "driver",
        "name": "Fleet Driver (EV-CV-001)",
        "icon": "🚚",
    },
    "solar_hub": {
        "password": "station123",
        "role": "station_a",
        "name": "[Private] BLR Solar Yard (Electronic City)",
        "icon": "🛡️",
    },
    "station_a": {
        "password": "station123",
        "role": "station_a",
        "name": "[Private] BLR Solar Yard (Electronic City)",
        "icon": "🛡️",
    },
    "grid_hub": {
        "password": "station123",
        "role": "station_b",
        "name": "[Public] Hosur EV Point (NH-44 Hub)",
        "icon": "⚡",
    },
    "station_b": {
        "password": "station123",
        "role": "station_b",
        "name": "[Public] Hosur EV Point (NH-44 Hub)",
        "icon": "⚡",
    },
    "whitefield_hub": {
        "password": "station123",
        "role": "station_c",
        "name": "[Private] Whitefield Tech Hub (ITPB Corridor)",
        "icon": "🛡️",
    },
    "station_c": {
        "password": "station123",
        "role": "station_c",
        "name": "[Private] Whitefield Tech Hub (ITPB Corridor)",
        "icon": "🛡️",
    },
    "silkboard_hub": {
        "password": "station123",
        "role": "station_d",
        "name": "[Public] Silk Board Depot (Central Transit)",
        "icon": "⚡",
    },
    "station_d": {
        "password": "station123",
        "role": "station_d",
        "name": "[Public] Silk Board Depot (Central Transit)",
        "icon": "⚡",
    },
    "krishnagiri_hub": {
        "password": "station123",
        "role": "station_e",
        "name": "[Public] Krishnagiri Plaza (NH-44 Highway)",
        "icon": "⚡",
    },
    "station_e": {
        "password": "station123",
        "role": "station_e",
        "name": "[Public] Krishnagiri Plaza (NH-44 Highway)",
        "icon": "⚡",
    },
    "hosur_terminal": {
        "password": "station123",
        "role": "station_f",
        "name": "[Private] Hosur Freight Terminal (YARD-HSR-003)",
        "icon": "🛡️",
    },
    "station_f": {
        "password": "station123",
        "role": "station_f",
        "name": "[Private] Hosur Freight Terminal (YARD-HSR-003)",
        "icon": "🛡️",
    },
    "peenya_hub": {
        "password": "station123",
        "role": "station_g",
        "name": "[Private] Peenya EV Logistics Hub (YARD-PNY-004)",
        "icon": "🛡️",
    },
    "station_g": {
        "password": "station123",
        "role": "station_g",
        "name": "[Private] Peenya EV Logistics Hub (YARD-PNY-004)",
        "icon": "🛡️",
    },
}



# ── constants ──────────────────────────────────────────────────────────
_CARGO: dict[str, tuple[str, float, str, bool]] = {
    # Cold Chain & Perishables
    "Pharmaceuticals / Vaccines":       ("💊", 1.00, "Urgent SLA: Temperature-sensitive", True),
    "Frozen Foods / Ice Cream":         ("🧊", 0.95, "Critical SLA: High urgency refrigeration", True),
    "Fresh Produce & Dairy":            ("🥛", 0.75, "High SLA: Perishable produce", False),
    # Time-Critical Logistics
    "Hazardous Materials / Chemicals":  ("☣️", 0.85, "Specialized SLA: Safety & dedicated yards", False),
    "Automotive / Manufacturing Parts": ("⚙️", 0.80, "High SLA: Just-In-Time assembly line", False),
    "Express E-Commerce Parcels":       ("📦", 0.70, "High SLA: Strict delivery deadline", False),
    # Standard / Non-Perishable Cargo
    "General Retail Freight":           ("🛍️", 0.40, "Standard SLA: Balanced speed vs cost", False),
    "Dry Bulk Goods / Grain":           ("🌾", 0.20, "Normal SLA: Flexible charging timeline", False),
    "Construction Materials":           ("🏗️", 0.15, "Normal SLA: Low urgency off-peak", False),
    # Legacy alias support
    "Ice Cream (Perishable)":           ("🧊", 0.95, "Critical SLA: High urgency refrigeration", True),
    "Vaccines / Medicine":              ("💊", 1.00, "Urgent SLA: Temperature-sensitive", True),
    "Electronic Goods":                 ("📱", 0.50, "Standard SLA: Balanced", False),
    "Dry Freight":                      ("📦", 0.20, "Normal SLA: Flexible", False),
}
_DEFAULT_BATT:    float = 100.0  # slider default start value

_STEP_KM:         float = 2.0
_STEP_DRAIN:      float = 1.5   # % per click
_DRAIN_RATE:      float = 0.75  # % per km for required battery calc
_SAFETY_BUFFER:   float = 5.0   # % flat safety margin


# ── default station coordinates & specs ─────────────────────────────────
STATIONS_DEFAULTS: dict[str, dict[str, Any]] = {
    "station_a": {
        "id":                       "station_a",
        "name":                     "[Private] BLR Solar Yard",
        "short":                    "Electronic City Hub",
        "facility_type":            "PRIVATE_YARD",
        "charger":                  "250 kW Ultra-Fast DC",
        "description":              "250 kW · Solar Energy Hub",
        "lat":                      12.9342,
        "lon":                      77.6101,
        "price_per_kwh":            0.22,
        "rating":                   4.9,
        "uptime_pct":               99.5,
        "queue_length":             0,
        "max_queue":                5,
        "status":                   "Available",
        "eta_minutes":              6,
        "passcode":                 "#BLR-808-GATE",
        "kw":                       250.0,
        "total_capacity_kw":        250.0,
        "safety_buffer_percentage": 70.0,
    },
    "station_b": {
        "id":                       "station_b",
        "name":                     "[Public] Hosur EV Point",
        "short":                    "NH-44 Expressway Hub",
        "facility_type":            "PUBLIC_STATION",
        "charger":                  "120 kW Fast Charger",
        "description":              "120 kW · Grid-Tied Hub",
        "lat":                      12.7409,
        "lon":                      77.8253,
        "price_per_kwh":            0.28,
        "rating":                   3.2,
        "uptime_pct":               86.5,
        "queue_length":             3,
        "max_queue":                8,
        "status":                   "Available",
        "eta_minutes":              18,
        "passcode":                 "#HOS-412-EV",
        "kw":                       120.0,
        "total_capacity_kw":        120.0,
        "safety_buffer_percentage": 70.0,
    },
    "station_c": {
        "id":                       "station_c",
        "name":                     "[Private] Whitefield Tech Hub",
        "short":                    "ITPB Corridor Station",
        "facility_type":            "PRIVATE_YARD",
        "charger":                  "180 kW Dual DC Charger",
        "description":              "180 kW · Tech Corridor Hub",
        "lat":                      12.9698,
        "lon":                      77.7500,
        "price_per_kwh":            0.24,
        "rating":                   4.7,
        "uptime_pct":               98.2,
        "queue_length":             1,
        "max_queue":                6,
        "status":                   "Available",
        "eta_minutes":              14,
        "passcode":                 "#WFD-990-TECH",
        "kw":                       180.0,
        "total_capacity_kw":        180.0,
        "safety_buffer_percentage": 70.0,
    },
    "station_d": {
        "id":                       "station_d",
        "name":                     "[Public] Silk Board Metro Depot",
        "short":                    "Central Transit Yard",
        "facility_type":            "PUBLIC_STATION",
        "charger":                  "300 kW HyperCharge DC",
        "description":              "300 kW · High-Cap Fleet Hub",
        "lat":                      12.9172,
        "lon":                      77.6228,
        "price_per_kwh":            0.30,
        "rating":                   4.3,
        "uptime_pct":               96.0,
        "queue_length":             2,
        "max_queue":                10,
        "status":                   "Available",
        "eta_minutes":              9,
        "passcode":                 "#SLK-300-HYPER",
        "kw":                       300.0,
        "total_capacity_kw":        300.0,
        "safety_buffer_percentage": 70.0,
    },
    "station_e": {
        "id":                       "station_e",
        "name":                     "[Public] Krishnagiri Highway Plaza",
        "short":                    "NH-44 Toll Plaza Depot",
        "facility_type":            "PUBLIC_STATION",
        "charger":                  "150 kW Highway DC Charger",
        "description":              "150 kW · Inter-state Freight Hub",
        "lat":                      12.5186,
        "lon":                      78.2137,
        "price_per_kwh":            0.25,
        "rating":                   3.1,
        "uptime_pct":               88.0,
        "queue_length":             0,
        "max_queue":                7,
        "status":                   "Available",
        "eta_minutes":              25,
        "passcode":                 "#KGI-150-HIGHWAY",
        "kw":                       150.0,
        "total_capacity_kw":        150.0,
        "safety_buffer_percentage": 70.0,
    },
    "station_f": {
        "id":                       "station_f",
        "name":                     "[Private] Hosur Freight Terminal",
        "short":                    "Hosur Industrial Belt, TN",
        "facility_type":            "PRIVATE_YARD",
        "charger":                  "250 kW Ultra-Fast DC",
        "description":              "250 kW · Freight Terminal Yard",
        "lat":                      12.7409,
        "lon":                      77.8253,
        "price_per_kwh":            0.21,
        "rating":                   4.8,
        "uptime_pct":               99.1,
        "queue_length":             0,
        "max_queue":                5,
        "status":                   "Available",
        "eta_minutes":              16,
        "passcode":                 "#HSR-808-GATE",
        "kw":                       250.0,
        "total_capacity_kw":        250.0,
        "safety_buffer_percentage": 70.0,
    },
    "station_g": {
        "id":                       "station_g",
        "name":                     "[Private] Peenya EV Logistics Hub",
        "short":                    "Peenya Industrial Area, Bengaluru",
        "facility_type":            "PRIVATE_YARD",
        "charger":                  "300 kW HyperCharge DC",
        "description":              "300 kW · Industrial Logistics Hub",
        "lat":                      13.0285,
        "lon":                      77.5197,
        "price_per_kwh":            0.22,
        "rating":                   4.4,
        "uptime_pct":               95.5,
        "queue_length":             0,
        "max_queue":                6,
        "status":                   "Available",
        "eta_minutes":              12,
        "passcode":                 "#PNY-909-GATE",
        "kw":                       300.0,
        "total_capacity_kw":        300.0,
        "safety_buffer_percentage": 70.0,
    },
}






_log = logging.getLogger("chargeverse")


# ══════════════════════════════════════════════════════════════════════
# SHARED PERSISTENT STATION & REQUEST DATABASE (stations_db.json)
# ══════════════════════════════════════════════════════════════════════


def check_active_vehicle_booking() -> tuple[str | None, dict[str, Any] | None, dict[str, Any] | None]:
    """Scans stations_db.json for active reservation following explicit lifecycle: ACCEPTED_WINNER, GATE_PASS_ISSUED, CHARGING_IN_PROGRESS."""
    db = load_stations_db()
    active_reqs = db.get("active_requests", {})
    ev_req = active_reqs.get("EV-CV-001", {})
    
    valid_statuses = ["ACCEPTED_WINNER", "GATE_PASS_ISSUED", "APPROVED_GATE_PASS", "ACCEPTED", "CHARGING_IN_PROGRESS"]
    
    if isinstance(ev_req, dict) and ev_req.get("status") in valid_statuses:
        accepted_sid = ev_req.get("accepted_by")
        if accepted_sid:
            stations = db.get("stations", {})
            st_data = stations.get(accepted_sid, {})
            if not st_data:
                st_data = STATIONS_DEFAULTS.get(accepted_sid, {})
            return accepted_sid, st_data, ev_req
            
    stations = db.get("stations", {})
    for sid, sdata in stations.items():
        if sdata.get("status") in valid_statuses:
            return sid, sdata, ev_req
            
    return None, None, None


def load_stations_db() -> dict[str, Any]:
    return _load_stations_db()

def save_stations_db(data: dict[str, Any]) -> None:
    _save_stations_db(data)

def _load_stations_db() -> dict[str, Any]:
    """Load stations database & active vehicle requests from stations_db.json.
    Supports backward compatibility with legacy station_state.json format."""
    raw_data = None
    if _STATIONS_DB_FILE.exists():
        try:
            raw_data = json.loads(_STATIONS_DB_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            _log.warning("Failed to load stations_db.json: %s", exc)
    elif _STATION_STATE_FILE.exists():
        try:
            raw_data = json.loads(_STATION_STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            _log.warning("Failed to load legacy station_state.json: %s", exc)

    stations = {}
    active_requests = {}

    if isinstance(raw_data, dict):
        if "stations" in raw_data:
            stations = raw_data.get("stations", {})
            active_requests = raw_data.get("active_requests", {})
        else:
            # legacy format where root dict is stations map
            stations = raw_data

    for sid, sdef in STATIONS_DEFAULTS.items():
        if sid not in stations:
            stations[sid] = {
                "status": sdef["status"],
                "price_per_kwh": sdef["price_per_kwh"],
                "queue_length": sdef["queue_length"],
                "kw": sdef["kw"],
            }

    return {"stations": stations, "active_requests": active_requests}


def _save_stations_db(updates: dict[str, Any]) -> None:
    """Merge updates into stations_db.json and write atomically."""
    current = _load_stations_db()
    if "stations" in updates:
        for sid, fields in updates["stations"].items():
            if sid not in current["stations"]:
                current["stations"][sid] = {}
            current["stations"][sid].update(fields)
    if "active_requests" in updates:
        if "active_requests" not in current:
            current["active_requests"] = {}
        for vid, req in updates["active_requests"].items():
            if vid not in current["active_requests"]:
                current["active_requests"][vid] = {}
            if req is None:
                current["active_requests"].pop(vid, None)
            else:
                current["active_requests"][vid].update(req)

    try:
        _STATIONS_DB_FILE.write_text(
            json.dumps(current, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        _log.error("Failed to write stations_db.json: %s", exc)


def _load_shared_station_state() -> dict[str, dict[str, Any]]:
    return _load_stations_db()["stations"]


def _save_shared_station_state(updates: dict[str, dict[str, Any]]) -> None:
    _save_stations_db({"stations": updates})


def _get_live_stations() -> dict[str, dict[str, Any]]:
    shared = _load_shared_station_state()
    live = {}
    for sid, sdef in STATIONS_DEFAULTS.items():
        s = dict(sdef)
        p = shared.get(sid, {})
        s["status"]                     = p.get("status", sdef["status"])
        s["price_per_kwh"]              = float(p.get("price_per_kwh", sdef["price_per_kwh"]))
        s["queue_length"]               = int(p.get("queue_length", sdef["queue_length"]))
        kw_val                          = float(p.get("kw", sdef["kw"]))
        s["kw"]                         = kw_val
        s["total_capacity_kw"]          = kw_val
        s["charger"]                    = f"{int(kw_val)} kW Charger"
        s["facility_type"]              = p.get("facility_type", sdef.get("facility_type", "PUBLIC_STATION"))

        # Reserve Buffer & Idle Capacity Engine
        safety_buf                      = float(p.get("safety_buffer_percentage", sdef.get("safety_buffer_percentage", 70.0)))
        s["safety_buffer_percentage"]   = safety_buf
        s["listed_idle_capacity_pct"]   = max(0.0, 100.0 - safety_buf)
        s["reserved_internal_kw"]       = round(kw_val * (safety_buf / 100.0), 1)
        s["available_power_kw"]         = round(kw_val * ((100.0 - safety_buf) / 100.0), 1)
        s["listed_idle_capacity_kw"]    = s["available_power_kw"]

        live[sid]                       = s
    return live




# ── GEOFENCE QUEUE ENGINE & HAVERSINE METRICS ───────────────────────

def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on Earth in meters."""
    R = 6371000  # Radius of Earth in meters
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_station_queue_status(station_id: str, geofence_radius_meters: float = 150.0) -> dict[str, Any]:
    """
    Geofence Queue Calculation Logic:
    1. Retrieve target station's coordinates (station_lat, station_lon) from STATIONS_DEFAULTS / stations_db.json.
    2. Query all active vehicle telemetry records in the system.
    3. Count a vehicle as 'QUEUED' if:
       - Distance to station <= 150 meters (Inside Geofence).
       - Speed < 5.0 km/h (Stationary / Creeping).
       - Vehicle status is NOT 'CHARGING' (Not plugged in).
       - Vehicle ID is NOT present in the station's active OCPP plug session list.
    4. Calculate Estimated Queue Delay = Queued Vehicles Count * 20 mins (Avg Charge Session Time).
    """
    db_store = _load_stations_db()
    st_meta = STATIONS_DEFAULTS.get(station_id, {})

    st_lat = st_meta.get("lat", 12.9342)
    st_lon = st_meta.get("lon", 77.6101)

    ocpp_sessions = db_store.get("ocpp_sessions", {}).get(station_id, [])
    vehicles_telemetry = db_store.get("vehicles_telemetry", {})

    if not vehicles_telemetry:
        # Dynamic telemetry pool for active fleet monitoring
        vehicles_telemetry = {
            "EV-CV-001": {
                "vehicle_id": "EV-CV-001",
                "lat": st_lat + 0.0006,  # ~66 meters away
                "lon": st_lon + 0.0004,
                "speed_kmh": 2.1,
                "status": "WAITING",
            },
            "EV-CV-002": {
                "vehicle_id": "EV-CV-002",
                "lat": st_lat + 0.0008,  # ~110 meters away
                "lon": st_lon + 0.0005,
                "speed_kmh": 3.4,
                "status": "WAITING",
            },
            "EV-CV-003": {
                "vehicle_id": "EV-CV-003",
                "lat": st_lat + 0.0003,  # ~35 meters away
                "lon": st_lon + 0.0002,
                "speed_kmh": 0.0,
                "status": "CHARGING",    # Filtered out (charging)
            },
            "EV-CV-004": {
                "vehicle_id": "EV-CV-004",
                "lat": st_lat + 0.0050,  # ~550 meters away (outside 150m geofence)
                "lon": st_lon + 0.0040,
                "speed_kmh": 24.5,
                "status": "EN_ROUTE",
            },
        }

    queued_vehicles = []
    active_plugs = len(ocpp_sessions)

    for vid, vdata in vehicles_telemetry.items():
        v_lat = float(vdata.get("lat", vdata.get("gps_lat", 0.0)))
        v_lon = float(vdata.get("lon", vdata.get("gps_lon", 0.0)))
        v_speed = float(vdata.get("speed_kmh", vdata.get("speed", 0.0)))
        v_status = str(vdata.get("status", "NORMAL")).upper()

        dist_m = calculate_haversine_distance(st_lat, st_lon, v_lat, v_lon)

        is_in_geofence = (dist_m <= geofence_radius_meters)
        is_stationary  = (v_speed < 5.0)
        is_not_charging = (v_status != "CHARGING")
        not_in_ocpp    = (vid not in ocpp_sessions)

        if is_in_geofence and is_stationary and is_not_charging and not_in_ocpp:
            queued_vehicles.append({
                "vehicle_id": vid,
                "distance_m": round(dist_m, 1),
                "speed_kmh": round(v_speed, 1),
                "status": "QUEUED (Inside 150m Geofence)",
            })

    queued_count = len(queued_vehicles)
    avg_session_mins = 20.0

    facility_type = st_meta.get("facility_type", "PUBLIC_STATION")
    if facility_type == "PRIVATE_YARD":
        # Private Yards operate on scheduled slots; public line queues do not apply (queue_delay = 0 mins)
        return {
            "queued_count": 0,
            "active_plugs": active_plugs,
            "queue_delay_mins": 0.0,
            "queued_vehicles": queued_vehicles,
            "geofence_radius_meters": geofence_radius_meters,
            "facility_type": "PRIVATE_YARD",
            "queue_mode": "DISABLED (RESERVED SLOT ACCESS)",
        }

    queue_delay_mins = queued_count * avg_session_mins

    return {
        "queued_count": queued_count,
        "active_plugs": active_plugs,
        "queue_delay_mins": round(queue_delay_mins, 1),
        "queued_vehicles": queued_vehicles,
        "geofence_radius_meters": geofence_radius_meters,
        "facility_type": "PUBLIC_STATION",
        "queue_mode": "ACTIVE (150m GPS GEOFENCE)",
    }





# ══════════════════════════════════════════════════════════════════════
# SESSION STATE INITIALIZATION
# ══════════════════════════════════════════════════════════════════════
if "logged_in"         not in st.session_state: st.session_state.logged_in         = False
if "username"          not in st.session_state: st.session_state.username          = None
if "role"              not in st.session_state: st.session_state.role              = None

if "distance_driven"   not in st.session_state: st.session_state.distance_driven   = 0.0
if "is_driving"        not in st.session_state: st.session_state.is_driving        = False
if "battery_soc"       not in st.session_state: st.session_state.battery_soc       = _DEFAULT_BATT

# ── GPS Location Persistence: load from URL query params first ──
if "gps_lat" not in st.session_state or "gps_lon" not in st.session_state:
    _qp = st.query_params
    def _parse_qp_float(v):
        try:
            f = float(v)
            return None if (f != f or abs(f) == float("inf")) else f
        except (TypeError, ValueError):
            return None
    _qp_lat = _parse_qp_float(_qp.get("lat"))
    _qp_lon = _parse_qp_float(_qp.get("lng"))
    if _qp_lat is not None and _qp_lon is not None:
        st.session_state["gps_lat"]   = _qp_lat
        st.session_state["gps_lon"]   = _qp_lon
        st.session_state["gps_label"] = _qp.get("location_name", "Detected Location")
    else:
        # No stored GPS yet — will be filled once geolocation widget fires
        st.session_state["gps_lat"]   = None
        st.session_state["gps_lon"]   = None
        st.session_state["gps_label"] = None


if "alert_active"      not in st.session_state: st.session_state.alert_active      = False
if "alert_status"      not in st.session_state: st.session_state.alert_status      = "NORMAL"
if "auction_triggered" not in st.session_state: st.session_state.auction_triggered = False

if "auction_fired"     not in st.session_state: st.session_state.auction_fired     = False
if "auction_payload"   not in st.session_state: st.session_state.auction_payload   = None
if "auction_results"   not in st.session_state: st.session_state.auction_results   = None
if "winning_station"   not in st.session_state: st.session_state.winning_station   = None
if "fleet_payload"     not in st.session_state: st.session_state.fleet_payload     = None
if "sla_payload"       not in st.session_state: st.session_state.sla_payload       = None
if "yard_host_payload"        not in st.session_state: st.session_state.yard_host_payload        = None
if "broker_payload"          not in st.session_state: st.session_state.broker_payload          = None
if "dynamic_pricing_payload" not in st.session_state: st.session_state.dynamic_pricing_payload = None
if "gate_pass"               not in st.session_state: st.session_state.gate_pass               = None
if "pipeline_results"        not in st.session_state: st.session_state.pipeline_results        = {}
if "invoice_ledger"          not in st.session_state: st.session_state.invoice_ledger          = None
if "wallet_balance"          not in st.session_state: st.session_state.wallet_balance          = 15000.00

# ── Persistent Local Database Initialization (stations_db.json) ──────
if "stations" not in st.session_state:
    st.session_state["stations"] = load_stations_db().get("stations", {})

# ── initialise station parameters from shared file → session state ──────
_db_data = load_stations_db()
_persisted = _db_data.get("stations", {})
st.session_state["stations"] = _persisted

for sid, sdef in STATIONS_DEFAULTS.items():
    _p = _persisted.get(sid, {})
    # Always prioritize persisted values from stations_db.json
    st.session_state[f"{sid}_status"] = _p.get("status", sdef["status"])
    st.session_state[f"{sid}_price_per_kwh"] = float(_p.get("price_per_kwh", sdef["price_per_kwh"]))
    st.session_state[f"{sid}_queue_length"] = int(_p.get("queue_length", sdef["queue_length"]))
    st.session_state[f"{sid}_kw"] = float(_p.get("kw", sdef["kw"]))
    if "safety_buffer_percentage" in _p:
        st.session_state[f"{sid}_safety_buffer"] = float(_p["safety_buffer_percentage"])


def _get_live_stations() -> dict[str, dict[str, Any]]:
    """Build a fresh stations dict directly from the shared persistent JSON file.

    Always reads from disk on every invocation so that any tariff, queue, power,
    or status changes made by a station admin instantly reflect in driver auctions."""
    shared = _load_shared_station_state()
    live = {}
    for sid, sdef in STATIONS_DEFAULTS.items():
        s = dict(sdef)
        p = shared.get(sid, {})
        s["status"]        = p.get("status", sdef["status"])
        s["price_per_kwh"] = float(p.get("price_per_kwh", sdef["price_per_kwh"]))
        s["queue_length"]  = int(p.get("queue_length", sdef["queue_length"]))
        kw_val             = float(p.get("kw", sdef["kw"]))
        s["kw"]            = kw_val
        s["charger"]       = f"{int(kw_val)} kW Charger"
        live[sid]          = s
    return live


# ══════════════════════════════════════════════════════════════════════
# BUTTON CALLBACKS
# ══════════════════════════════════════════════════════════════════════

def _step_energy():
    st.session_state.distance_driven = round(st.session_state.distance_driven + _STEP_KM, 2)
    st.session_state.battery_soc     = round(max(1.0, st.session_state.battery_soc - _STEP_DRAIN), 2)

def _reset_energy():
    st.session_state.battery_soc       = _DEFAULT_BATT
    st.session_state.distance_driven   = 0.0
    st.session_state.alert_active      = False
    st.session_state.alert_status      = "NORMAL"
    st.session_state.auction_triggered = False
    st.session_state.auction_fired     = False
    st.session_state.auction_payload   = None
    st.session_state.auction_results   = None
    st.session_state.winning_station   = None
    st.session_state.fleet_payload            = None
    st.session_state.sla_payload              = None
    st.session_state.broker_payload           = None
    st.session_state.dynamic_pricing_payload  = None
    st.session_state.gate_pass               = None
    st.session_state.top3_stations            = None
    # Purge active vehicle request in stations_db.json
    db = _load_stations_db()
    if "EV-CV-001" in db.get("active_requests", {}):
        _save_stations_db({"active_requests": {"EV-CV-001": None}})


def _drain_to_alert():
    st.session_state.battery_soc     = 45.0
    st.session_state.distance_driven = 35.0



def _do_logout():
    # Preserve detected GPS location across logout
    _saved_lat   = st.session_state.get("gps_lat")
    _saved_lon   = st.session_state.get("gps_lon")
    _saved_label = st.session_state.get("gps_label")
    st.session_state.logged_in = False
    st.session_state.username  = None
    st.session_state.role      = None
    # Restore location so it survives the rerun
    st.session_state["gps_lat"]   = _saved_lat
    st.session_state["gps_lon"]   = _saved_lon
    st.session_state["gps_label"] = _saved_label


# ══════════════════════════════════════════════════════════════════════
# MULTI-AGENT PIPELINE (4 AGENTS)
# ══════════════════════════════════════════════════════════════════════

def _compute_distance_km(
    lat1: float, lon1: float, lat2: float, lon2: float,
) -> float:
    return geodesic((lat1, lon1), (lat2, lon2)).kilometers


class FleetEVAgent:
    @staticmethod
    def track_telemetry(
        battery_current: float,
        battery_required: float,
        dist_km: float,
        lat: float,
        lon: float,
        destination: str,
        cargo_type: str,
    ) -> dict[str, Any]:
        return {
            "vehicle_id": "EV-CV-001",
            "gps_lat": round(lat, 5),
            "gps_lon": round(lon, 5),
            "destination": destination,
            "route_distance_km": round(dist_km, 2),
            "battery_current": round(battery_current, 2),
            "battery_required": round(battery_required, 2),
            "cargo_type": cargo_type,
            "timestamp": round(time.time(), 2),
        }

    @staticmethod
    def detect_energy_deficit(
        battery_current: float,
        battery_required: float,
    ) -> tuple[bool, float]:
        deficit = round(max(0.0, battery_required - battery_current), 2)
        return deficit > 0.0, deficit

    @staticmethod
    def construct_auction_trigger(
        battery_current: float,
        battery_required: float,
        deficit: float,
        sla_urgency: float,
        lat: float,
        lon: float,
        destination: str,
        dist_km: float,
        cargo_type: str,
        top3_stations: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "action": "AuctionTrigger",
            "agent": "Fleet_EV Agent",
            "vehicle_id": "EV-CV-001",
            "gps_lat": round(lat, 5),
            "gps_lon": round(lon, 5),
            "destination": destination,
            "route_distance_km": round(dist_km, 2),
            "battery_current": round(battery_current, 2),
            "battery_required": round(battery_required, 2),
            "energy_deficit": round(deficit, 2),
            "sla_urgency": round(sla_urgency, 4),
            "cargo_type": cargo_type,
            "top3_stations": top3_stations or [],
            "timestamp": round(time.time(), 2),
        }


class SLAGuardianAgent:
    @staticmethod
    def evaluate_cargo_risk(
        cargo_type: str,
        battery_soc: float,
        dist_km: float = 0.0,
        remaining_window_minutes: float = 120.0,
        total_window_minutes: float = 120.0,
    ) -> float:
        cargo_info = _CARGO.get(cargo_type, ("📦", 0.40, "Standard", False))
        w_cargo = cargo_info[1]

        # 1) SLA Deadline Proximity (0.0 to 1.0)
        elapsed_ratio = max(0.0, 1.0 - (remaining_window_minutes / max(total_window_minutes, 1.0)))
        deadline_proximity = min(1.0, elapsed_ratio)

        # 2) Battery Deficiency % (0.0 to 1.0)
        battery_deficiency = max(0.0, min(1.0, (100.0 - battery_soc) / 100.0))

        # Composite Formula:
        # Urgency Score = (Battery Deficiency %) * 0.4 + (SLA Deadline Proximity) * 0.3 + W_cargo * 0.3
        urgency = (battery_deficiency * 0.4) + (deadline_proximity * 0.3) + (w_cargo * 0.3)
        return round(max(0.0, min(1.0, urgency)), 4)

    @staticmethod
    def get_urgency_band(urgency: float) -> str:
        if urgency > 0.70:
            return "CRITICAL"
        elif urgency > 0.40:
            return "MODERATE"
        return "LOW"

    @staticmethod
    def inject_urgency_payload(
        urgency: float,
        cargo_type: str,
    ) -> dict[str, Any]:
        return {
            "evaluated_by": "SLA_Guardian Agent",
            "sla_urgency": urgency,
            "urgency_band": SLAGuardianAgent.get_urgency_band(urgency),
            "cargo_type": cargo_type,
            "timestamp": round(time.time(), 2),
        }


class DealOptimizerAgent:
    _GATE_PASSCODE = "#808-GATE-PASS"

    @staticmethod
    def _compute_dynamic_weights(sla_urgency: float) -> dict[str, float]:
        if sla_urgency > 0.70:
            return {
                "distance": 0.20,
                "price": 0.10,
                "queue": 0.40,
                "charger_speed": 0.15,
                "sla_urgency": 0.15,
            }
        elif sla_urgency > 0.40:
            return {
                "distance": 0.25,
                "price": 0.25,
                "queue": 0.25,
                "charger_speed": 0.15,
                "sla_urgency": 0.10,
            }
        else:
            return {
                "distance": 0.20,
                "price": 0.40,
                "queue": 0.15,
                "charger_speed": 0.15,
                "sla_urgency": 0.10,
            }

    @staticmethod
    def _norm_min(vals: list[float], v: float) -> float:
        lo, hi = min(vals), max(vals)
        return 1.0 if hi == lo else 1.0 - (v - lo) / (hi - lo)

    @staticmethod
    def _norm_max(vals: list[float], v: float) -> float:
        lo, hi = min(vals), max(vals)
        return 0.5 if hi == lo else (v - lo) / (hi - lo)

    def receive_bids(
        self,
        vehicle_lat: float,
        vehicle_lon: float,
        sla_urgency: float,
        battery_current: float,
        battery_required: float,
        stations: dict[str, dict[str, Any]],
        cargo_type: str = "",
    ) -> list[dict[str, Any]]:
        bids: list[dict[str, Any]] = []
        distances: list[float] = []
        prices: list[float] = []
        queues: list[int] = []
        chargers: list[float] = []

        station_list = []

        cargo_info = _CARGO.get(cargo_type, ("📦", 0.40, "Standard", False))
        w_cargo = cargo_info[1]
        is_critical_sla = (w_cargo >= 0.90)

        for sid, s in stations.items():
            if s["status"] == "Offline":
                continue

            f_type = s.get("facility_type", STATIONS_DEFAULTS.get(sid, {}).get("facility_type", "PUBLIC_STATION"))

            # Private Yard Restricted Access Check: Reserved for contracted / SLA cargo vehicles (w_cargo >= 0.40)
            if f_type == "PRIVATE_YARD" and w_cargo < 0.40:
                _log.info("Filtering out Private Yard %s for uncontracted low-SLA cargo (%s)", sid, cargo_type)
                continue

            kw_rating = float(s.get("kw", 0.0))
            # Critical SLA cargo requirement: Restrict choices to high-speed DC fast-charging yards (>= 50 kW)
            if is_critical_sla and kw_rating < 50.0:
                _log.info("Filtering out station %s (< 50 kW) for Critical SLA cargo: %s", sid, cargo_type)
                continue

            # GPS Geofenced Queue Status & SLA Margin check
            q_info = get_station_queue_status(sid, geofence_radius_meters=150.0)

            # Skip queue wait calculations for Private Yards (queue_delay = 0 mins for reserved slot access)
            if f_type == "PRIVATE_YARD":
                q_info["queue_delay_mins"] = 0.0
                q_info["queued_count"] = 0

            queue_delay_mins = q_info["queue_delay_mins"]
            est_charge_mins = 20.0
            total_delay_mins = queue_delay_mins + est_charge_mins

            # Cargo SLA Margin evaluation (Critical SLA cargo max delay margin = 35 mins; Standard cargo = 75 mins)
            sla_margin_mins = 35.0 if is_critical_sla else 75.0
            if total_delay_mins > sla_margin_mins:
                _log.info("Filtering out station %s due to SLA Queue Margin breach (delay %.1f mins > margin %.1f mins)", sid, total_delay_mins, sla_margin_mins)
                continue

            dist = _compute_distance_km(vehicle_lat, vehicle_lon, s["lat"], s["lon"])
            distances.append(dist)
            prices.append(s["price_per_kwh"])
            queues.append(q_info["queued_count"])
            chargers.append(float(s["charger"].split()[0]))
            station_list.append((sid, s, dist, q_info))

        if not station_list:
            return []

        W = self._compute_dynamic_weights(sla_urgency)

        for sid, s, dist, q_info in station_list:
            dist_score    = self._norm_min(distances, dist)
            price_score   = self._norm_min(prices, s["price_per_kwh"])
            queue_score   = self._norm_min(queues, q_info["queued_count"])
            charger_score = self._norm_max(chargers, float(s["charger"].split()[0]))

            sla_bonus = sla_urgency * 0.5 * dist_score

            rating_val = float(s.get("rating", STATIONS_DEFAULTS.get(sid, {}).get("rating", 4.2)))
            uptime_val = float(s.get("uptime_pct", STATIONS_DEFAULTS.get(sid, {}).get("uptime_pct", 98.0)))
            
            # Rating multiplier factor (>=4.5 -> 1.05 boost, <3.5 -> 0.90 penalty)
            rep_boost = 1.05 if rating_val >= 4.5 else (0.90 if rating_val < 3.5 else 1.00)
            if uptime_val < 90.0:
                rep_boost -= 0.05

            score = (
                W["distance"] * dist_score
                + W["price"] * price_score
                + W["queue"] * queue_score
                + W["charger_speed"] * charger_score
                + W["sla_urgency"] * (dist_score * sla_urgency)
                + sla_bonus
            ) * rep_boost

            # Geofence Queue Delay penalty
            if q_info["queue_delay_mins"] > 0:
                score *= max(0.2, 1.0 - (q_info["queue_delay_mins"] / 100.0))

            if s["status"] == "Busy":
                score *= 0.6

            eta = round(dist / 0.8)
            f_type = s.get("facility_type", STATIONS_DEFAULTS.get(sid, {}).get("facility_type", "PUBLIC_STATION"))
            bids.append({
                "station_id": sid,
                "name": s["name"],
                "short": s["short"],
                "facility_type": f_type,
                "distance_km": round(dist, 2),
                "eta_min": max(1, eta),
                "price_per_kwh": s["price_per_kwh"],
                "charger": s["charger"],
                "rating": rating_val,
                "uptime_pct": uptime_val,
                "reputation_multiplier": round(rep_boost, 2),
                "queue_length": q_info["queued_count"],
                "queue_delay_mins": q_info["queue_delay_mins"],
                "status": s["status"],
                "passcode": s.get("passcode", self._GATE_PASSCODE),
                "score": round(score, 4),
                "dist_score": round(dist_score, 4),
                "price_score": round(price_score, 4),
                "queue_score": round(queue_score, 4),
                "charger_score": round(charger_score, 4),
            })

        bids.sort(key=lambda b: b["score"], reverse=True)
        return bids



    def select_winning_station(
        self,
        bids: list[dict[str, Any]],
        sla_urgency: float,
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        if not bids:
            return None, []

        winner = dict(bids[0])
        winner["passcode"] = winner.get("passcode", self._GATE_PASSCODE)

        avg_price = sum(b["price_per_kwh"] for b in bids) / len(bids)
        avg_queue = sum(b["queue_length"] for b in bids) / len(bids)

        savings_usd = round((avg_price - winner["price_per_kwh"]) * 10.0, 2)
        saved_queue_time = max(0, int(avg_queue - winner["queue_length"]))

        trade_off_score = round(
            winner["score"]
            * (1.0 + (savings_usd / max(avg_price, 0.01)) * 0.05)
            * (1.0 + saved_queue_time * 0.02),
            4,
        )

        winner["trade_off_score"] = trade_off_score
        winner["savings_usd"] = savings_usd
        winner["saved_queue_time"] = saved_queue_time
        winner["weight_config"] = self._compute_dynamic_weights(sla_urgency)

        return winner, bids


def run_auction_pipeline(
    vehicle_lat: float,
    vehicle_lon: float,
    sla_urgency: float,
    battery_current: float,
    battery_required: float,
    stations: dict[str, dict[str, Any]],
    cargo_type: str = "",
    destination: str = "",
    dist_km: float = 0.0,
) -> tuple[
    dict[str, Any] | None,
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    Any,
    Any,
    list[str],
]:
    """Sequential 9-agent pipeline:
    WeatherImpact → FleetEV → SLA Guardian → Dynamic Pricing → Broker Auctioneer → Deal Optimizer → Yard Host → Security Pass → FinTech
    """
    # ── Agent 1 (Pre-Auction): Weather Impact Agent ──────────────────
    weather_agent = WeatherImpactAgent()
    base_kwh_deficit = max(0.0, battery_required - battery_current) * 0.8
    weather_payload = weather_agent.evaluate_weather_impact(
        base_kwh=base_kwh_deficit if base_kwh_deficit > 0 else 40.0,
        lat=vehicle_lat,
        lon=vehicle_lon
    )
    if hasattr(st, "session_state"):
        st.session_state["weather_payload"] = weather_payload

    fleet_ev = FleetEVAgent()
    deficit = max(0.0, battery_required - battery_current)

    # ── Agent 2: SLA Guardian ─────────────────────────────────────────
    sla_guardian = SLAGuardianAgent()
    sla_payload = sla_guardian.inject_urgency_payload(
        urgency=sla_urgency,
        cargo_type=cargo_type,
    )

    cargo_info = _CARGO.get(cargo_type, ("📦", 0.40, "Standard", False))
    w_cargo = cargo_info[1]

    # ── Agent 3: Dynamic Pricing — ToU & Congestion Tariff Engine ─────
    pricing_agent = DynamicPricingAgent(min_tariff_floor=8.0, max_tariff_cap=25.0)

    # Build raw station bids for the pricing agent (all non-offline stations)
    raw_pricing_bids: list[dict[str, Any]] = []
    for sid, s in stations.items():
        if s["status"] == "Offline":
            continue
        f_type   = s.get("facility_type", "PUBLIC_STATION")
        avail_kw = float(s.get("available_power_kw", s.get("kw", 0.0)))
        if f_type == "PUBLIC_STATION":
            avail_kw = float(s.get("kw", avail_kw))
        raw_pricing_bids.append({
            "station_id":      sid,
            "facility_name":   s["name"],
            "facility_type":   f_type,
            "tariff_per_kwh":  float(s.get("price_per_kwh", 0.25)),
            "queue_length":    int(s.get("queue_length", 0)),
            "total_chargers":  int(s.get("total_chargers", 5)),
            "available_power_kw": avail_kw,
        })

    dynamic_pricing_results = pricing_agent.compute_dynamic_tariffs(raw_pricing_bids)
    dynamic_pricing_payload = pricing_agent.build_payload(
        dynamic_pricing_results,
        tou_multiplier=pricing_agent.calculate_tou_multiplier()[0],
    )

    # Build a station_id → dynamic_tariff lookup for downstream agents
    dynamic_tariff_map: dict[str, float] = {
        r.station_id: r.dynamic_tariff for r in dynamic_pricing_results
    }

    # ── Agent 4: Broker Auctioneer — Double-Blind Market Clearing ─────
    broker = BrokerAuctioneerAgent(market_fee_percent=2.0)

    auction_request = AuctionRequestPayload(
        vehicle_id="EV-CV-001",
        current_soc=battery_current,
        urgency_score=sla_urgency,
        cargo_weight_factor=w_cargo,
        required_kwh=round(max(0.0, battery_required - battery_current) * 0.8, 2),
    )

    # Build station offers using dynamic tariffs from the Pricing Agent
    station_offers: list[dict[str, Any]] = []
    for sid, s in stations.items():
        if s["status"] == "Offline":
            continue
        f_type   = s.get("facility_type", "PUBLIC_STATION")
        avail_kw = float(s.get("available_power_kw", s.get("kw", 0.0)))
        if f_type == "PUBLIC_STATION":
            avail_kw = float(s.get("kw", avail_kw))
        # Use dynamic tariff if available, fall back to base tariff
        dynamic_tariff = dynamic_tariff_map.get(sid, float(s.get("price_per_kwh", 0.25)))
        station_offers.append({
            "station_id":               sid,
            "facility_name":            s["name"],
            "facility_type":            f_type,
            "available_power_kw":       avail_kw,
            "tariff_per_kwh":           dynamic_tariff,   # ← dynamic price injected
            "queue_delay_mins":         float(s.get("eta_minutes", 0.0)),
            "min_cargo_weight_required": 0.40 if f_type == "PRIVATE_YARD" else 0.0,
        })

    cleared_bids = broker.clear_auction(auction_request, station_offers)
    broker_payload = broker.build_payload(auction_request, cleared_bids)

    # Extract set of eligible station IDs so Deal Optimizer only scores survivors
    eligible_station_ids = {b.station_id for b in cleared_bids if b.eligible}

    # Build eligible_stations with dynamic tariffs applied to price_per_kwh
    eligible_stations: dict[str, dict[str, Any]] = {}
    for sid, s in stations.items():
        if sid not in eligible_station_ids:
            continue
        s_copy = dict(s)
        if sid in dynamic_tariff_map:
            s_copy["price_per_kwh"] = dynamic_tariff_map[sid]
        eligible_stations[sid] = s_copy

    # ── Station Reputation & Trust Verification Agent ─────────────────
    reputation_agent = StationReputationAgent()
    reputation_payloads: dict[str, Any] = {}
    target_eval_stations = eligible_stations if eligible_stations else stations

    for sid, sdata in target_eval_stations.items():
        s_eval = dict(sdata)
        s_eval["station_id"] = sid
        s_eval["facility_name"] = sdata.get("name", sid)
        s_eval["rating"] = sdata.get("rating", STATIONS_DEFAULTS.get(sid, {}).get("rating", 4.2))
        s_eval["uptime_pct"] = sdata.get("uptime_pct", STATIONS_DEFAULTS.get(sid, {}).get("uptime_pct", 98.0))
        rep_pl = reputation_agent.evaluate_station_reputation(s_eval)
        reputation_payloads[sid] = rep_pl

    if hasattr(st, "session_state"):
        st.session_state["reputation_scores"] = reputation_payloads

    # ── Agent 5: Deal Optimizer ───────────────────────────────────────
    deal_optimizer = DealOptimizerAgent()
    all_bids = deal_optimizer.receive_bids(
        vehicle_lat=vehicle_lat,
        vehicle_lon=vehicle_lon,
        sla_urgency=sla_urgency,
        battery_current=battery_current,
        battery_required=battery_required,
        stations=eligible_stations if eligible_stations else stations,
        cargo_type=cargo_type,
    )

    # Dynamically adjust candidate bid MCDA scores with Reputation Multiplier
    for bid in all_bids:
        b_sid = bid.get("station_id")
        if b_sid in reputation_payloads:
            rep_info = reputation_payloads[b_sid]
            bid["user_rating"] = rep_info.user_rating
            bid["uptime_pct"] = rep_info.uptime_pct
            bid["reputation_multiplier"] = rep_info.reputation_multiplier
            bid["reputation_badge"] = rep_info.badge_label
            bid["reputation_explanation"] = rep_info.explanation
            bid["score"] = round(bid["score"] * rep_info.reputation_multiplier, 4)

    # Re-sort candidate bids based on reputation-adjusted MCDA scores
    all_bids.sort(key=lambda b: b["score"], reverse=True)

    winner, all_bids = deal_optimizer.select_winning_station(all_bids, sla_urgency)

    top3_stations = [b["station_id"] for b in all_bids[:3]]

    # ── Agent 1 payload assembly (uses top3 from Deal Optimizer) ──────
    fleet_payload = fleet_ev.construct_auction_trigger(
        battery_current=battery_current,
        battery_required=battery_required,
        deficit=deficit,
        sla_urgency=sla_urgency,
        lat=vehicle_lat,
        lon=vehicle_lon,
        destination=destination,
        dist_km=dist_km,
        cargo_type=cargo_type,
        top3_stations=top3_stations,
    )

    db = _load_stations_db()
    existing_req = db.get("active_requests", {}).get("EV-CV-001", {})
    existing_status = existing_req.get("status")

    if existing_status in ["ACCEPTED", "ACCEPTED_WINNER", "GATE_PASS_ISSUED", "APPROVED_GATE_PASS", "CHARGING_IN_PROGRESS"]:
        req_status = existing_status
        accepted_by = existing_req.get("accepted_by")
        acc_bid = next((b for b in all_bids if b["station_id"] == accepted_by), None)
        if acc_bid:
            winner = acc_bid
    else:
        req_status = "PENDING"
        accepted_by = None

    _save_stations_db({
        "active_requests": {
            "EV-CV-001": {
                "vehicle_id": "EV-CV-001",
                "status": req_status,
                "accepted_by": accepted_by,
                "top3_stations": top3_stations,
                "battery_soc": round(battery_current, 2),
                "energy_deficit": round(deficit, 2),
                "sla_urgency": round(sla_urgency, 4),
                "cargo_type": cargo_type,
                "gps_lat": round(vehicle_lat, 5),
                "gps_lon": round(vehicle_lon, 5),
                "timestamp": round(time.time(), 2),
            }
        }
    })

    # ── Multi-Station Request Broadcast & First-Accept Win Workflow ──
    db = _load_stations_db()
    existing_req = db.get("active_requests", {}).get("EV-CV-001", {})
    existing_status = existing_req.get("status")
    accepted_by = existing_req.get("accepted_by")

    gate_pass_payload = None
    invoice_payload = None

    if existing_status in ["ACCEPTED", "APPROVED_GATE_PASS", "CHARGING_IN_PROGRESS", "CHARGING_COMPLETED"] and accepted_by:
        acc_bid = next((b for b in all_bids if b["station_id"] == accepted_by), None)
        if acc_bid:
            winner = acc_bid

        # Issue Gate Pass & Invoice for the accepted winner
        sec_agent = SecurityPassAgent()
        is_haz = (cargo_type == "Hazardous Chemicals / Flammables")
        try:
            gate_pass_payload = sec_agent.issue_gate_pass(
                winning_deal=winner if winner else {"station_id": accepted_by, "facility_name": "Accepted Station"},
                cargo_type=cargo_type if cargo_type else "General Retail Freight",
                is_hazard=is_haz
            )
        except Exception as e:
            _log.error("SecurityPassAgent execution failed: %s", e)

        if gate_pass_payload:
            fintech_agent = FinTechSettlementAgent(initial_wallet_balance=st.session_state.get("wallet_balance", 15000.00))
            gp_dict = gate_pass_payload.dict() if hasattr(gate_pass_payload, 'dict') else {"pass_id": getattr(gate_pass_payload, 'pass_id', '#808-GATE-PASS'), "vehicle_id": "EV-CV-001"}
            invoice_payload = fintech_agent.execute_settlement(
                gate_pass_data=gp_dict,
                winning_deal=winner if winner else {"facility_name": "Accepted Station", "required_kwh": 45.0, "effective_tariff": 12.0},
                current_wallet_balance=st.session_state.get("wallet_balance", 15000.00)
            )

            # Preserve booking details in stations_db.json
            _save_stations_db({
                "active_requests": {
                    "EV-CV-001": {
                        "status": existing_status,
                        "accepted_by": accepted_by,
                        "gate_pass_id": gate_pass_payload.pass_id,
                        "assigned_bay": gate_pass_payload.assigned_bay,
                        "security_hash": gate_pass_payload.security_hash,
                        "valid_until": gate_pass_payload.valid_until,
                        "cargo_type": cargo_type,
                        "timestamp": round(time.time(), 2)
                    }
                }
            })
    else:
        # Broadcast alert to Top 3 candidate stations
        st_db = load_stations_db()
        st_map = st_db.get("stations", {})

        for sid in top3_stations:
            if sid in st_map:
                st_map[sid]["status"] = "AUCTION_ALERT_PENDING"
                st_map[sid]["pending_request"] = {
                    "vehicle_id": "EV-CV-001",
                    "required_kwh": round(max(0.0, battery_required - battery_current) * 0.8, 2),
                    "urgency": SLAGuardianAgent.get_urgency_band(sla_urgency),
                    "cargo_type": cargo_type,
                    "proposed_tariff": dynamic_tariff_map.get(sid, 12.0)
                }

        save_stations_db({
            "stations": st_map,
            "active_requests": {
                "EV-CV-001": {
                    "vehicle_id": "EV-CV-001",
                    "status": "AUCTION_ALERT_PENDING",
                    "accepted_by": None,
                    "top3_stations": top3_stations,
                    "battery_soc": round(battery_current, 2),
                    "energy_deficit": round(deficit, 2),
                    "sla_urgency": round(sla_urgency, 4),
                    "cargo_type": cargo_type,
                    "gps_lat": round(vehicle_lat, 5),
                    "gps_lon": round(vehicle_lon, 5),
                    "timestamp": round(time.time(), 2)
                }
            }
        })

    return winner, all_bids, fleet_payload, sla_payload, dynamic_pricing_payload, broker_payload, gate_pass_payload, invoice_payload, top3_stations



# ══════════════════════════════════════════════════════════════════════
# CYBERPUNK NEON GREEN THEME & ANIMATION ENGINE (CSS)
# ══════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
    --bg-primary: #06100C;
    --bg-secondary: #0C1A12;
    --bg-card: rgba(14, 28, 20, 0.80);
    --glass-bg: rgba(16, 34, 24, 0.70);
    --glass-border: rgba(0, 214, 143, 0.18);
    --accent-primary: #00D68F;
    --accent-secondary: #00B87A;
    --accent-bright: #1AFFA8;
    --accent-teal: #00C9A7;
    --accent-blue: #3B82F6;
    --warn-amber: #F59E0B;
    --warn-orange: #FB923C;
    --crit-red: #EF4444;
    --success-green: #10B981;
    --text-primary: #F0FDF6;
    --text-secondary: #D1FAE5;
    --text-muted: #6EE7B7;
    --text-dim: #4B7B65;
    --font-heading: 'Plus Jakarta Sans', 'Inter', sans-serif;
    --font-body: 'Inter', sans-serif;
    --font-mono: 'JetBrains Mono', 'Courier New', monospace;
    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 18px;
    --radius-xl: 24px;
    --shadow-card: 0 4px 24px rgba(0, 0, 0, 0.40), 0 1px 4px rgba(0, 214, 143, 0.06);
    --shadow-glow: 0 0 24px rgba(0, 214, 143, 0.18);
    --transition: all 0.22s cubic-bezier(0.4, 0, 0.2, 1);
}

/* ── Lock sidebar permanently open — hide collapse toggle ── */
[data-testid="collapsedControl"],
button[kind="header"][aria-label="Close sidebar"],
button[aria-label="Close sidebar"],
[data-testid="stSidebarCollapseButton"] {
    display: none !important;
}
section[data-testid="stSidebar"] {
    transform: none !important;
    min-width: 280px !important;
    visibility: visible !important;
}

*, *::before, *::after {
    box-sizing: border-box;
    font-family: var(--font-body);
}

/* ── Professional Dark Background ── */
.stApp {
    background-color: var(--bg-primary);
    background-image:
        radial-gradient(ellipse at 60% -10%, rgba(0, 214, 143, 0.10) 0%, transparent 55%),
        radial-gradient(ellipse at 90% 80%, rgba(0, 201, 167, 0.06) 0%, transparent 50%),
        radial-gradient(ellipse at 5% 95%, rgba(0, 184, 122, 0.07) 0%, transparent 45%);
    background-attachment: fixed;
    color: var(--text-primary);
}

/* ── Hide Streamlit Chrome & Polish Header ── */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.5rem !important; padding-bottom: 3.5rem !important; }

/* ── Professional Sidebar ── */
section[data-testid="stSidebar"] {
    background: rgba(6, 14, 10, 0.97) !important;
    border-right: 1px solid rgba(0, 214, 143, 0.12) !important;
    backdrop-filter: blur(24px);
}

.sb-cyber-badge {
    background: rgba(0, 214, 143, 0.06);
    border: 1px solid rgba(0, 214, 143, 0.18);
    border-radius: var(--radius-md);
    padding: 14px 16px;
    margin-bottom: 16px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.30);
    transition: var(--transition);
}
.sb-cyber-badge:hover {
    border-color: rgba(0, 214, 143, 0.35);
    box-shadow: 0 4px 20px rgba(0, 214, 143, 0.10);
}

.sb-label {
    font-family: var(--font-body);
    font-size: 0.70rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: var(--text-muted);
    margin: 0 0 6px;
}

/* ── Professional Page Headers ── */
.cv-header {
    text-align: center;
    padding: 8px 0 28px;
}
.cv-header h1 {
    font-family: var(--font-heading);
    font-size: 2.0rem;
    font-weight: 800;
    background: linear-gradient(135deg, #00D68F 0%, #00C9A7 50%, #1AFFA8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0 0 8px;
    letter-spacing: -0.5px;
}
.cv-header p {
    font-family: var(--font-body);
    font-size: 0.82rem;
    font-weight: 400;
    color: var(--text-dim);
    letter-spacing: 0.5px;
    margin: 0;
}

/* ── Professional Glass Cards ── */
.cyber-card {
    background: var(--glass-bg);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-lg);
    padding: 20px 18px;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    box-shadow: var(--shadow-card);
    transition: var(--transition);
    position: relative;
    overflow: hidden;
}
.cyber-card::before {
    content: '';
    position: absolute;
    top: 0; left: 16px; right: 16px;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0, 214, 143, 0.50), transparent);
}
.cyber-card:hover {
    transform: translateY(-3px);
    border-color: rgba(0, 214, 143, 0.35);
    box-shadow: var(--shadow-card), var(--shadow-glow);
}

.card-icon {
    font-size: 1.6rem;
    line-height: 1;
}
.card-label {
    font-family: var(--font-body);
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: var(--text-dim);
    margin: 0;
}
.card-value {
    font-family: var(--font-heading);
    font-size: 1.9rem;
    font-weight: 800;
    margin: 4px 0 0;
    line-height: 1.1;
    letter-spacing: -0.5px;
}

/* ── Professional Color States ── */
.glow-neon   { color: var(--accent-primary); }
.glow-mint   { color: var(--accent-teal); }
.glow-lime   { color: var(--accent-bright); }
.glow-warn   { color: var(--warn-amber); }
.glow-crit   { color: var(--crit-red); }

/* ── Professional Status Badges ── */
.cyber-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 4px 10px;
    border-radius: 20px;
    font-family: var(--font-body);
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    width: fit-content;
    transition: var(--transition);
}
.badge-optimal {
    background: rgba(16, 185, 129, 0.12);
    color: var(--success-green);
    border: 1px solid rgba(16, 185, 129, 0.28);
}
.badge-critical {
    background: rgba(239, 68, 68, 0.12);
    color: var(--crit-red);
    border: 1px solid rgba(239, 68, 68, 0.30);
    animation: crit-pulse 2s ease-in-out infinite;
}
@keyframes crit-pulse {
    0%, 100% { opacity: 1; border-color: rgba(239, 68, 68, 0.30); }
    50%       { opacity: 0.70; border-color: rgba(239, 68, 68, 0.60); }
}

/* ── Battery Gauge Track ── */
.cyber-batt-track {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(0, 214, 143, 0.10);
    border-radius: 8px;
    height: 8px;
    width: 100%;
    overflow: hidden;
    margin-top: 8px;
    position: relative;
}
.cyber-batt-fill {
    height: 100%;
    border-radius: 8px;
    transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
}

/* ── 3-Agent Flow Diagram ── */
.agent-pipeline-box {
    background: rgba(14, 26, 18, 0.80);
    border: 1px solid rgba(0, 214, 143, 0.15);
    border-radius: var(--radius-lg);
    padding: 20px;
    margin: 16px 0;
    box-shadow: var(--shadow-card);
}
.agent-step-card {
    background: rgba(8, 18, 12, 0.90);
    border: 1px solid rgba(0, 214, 143, 0.12);
    border-radius: var(--radius-md);
    padding: 16px;
    height: 100%;
    position: relative;
    transition: var(--transition);
}
.agent-step-card:hover {
    border-color: rgba(0, 214, 143, 0.30);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.30);
}

/* ── Enterprise Auction Grid ── */
.cyber-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0 8px;
    margin: 12px 0 20px;
}
.cyber-table th {
    font-family: var(--font-tech);
    font-size: 0.70rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: var(--accent-neon);
    padding: 12px 16px;
    text-align: left;
    background: rgba(0,255,136,0.06);
    border-bottom: 2px solid rgba(0,255,136,0.25);
}
.cyber-table td {
    font-size: 0.86rem;
    color: var(--text-primary);
    padding: 13px 16px;
    background: rgba(13,31,20,0.80);
    border-top: 1px solid rgba(0,255,136,0.07);
    border-bottom: 1px solid rgba(0,255,136,0.07);
    transition: background 0.22s ease, box-shadow 0.22s ease;
    vertical-align: middle;
}
.cyber-table tbody tr:hover td {
    background: rgba(0,255,136,0.10);
    box-shadow: inset 0 0 12px rgba(0,255,136,0.06);
}
.cyber-table tr.winner td {
    background: rgba(0,255,136,0.13);
    border-top-color: rgba(0,255,136,0.38);
    border-bottom-color: rgba(0,255,136,0.38);
    box-shadow: inset 0 0 20px rgba(0,255,136,0.08);
}
.cyber-table td:first-child {
    border-radius: 12px 0 0 12px;
    border-left: 2px solid rgba(0,255,136,0.18);
}
.cyber-table td:last-child {
    border-radius: 0 12px 12px 0;
    border-right: 2px solid rgba(0,255,136,0.18);
}
.cyber-table tr.winner td:first-child { border-left-color: var(--accent-neon); }
.cyber-table tr.winner td:last-child  { border-right-color: var(--accent-neon); }

/* ── Bids Section Wrapper ── */
.bids-section-wrap {
    background: rgba(13,31,20,0.55);
    border: 1px solid rgba(0,255,136,0.18);
    border-radius: 22px;
    padding: 24px 28px;
    margin: 18px 0;
    backdrop-filter: blur(12px);
    box-shadow: 0 4px 40px rgba(0,0,0,0.35), inset 0 1px 0 rgba(0,255,136,0.10);
}
.bids-section-title {
    font-family: var(--font-heading);
    font-size: 0.85rem;
    font-weight: 800;
    color: var(--accent-neon);
    text-transform: uppercase;
    letter-spacing: 2.5px;
    margin: 0 0 18px;
    display: flex;
    align-items: center;
    gap: 10px;
}
.bids-section-title::after {
    content: '';
    flex: 1;
    height: 1px;
    background: linear-gradient(90deg, rgba(0,255,136,0.35), transparent);
}
/* ── Score bar inside table ── */
.score-bar-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
}
.score-bar-bg {
    flex: 1;
    height: 6px;
    background: rgba(0,255,136,0.12);
    border-radius: 99px;
    overflow: hidden;
}
.score-bar-fill {
    height: 100%;
    border-radius: 99px;
    background: linear-gradient(90deg, #00FF88, #76FF03);
    box-shadow: 0 0 8px rgba(0,255,136,0.6);
}
.score-bar-fill.loser {
    background: linear-gradient(90deg, #39FFB6, #00C853);
    box-shadow: none;
}
.score-val { font-family: var(--font-heading); font-size: 0.78rem; font-weight: 800; white-space: nowrap; }


/* ── Winner Centerpiece Card ── */
.winner-hero-card {
    background: linear-gradient(135deg, rgba(0, 214, 143, 0.10) 0%, rgba(14, 28, 20, 0.95) 100%);
    border: 1.5px solid rgba(0, 214, 143, 0.40);
    border-radius: var(--radius-xl);
    padding: 26px 28px;
    margin: 18px 0;
    box-shadow: var(--shadow-card), 0 0 40px rgba(0, 214, 143, 0.12);
    position: relative;
    overflow: hidden;
}
.winner-hero-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, var(--accent-primary), transparent);
}
.passcode-pill {
    background: rgba(8, 16, 12, 0.95);
    border: 1.5px solid rgba(0, 214, 143, 0.40);
    border-radius: var(--radius-md);
    padding: 10px 22px;
    font-family: var(--font-mono);
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--accent-primary);
    letter-spacing: 2px;
    display: inline-block;
}

/* ── Professional Form Inputs ── */
.stSelectbox > div > div,
.stTextInput > div > div > input,
.stNumberInput > div > div > input {
    background: rgba(8, 18, 12, 0.90) !important;
    border: 1px solid rgba(0, 214, 143, 0.18) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-primary) !important;
    font-family: var(--font-body) !important;
    font-size: 0.88rem !important;
    transition: var(--transition) !important;
}
.stSelectbox > div > div:hover,
.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus {
    border-color: rgba(0, 214, 143, 0.45) !important;
    box-shadow: 0 0 0 3px rgba(0, 214, 143, 0.08) !important;
}

/* ── Professional Button System ── */
.stButton > button {
    background: linear-gradient(135deg, #00D68F 0%, #00A86B 100%) !important;
    color: #03150A !important;
    font-family: var(--font-body) !important;
    font-size: 0.84rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.4px !important;
    padding: 10px 20px !important;
    border-radius: var(--radius-sm) !important;
    border: none !important;
    box-shadow: 0 2px 8px rgba(0, 214, 143, 0.25), 0 1px 2px rgba(0,0,0,0.30) !important;
    transition: var(--transition) !important;
    width: 100% !important;
    cursor: pointer !important;
    position: relative !important;
    overflow: hidden !important;
}
.stButton > button::before {
    content: '' !important;
    position: absolute !important;
    top: 0 !important; left: -100% !important;
    width: 100% !important; height: 100% !important;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.12), transparent) !important;
    transition: left 0.5s ease !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #1AFFA8 0%, #00C97E 100%) !important;
    box-shadow: 0 4px 18px rgba(0, 214, 143, 0.40), 0 2px 4px rgba(0,0,0,0.30) !important;
    transform: translateY(-1px) !important;
}
.stButton > button:hover::before {
    left: 100% !important;
}
.stButton > button:active {
    transform: translateY(0) !important;
    box-shadow: 0 1px 4px rgba(0, 214, 143, 0.20) !important;
}

/* ── Logout / Danger Button override ── */
.stButton > button[data-testid="baseButton-secondary"] {
    background: transparent !important;
    border: 1px solid rgba(239, 68, 68, 0.30) !important;
    color: rgba(239, 68, 68, 0.80) !important;
    box-shadow: none !important;
    font-size: 0.78rem !important;
}
.stButton > button[data-testid="baseButton-secondary"]:hover {
    background: rgba(239, 68, 68, 0.08) !important;
    border-color: rgba(239, 68, 68, 0.55) !important;
    color: var(--crit-red) !important;
    transform: none !important;
    box-shadow: none !important;
}

/* ── Sidebar specific logout button ── */
section[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    border: 1px solid rgba(239, 68, 68, 0.25) !important;
    color: rgba(239, 68, 68, 0.70) !important;
    font-size: 0.76rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.3px !important;
    padding: 7px 16px !important;
    box-shadow: none !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(239, 68, 68, 0.08) !important;
    border-color: rgba(239, 68, 68, 0.50) !important;
    color: var(--crit-red) !important;
    transform: none !important;
    box-shadow: none !important;
}

/* ── Form submit button keep primary style ── */
[data-testid="stFormSubmitButton"] > button {
    background: linear-gradient(135deg, #00D68F 0%, #00A86B 100%) !important;
    color: #03150A !important;
    font-weight: 700 !important;
    letter-spacing: 0.4px !important;
    box-shadow: 0 2px 12px rgba(0, 214, 143, 0.30) !important;
}
[data-testid="stFormSubmitButton"] > button:hover {
    background: linear-gradient(135deg, #1AFFA8 0%, #00C97E 100%) !important;
    box-shadow: 0 4px 20px rgba(0, 214, 143, 0.45) !important;
}

/* ── Slider & other widgets ── */
.stSlider [data-baseweb="slider"] [role="slider"] {
    background: var(--accent-primary) !important;
    border-color: var(--accent-secondary) !important;
    box-shadow: 0 0 0 4px rgba(0, 214, 143, 0.15) !important;
}

/* ── Professional Footer ── */
.cv-footer {
    text-align: center;
    padding: 24px 0 8px;
    border-top: 1px solid rgba(0, 214, 143, 0.08);
    margin-top: 40px;
}
.cv-footer p {
    font-family: var(--font-body);
    font-size: 0.72rem;
    color: var(--text-dim);
    letter-spacing: 0.5px;
    margin: 0;
}

/* ── Admin card ── */
.admin-card {
    background: rgba(14, 26, 18, 0.75);
    border: 1px solid rgba(0, 214, 143, 0.14);
    border-radius: var(--radius-lg);
    padding: 20px 22px;
    margin-bottom: 20px;
    box-shadow: var(--shadow-card);
}




/* ── Banner styles ── */
.banner-cruise {
    background: rgba(16, 185, 129, 0.08);
    border: 1px solid rgba(16, 185, 129, 0.25);
    border-radius: var(--radius-md);
    padding: 14px 20px;
    margin: 4px 0;
}
.banner-cruise-title {
    font-family: var(--font-heading);
    font-size: 0.95rem;
    font-weight: 700;
    color: var(--success-green);
    margin: 0 0 4px;
}
.banner-cruise-sub {
    font-family: var(--font-body);
    font-size: 0.80rem;
    color: var(--text-dim);
    margin: 0;
}

.banner-emergency {
    background: rgba(239, 68, 68, 0.07);
    border: 1px solid rgba(239, 68, 68, 0.25);
    border-radius: var(--radius-md);
    padding: 16px 20px;
    margin: 4px 0;
}
.banner-emergency-title {
    font-family: var(--font-heading);
    font-size: 0.95rem;
    font-weight: 700;
    color: var(--crit-red);
    margin: 0 0 12px;
}

/* ── Charger row inside banners ── */
.charger-card {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin-top: 10px;
}
.charger-row-label {
    font-family: var(--font-body);
    font-size: 0.62rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: var(--text-dim);
    margin: 0 0 2px;
}
.charger-row-value {
    font-family: var(--font-mono);
    font-size: 0.95rem;
    font-weight: 600;
    margin: 0;
}

/* ── Label typography ── */
label[data-testid="stWidgetLabel"] p,
.stMarkdown p {
    font-family: var(--font-body) !important;
}

/* ── Remove default Streamlit padding on widgets ── */
.stSelectbox label, .stTextInput label, .stSlider label, .stNumberInput label {
    font-size: 0.76rem !important;
    color: var(--text-muted) !important;
    font-weight: 500 !important;
}

/* ── Metric style override ── */
[data-testid="stMetric"] {
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-md);
    padding: 14px 16px;
}

/* ── Tab override ── */
.stTabs [data-baseweb="tab-list"] {
    background: transparent;
    border-bottom: 1px solid rgba(0, 214, 143, 0.12);
}
.stTabs [data-baseweb="tab"] {
    font-family: var(--font-body);
    font-size: 0.82rem;
    font-weight: 500;
    color: var(--text-dim);
    border-bottom: 2px solid transparent;
    padding: 8px 16px;
}
.stTabs [aria-selected="true"] {
    color: var(--accent-primary) !important;
    border-bottom-color: var(--accent-primary) !important;
}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════

def _safe_float(val: Any) -> float | None:
    try:
        f = float(val)
        return None if (f != f or abs(f) == float("inf")) else f
    except (TypeError, ValueError):
        return None


@st.cache_data(show_spinner=False, ttl=600)
def _reverse_geocode(lat: float, lon: float) -> str:
    # ── Comprehensive Offline Bounding Box Lookup (avoids Nominatim rate limits) ──
    _BBOX_TABLE = [
        # (center_lat, center_lon, radius_deg, label)
        # Karnataka
        (12.9716, 77.5946, 0.20, "Bengaluru, Karnataka"),
        (15.3173, 75.7139, 0.30, "Dharwad, Karnataka"),
        (12.2958, 76.6394, 0.20, "Mysuru, Karnataka"),
        (13.0285, 77.5197, 0.20, "Peenya / Bengaluru NW, Karnataka"),
        (15.8497, 74.4977, 0.25, "Belagavi, Karnataka"),
        (14.4426, 75.7278, 0.25, "Davangere, Karnataka"),
        (17.3850, 76.8200, 0.25, "Kalaburagi, Karnataka"),
        (13.3409, 77.1000, 0.20, "Tumkur, Karnataka"),
        # Tamil Nadu
        (13.0827, 80.2707, 0.20, "Chennai, Tamil Nadu"),
        (12.7409, 77.8253, 0.20, "Hosur, Tamil Nadu"),
        (12.5186, 78.2137, 0.20, "Krishnagiri, Tamil Nadu"),
        (10.8277, 77.0604, 0.25, "Pollachi / Coimbatore Belt, Tamil Nadu"),
        (11.0168, 76.9558, 0.20, "Coimbatore, Tamil Nadu"),
        (9.9252, 78.1198, 0.20, "Madurai, Tamil Nadu"),
        (10.7905, 78.7047, 0.20, "Tiruchirappalli, Tamil Nadu"),
        (8.7139, 77.7567, 0.20, "Tirunelveli, Tamil Nadu"),
        (11.6643, 78.1460, 0.20, "Salem, Tamil Nadu"),
        (11.3410, 77.7172, 0.20, "Erode, Tamil Nadu"),
        (8.0883, 77.5385, 0.20, "Nagercoil, Tamil Nadu"),
        (12.9249, 79.1325, 0.20, "Vellore, Tamil Nadu"),
        (10.4549, 77.8253, 0.20, "Dindigul, Tamil Nadu"),
        (9.5680, 77.9270, 0.20, "Theni, Tamil Nadu"),
        # Andhra Pradesh / Telangana
        (17.3850, 78.4867, 0.20, "Hyderabad, Telangana"),
        (16.3067, 80.4365, 0.20, "Vijayawada, Andhra Pradesh"),
        (17.6868, 83.2185, 0.20, "Visakhapatnam, Andhra Pradesh"),
        (15.8281, 78.0373, 0.20, "Kurnool, Andhra Pradesh"),
        # Kerala
        (8.5241, 76.9366, 0.20, "Thiruvananthapuram, Kerala"),
        (9.9312, 76.2673, 0.20, "Kochi, Kerala"),
        (11.2588, 75.7804, 0.20, "Kozhikode, Kerala"),
        (10.5276, 76.2144, 0.20, "Thrissur, Kerala"),
        # Maharashtra
        (19.0760, 72.8777, 0.25, "Mumbai, Maharashtra"),
        (18.5204, 73.8567, 0.20, "Pune, Maharashtra"),
        (21.1458, 79.0882, 0.20, "Nagpur, Maharashtra"),
        # Other Major Cities
        (28.6139, 77.2090, 0.20, "New Delhi, Delhi"),
        (13.0827, 80.2707, 0.20, "Chennai, Tamil Nadu"),
        (22.5726, 88.3639, 0.20, "Kolkata, West Bengal"),
        (23.0225, 72.5714, 0.20, "Ahmedabad, Gujarat"),
        (26.9124, 75.7873, 0.20, "Jaipur, Rajasthan"),
        (12.9165, 74.8562, 0.20, "Mangaluru, Karnataka"),
    ]

    for (clat, clon, radius, label) in _BBOX_TABLE:
        if abs(lat - clat) < radius and abs(lon - clon) < radius:
            return label

    # ── Live Nominatim Reverse Geocode (if not matched offline) ──
    try:
        geo = Nominatim(user_agent="chargeverse_ev_fleet_ops_v6")
        res = geo.reverse((lat, lon), language="en", timeout=6)
        if res and res.raw.get("address"):
            a = res.raw["address"]
            city_part = (
                a.get("city")
                or a.get("suburb")
                or a.get("town")
                or a.get("village")
                or a.get("county")
                or a.get("state_district")
                or "Unknown Area"
            )
            state_part = a.get("state") or a.get("country") or "India"
            return f"{city_part}, {state_part}"
    except (GeocoderTimedOut, GeocoderUnavailable, GeocoderRateLimited, GeocoderQuotaExceeded, GeopyError, Exception) as exc:
        _log.warning("Reverse geocode failed gracefully: %s", exc)

    # ── Final fallback: Clean coordinate label ──
    return f"{lat:.4f}° N, {lon:.4f}° E"






def _urgency(cargo: str, batt: float) -> float:
    return SLAGuardianAgent.evaluate_cargo_risk(cargo, batt, 0.0)


def _required_battery(dist_km: float) -> float:
    return round(dist_km * _DRAIN_RATE + _SAFETY_BUFFER, 2)


def _energy_deficit(current: float, required: float) -> float:
    return round(max(0.0, required - current), 2)


def _batt_bar_html(soc: float, required: float | None = None) -> str:
    fill_pct = max(0.0, min(100.0, soc))
    color    = "linear-gradient(90deg, #00D68F, #00C9A7)" if required is None or soc >= required else "linear-gradient(90deg, #EF4444, #F59E0B)"
    marker   = ""
    if required is not None:
        req_pct = max(0.0, min(100.0, required))
        marker  = f'<div style="position:absolute;top:-2px;width:2px;height:12px;background:#F59E0B;border-radius:2px;left:{req_pct:.1f}%;"></div>'
    return (
        f'<div class="cyber-batt-track" style="position:relative;">'
        f'<div class="cyber-batt-fill" style="width:{fill_pct:.1f}%;background:{color};"></div>'
        f'{marker}'
        f'</div>'
    )


@st.cache_data(show_spinner=False, ttl=600)
def _geocode_dest(address: str) -> tuple[float, float] | None:
    try:
        geo = Nominatim(user_agent="chargeverse_ev_fleet_ops_v6")
        loc = geo.geocode(address, timeout=10)
        if loc:
            return (loc.latitude, loc.longitude)
    except (GeocoderTimedOut, GeocoderUnavailable, GeocoderRateLimited, GeocoderQuotaExceeded, GeopyError, Exception) as exc:
        _log.warning("Geocode destination failed gracefully: %s", exc)
    return None


def _status_badge_html(status: str) -> str:
    cls = {
        "Available": "badge-optimal",
        "Busy":      "badge-warning",
        "Offline":   "badge-critical",
    }.get(status, "badge-warning")
    color = {
        "Available": "#10B981",
        "Busy":      "#F59E0B",
        "Offline":   "#EF4444",
    }.get(status, "#F59E0B")
    return f'<span class="cyber-badge {cls}" style="color:{color};border-color:{color}40;">● {status}</span>'


# ══════════════════════════════════════════════════════════════════════
# LOGIN SCREEN
# ══════════════════════════════════════════════════════════════════════

def render_login_page():
    # Logo replaces title
    _lcol1, _lcol2, _lcol3 = st.columns([1.5, 1, 1.5])
    with _lcol2:
        st.image(str(_LOGO_PATH), use_container_width=True)

    st.markdown("""
    <div style="text-align:center;padding:4px 0 12px;">
      <p style="font-family:var(--font-body);font-size:0.84rem;color:var(--text-dim);
                letter-spacing:0.5px;margin:0;">
        Autonomous EV Fleet Operations &middot; India Multi-Station Corridor Command
      </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div style="background:rgba(14,26,18,0.85);backdrop-filter:blur(20px);
                    border:1px solid rgba(0,214,143,0.25);border-radius:20px;
                    padding:32px 28px;margin:10px auto 20px;box-shadow:0 8px 40px rgba(0,0,0,0.40);"
        >
          <p style="font-family:var(--font-heading);font-size:1.35rem;font-weight:800;
                    color:var(--accent-primary);text-align:center;margin:0 0 4px;letter-spacing:-0.3px;">
            Sign In to ChargeVerse
          </p>
          <p style="font-family:var(--font-body);font-size:0.76rem;color:var(--text-dim);
                    text-align:center;letter-spacing:0.3px;margin:0 0 22px;">
            Enter your credentials or click a Quick Login button below
          </p>
        """, unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=False):
            username_input = st.text_input("Username", placeholder="e.g. driver, solar_hub, or whitefield_hub", key="login_user")
            password_input = st.text_input("Password", type="password", placeholder="••••••••", key="login_pass")
            submit_login = st.form_submit_button("→  Sign In")

            if submit_login:
                user_clean = username_input.strip().lower()
                if user_clean in CREDENTIALS and CREDENTIALS[user_clean]["password"] == password_input:
                    st.session_state.logged_in = True
                    st.session_state.username = user_clean
                    st.session_state.role = CREDENTIALS[user_clean]["role"]
                    st.rerun()
                else:
                    st.error("Authentication failed — invalid username or password.")

        st.markdown('<hr style="border:none;border-top:1px solid rgba(0,214,143,0.12);margin:20px 0 16px;">', unsafe_allow_html=True)
        st.markdown('<p style="font-family:var(--font-tech);font-size:0.72rem;color:var(--accent-neon);text-transform:uppercase;letter-spacing:1.5px;text-align:center;margin:0 0 12px;">⚡ Quick Login Options (India EV Hubs)</p>', unsafe_allow_html=True)

        q1, q2 = st.columns(2)
        with q1:
            if st.button("🚚 Fleet Driver (EV-CV-001)", key="q_driver"):
                st.session_state.logged_in = True
                st.session_state.username = "driver"
                st.session_state.role = "driver"
                st.rerun()
            if st.button("🛡️ Station A: [Private] BLR Solar Yard", key="q_station_a"):
                st.session_state.logged_in = True
                st.session_state.username = "solar_hub"
                st.session_state.role = "station_a"
                st.rerun()
            if st.button("⚡ Station B: [Public] Hosur EV Point", key="q_station_b"):
                st.session_state.logged_in = True
                st.session_state.username = "grid_hub"
                st.session_state.role = "station_b"
                st.rerun()
            if st.button("🛡️ Station F: [Private] Hosur Freight Terminal", key="q_station_f"):
                st.session_state.logged_in = True
                st.session_state.username = "hosur_terminal"
                st.session_state.role = "station_f"
                st.rerun()

        with q2:
            if st.button("🛡️ Station C: [Private] Whitefield Tech Hub", key="q_station_c"):
                st.session_state.logged_in = True
                st.session_state.username = "whitefield_hub"
                st.session_state.role = "station_c"
                st.rerun()
            if st.button("⚡ Station D: [Public] Silk Board Metro Depot", key="q_station_d"):
                st.session_state.logged_in = True
                st.session_state.username = "silkboard_hub"
                st.session_state.role = "station_d"
                st.rerun()
            if st.button("⚡ Station E: [Public] Krishnagiri Highway Plaza", key="q_station_e"):
                st.session_state.logged_in = True
                st.session_state.username = "krishnagiri_hub"
                st.session_state.role = "station_e"
                st.rerun()
            if st.button("🛡️ Station G: [Private] Peenya EV Logistics Hub", key="q_station_g"):
                st.session_state.logged_in = True
                st.session_state.username = "peenya_hub"
                st.session_state.role = "station_g"
                st.rerun()



        st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# MAIN ROUTER
# ══════════════════════════════════════════════════════════════════════

if not st.session_state.logged_in:
    render_login_page()
    st.stop()


# ── SIDEBAR ──
with st.sidebar:
    st.image(str(_LOGO_PATH), use_container_width=True)
    st.markdown("""<p style="font-family:var(--font-body);font-size:0.66rem;color:var(--text-dim);text-align:center;letter-spacing:1.2px;text-transform:uppercase;margin:0 0 12px;">Autonomous EV Command</p>""", unsafe_allow_html=True)

    curr_user = CREDENTIALS.get(st.session_state.username, {})
    user_name = curr_user.get("name", st.session_state.username)
    user_icon = curr_user.get("icon", "👤")

    st.markdown(f"""
    <div class="sb-cyber-badge">
      <p style="font-family:var(--font-body);font-size:0.60rem;color:var(--text-dim);
                text-transform:uppercase;letter-spacing:1px;margin:0;">Active Session</p>
      <p style="font-family:var(--font-body);font-size:0.86rem;font-weight:700;color:var(--text-primary);margin:3px 0 0;">
        {user_icon} {user_name}
      </p>
      <p style="font-family:var(--font-mono);font-size:0.66rem;color:var(--accent-primary);margin:3px 0 0;">
        {st.session_state.role}
      </p>
    </div>
    """, unsafe_allow_html=True)

    st.button("→ Sign Out", key="logout_btn", on_click=_do_logout)

    st.markdown('<hr style="border:none;border-top:1px solid rgba(0,214,143,0.08);margin:16px 0;">', unsafe_allow_html=True)

    if st.session_state.role == "driver":
        # ── COMPLETED CHARGE SYNC (Must execute before battery_soc slider widget instantiation) ──
        db_sync = _load_stations_db()
        active_req_sync = db_sync.get("active_requests", {}).get("EV-CV-001")
        req_status = active_req_sync.get("status") if isinstance(active_req_sync, dict) else None

        if req_status in ["ACCEPTED_WINNER", "GATE_PASS_ISSUED", "APPROVED_GATE_PASS", "CHARGING_IN_PROGRESS"]:
            saved_soc = float(active_req_sync.get("battery_soc", 45.0)) if isinstance(active_req_sync, dict) else 45.0
            st.session_state.battery_soc = saved_soc if saved_soc < 100.0 else 45.0
        elif req_status == "CHARGING_COMPLETED" or req_status == "COMPLETED":
            st.session_state.battery_soc       = 100.0
            st.session_state.distance_driven   = 0.0
            st.session_state.alert_active      = False
            st.session_state.alert_status      = "NORMAL"
            st.session_state.auction_triggered = False
            st.session_state.auction_fired     = False
            st.session_state.auction_payload   = None
            st.session_state.auction_results   = None
            st.session_state.winning_station   = None
            st.session_state.top3_stations     = None
            st.toast("🎉 Vehicle battery fully charged! Thank you for using ChargeVerse.")
            # Clear pending alert log from stations_db.json
            _save_stations_db({"active_requests": {"EV-CV-001": None}})


        st.markdown('<p class="sb-label">📦 Cargo Category & SLA</p>', unsafe_allow_html=True)
        cargo_type = st.selectbox(
            "Cargo",
            list(_CARGO.keys()),
            key="selected_cargo_type",
            label_visibility="collapsed",
        )
        cargo_info = _CARGO[cargo_type]
        icon, w_cargo, cargo_desc, req_fast = cargo_info
        st.markdown(
            f'<p style="font-family:var(--font-tech);font-size:0.68rem;color:var(--text-muted);margin:4px 0 0;">'
            f'{icon} {cargo_desc} (W<sub>cargo</sub>={w_cargo:.2f})</p>',
            unsafe_allow_html=True,
        )


        st.markdown('<hr style="border:none;border-top:1px solid rgba(0,214,143,0.06);margin:14px 0;">', unsafe_allow_html=True)
        st.markdown('<p class="sb-label">Destination</p>', unsafe_allow_html=True)
        destination = st.text_input(
            "Destination",
            value="Electronic City, Bangalore",
            placeholder="e.g. Hosur EV Station",
            label_visibility="collapsed",
        )

        st.markdown('<hr style="border:none;border-top:1px solid rgba(0,214,143,0.06);margin:14px 0;">', unsafe_allow_html=True)

        # ── AUTOMATIC REAL-TIME DEVICE GPS LOCATION DETECTION ──
        raw_loc = streamlit_geolocation()
        st.session_state["device_raw_loc"] = raw_loc
        dev_lat = _safe_float(raw_loc.get("latitude") if isinstance(raw_loc, dict) else None)
        dev_lon = _safe_float(raw_loc.get("longitude") if isinstance(raw_loc, dict) else None)

        if dev_lat is not None and dev_lon is not None:
            sb_lat, sb_lon = dev_lat, dev_lon
            sb_loc_label = _reverse_geocode(sb_lat, sb_lon)
            # ── Persist to session_state and URL query params ──
            st.session_state["gps_lat"]   = sb_lat
            st.session_state["gps_lon"]   = sb_lon
            st.session_state["gps_label"] = sb_loc_label
            try:
                st.query_params["lat"]           = str(round(sb_lat, 6))
                st.query_params["lng"]           = str(round(sb_lon, 6))
                st.query_params["location_name"] = sb_loc_label
            except Exception:
                pass
        elif st.session_state.get("gps_lat") is not None:
            # ── Reuse previously detected location from session/URL ──
            sb_lat, sb_lon = st.session_state["gps_lat"], st.session_state["gps_lon"]
            sb_loc_label = st.session_state.get("gps_label") or _reverse_geocode(sb_lat, sb_lon)
        else:
            sb_lat, sb_lon = 12.9716, 77.5946
            sb_loc_label = _reverse_geocode(sb_lat, sb_lon)

        telemetry_sb = FleetEVTelemetry(
            vehicle_id="EV-CV-001",
            current_lat=sb_lat,
            current_long=sb_lon,
            location_label=sb_loc_label,
            current_soc=st.session_state.get("battery_soc", 100.0),
        )

        st.markdown(f'<p class="sb-label">📍 Active Vehicle Location</p>', unsafe_allow_html=True)
        st.markdown(
            f'<div style="background:rgba(0,255,136,0.08);border:1px solid rgba(0,255,136,0.25);border-radius:10px;padding:8px 12px;font-family:var(--font-tech);font-size:0.75rem;color:var(--accent-neon);font-weight:700;">'
            f'📍 {telemetry_sb.location_label}</div>',
            unsafe_allow_html=True,
        )

        st.markdown('<hr style="border:none;border-top:1px solid rgba(0,214,143,0.06);margin:14px 0;">', unsafe_allow_html=True)

        st.markdown('<p class="sb-label">🔋 Battery SoC (%)</p>', unsafe_allow_html=True)
        st.slider(
            "Battery SoC",
            min_value=1.0,
            max_value=100.0,
            step=0.5,
            key="battery_soc",
            label_visibility="collapsed",
        )
        st.markdown(
            f'<p style="font-family:var(--font-body);font-size:0.70rem;color:var(--text-dim);margin:6px 0 0;">'
            f'Distance driven: <b style="color:var(--accent-primary);">{st.session_state.distance_driven:.1f} km</b></p>',
            unsafe_allow_html=True,
        )


# ══════════════════════════════════════════════════════════════════════
# VIEW A: FLEET DRIVER VIEW
# ══════════════════════════════════════════════════════════════════════
if st.session_state.role == "driver":

    st.markdown("""
    <div class="cv-header">
      <h1>🚚 FLEET DRIVER COMMAND CENTER</h1>
      <p>Real-Time EV Telemetry · SLA Risk Engine · Deal_Optimizer Auction Engine</p>
    </div>
    """, unsafe_allow_html=True)

    # ── READ PERSISTED GPS LOCATION (session_state → URL params → geolocation widget) ──
    raw_loc = st.session_state.get("device_raw_loc", {})
    device_lat = _safe_float(raw_loc.get("latitude") if isinstance(raw_loc, dict) else None)
    device_lon = _safe_float(raw_loc.get("longitude") if isinstance(raw_loc, dict) else None)

    if device_lat is not None and device_lon is not None:
        # Fresh live reading from geolocation widget
        lat = device_lat
        lon = device_lon
        city = _reverse_geocode(lat, lon)
        gps_source = "HTML5 DEVICE GPS"
    elif st.session_state.get("gps_lat") is not None:
        # Reuse persisted location from previous detection (survives login/logout/refresh)
        lat = st.session_state["gps_lat"]
        lon = st.session_state["gps_lon"]
        city = st.session_state.get("gps_label") or _reverse_geocode(lat, lon)
        gps_source = "PERSISTED GPS"
    else:
        # No GPS yet detected — use Bengaluru as loading placeholder
        lat = 12.9716
        lon = 77.5946
        city = _reverse_geocode(lat, lon)
        gps_source = "AWAITING GPS"

    telemetry = FleetEVTelemetry(
        vehicle_id="EV-CV-001",
        current_lat=lat,
        current_long=lon,
        location_label=city,
        current_soc=st.session_state.get("battery_soc", 100.0),
    )




    # ── AUTOMATIC ACTIVE RESERVATION CHECK & GATE PASS RECONSTRUCTION ──
    act_sid, act_sdata, act_ev_req = check_active_vehicle_booking()
    if act_sid and act_ev_req:
        # Transition status from ACCEPTED_WINNER to GATE_PASS_ISSUED if needed
        _cur_st = act_ev_req.get("status")
        if _cur_st == "ACCEPTED_WINNER":
            save_stations_db({
                "active_requests": {
                    "EV-CV-001": {
                        "status": "GATE_PASS_ISSUED"
                    }
                }
            })

        # Force alert active & preserve depleted SoC (DO NOT RESTORE BATTERY TO 100% HERE!)
        st.session_state.alert_active = True
        st.session_state.alert_status = "CRITICAL"
        st.session_state.auction_triggered = True

        _deal_recon = dict(act_sdata)
        _deal_recon["station_id"] = act_sid
        _deal_recon["name"] = _deal_recon.get("name", STATIONS_DEFAULTS.get(act_sid, {}).get("name", act_sid))
        _deal_recon["facility_name"] = _deal_recon["name"]
        _deal_recon["passcode"] = _deal_recon.get("passcode", "#808-GATE-PASS")

        if "winning_station" not in st.session_state or st.session_state["winning_station"] is None:
            st.session_state["winning_station"] = _deal_recon

        # Build / restore gate_pass and invoice
        if "gate_pass" not in st.session_state or st.session_state["gate_pass"] is None:
            sec_agent_recon = SecurityPassAgent()
            st.session_state["gate_pass"] = sec_agent_recon.issue_gate_pass(
                winning_deal=_deal_recon,
                cargo_type=act_ev_req.get("cargo_type", "General Cargo")
            )
        if "invoice_ledger" not in st.session_state or st.session_state["invoice_ledger"] is None:
            fintech_agent_recon = FinTechSettlementAgent(initial_wallet_balance=st.session_state.get("wallet_balance", 15000.00))
            _gp_recon_dict = st.session_state["gate_pass"].dict() if hasattr(st.session_state["gate_pass"], 'dict') else {}
            st.session_state["invoice_ledger"] = fintech_agent_recon.execute_settlement(
                gate_pass_data=_gp_recon_dict,
                winning_deal=_deal_recon,
                current_wallet_balance=st.session_state.get("wallet_balance", 15000.00)
            )

    # ── ROUTE MATH & CHARGE STATE READ ──
    db_store = _load_stations_db()
    active_req = db_store.get("active_requests", {}).get("EV-CV-001", {})

    batt        = float(st.session_state.battery_soc)
    dist_driven = float(st.session_state.distance_driven)


    dest_coords = _geocode_dest(destination) if destination.strip() else None
    if dest_coords:
        raw_dist_km = geodesic((lat, lon), dest_coords).kilometers
        dist_km     = max(0.0, raw_dist_km - dist_driven)
    else:
        raw_dist_km = 0.0
        dist_km     = 0.0

    required_batt  = _required_battery(dist_km)
    deficit        = _energy_deficit(batt, required_batt)
    route_feasible = batt >= required_batt
    urgency_score  = _urgency(cargo_type, batt)

    live_stations  = _get_live_stations()

    is_alert_triggered = (batt < 95.0 and deficit > 0.0) or (batt <= 50.0) or (not route_feasible)

    if is_alert_triggered or (act_sid and act_ev_req and act_ev_req.get('status') in ['ACCEPTED_WINNER', 'GATE_PASS_ISSUED', 'APPROVED_GATE_PASS', 'ACCEPTED', 'CHARGING_IN_PROGRESS']):
        st.session_state.alert_active      = True
        st.session_state.alert_status      = "CRITICAL"
        st.session_state.auction_triggered = True
        st.session_state.auction_fired     = True
        # Always re-run the auction with the latest shared station data
        winner, all_bids, fleet_payload, sla_payload, dynamic_pricing_payload, broker_payload, gate_pass_payload, invoice_payload, top3_stations = run_auction_pipeline(
            vehicle_lat=lat,
            vehicle_lon=lon,
            sla_urgency=urgency_score,
            battery_current=batt,
            battery_required=required_batt,
            stations=live_stations,
            cargo_type=cargo_type,
            destination=destination,
            dist_km=dist_km,
        )
        st.session_state.auction_results             = all_bids
        st.session_state.winning_station             = winner
        st.session_state.fleet_payload               = fleet_payload
        st.session_state.sla_payload                 = sla_payload
        st.session_state.broker_payload              = broker_payload
        st.session_state.dynamic_pricing_payload     = dynamic_pricing_payload
        st.session_state.auction_payload             = fleet_payload
        if gate_pass_payload is not None:
            st.session_state.gate_pass               = gate_pass_payload
        if invoice_payload is not None:
            st.session_state.invoice_ledger          = invoice_payload
        st.session_state.wallet_balance              = getattr(invoice_payload, 'wallet_balance_remaining', 15000.00)
        st.session_state.top3_stations               = top3_stations
        _w_payload_dict = st.session_state.get("weather_payload")
        _w_dict = _w_payload_dict.dict() if hasattr(_w_payload_dict, 'dict') else str(_w_payload_dict)

        _rep_scores = st.session_state.get("reputation_scores") or {}
        _rep_dict = {k: (v.dict() if hasattr(v, 'dict') else str(v)) for k, v in _rep_scores.items()}

        st.session_state.pipeline_results            = {
            "Agent 1: WeatherImpact": _w_dict,
            "Agent 2: FleetEV": fleet_payload,
            "Agent 3: SLAGuardian": sla_payload,
            "Agent 4: DynamicPricing": dynamic_pricing_payload,
            "Agent 5: BrokerAuctioneer": broker_payload,
            "Agent 6: StationReputation": _rep_dict,
            "Agent 7: DealOptimizer": {"winning_deal": winner, "candidate_bids": all_bids},
            "Agent 8: YardHost": {
                "assigned_bay": getattr(gate_pass_payload, 'assigned_bay', 'BAY-01'),
                "station_id": winner['station_id'] if winner else None,
                "status": "RESERVED"
            },
            "Agent 9: SecurityPass": gate_pass_payload.dict() if hasattr(gate_pass_payload, 'dict') else str(gate_pass_payload),
            "Agent 10: FinTechSettlement": invoice_payload.dict() if hasattr(invoice_payload, 'dict') else str(invoice_payload)
        }
    else:
        st.session_state.alert_active      = False
        st.session_state.alert_status      = "NORMAL"
        st.session_state.auction_triggered = False
        st.session_state.auction_fired     = False
        st.session_state.auction_payload   = None
        st.session_state.auction_results   = None
        st.session_state.winning_station   = None
        st.session_state.top3_stations     = None



    # ── 4 HERO CARDS (FUTURISTIC WIDGETS) ──
    batt_color = "glow-neon" if route_feasible else ("glow-warn" if batt >= 20.0 else "glow-crit")
    urgency_color = "glow-crit" if urgency_score > 0.70 else ("glow-warn" if urgency_score > 0.40 else "glow-neon")

    c1, c2, c3, c4 = st.columns(4, gap="medium")

    with c1:
        st.markdown(f"""
        <div class="cyber-card">
          <div>
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <span class="card-icon">🔋</span>
              <span class="cyber-badge {'badge-optimal' if route_feasible else 'badge-critical'}">
                {'FEASIBLE' if route_feasible else 'DEFICIT ALERT'}
              </span>
            </div>
            <p class="card-label" style="margin-top:12px;">BATTERY ENERGY SoC</p>
            <p class="card-value {batt_color}">{batt:.1f}%</p>
          </div>
          <div>
            {_batt_bar_html(batt, required_batt)}
            <p style="font-family:var(--font-tech);font-size:0.72rem;color:var(--text-muted);margin:8px 0 0;">
              Driven: {dist_driven:.1f} km · Drain: −{_STEP_DRAIN}% / step
            </p>
          </div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="cyber-card">
          <div>
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <span class="card-icon">📍</span>
              <span class="cyber-badge badge-info">{gps_source}</span>
            </div>
            <p class="card-label" style="margin-top:12px;">TELEMETRY POSITION</p>
            <p class="card-value glow-info" style="font-size:1.15rem;margin-top:4px;">{city}</p>
          </div>
          <div>
            <p style="font-family:var(--font-tech);font-size:0.75rem;color:var(--text-muted);margin:0;">
              Coordinates: {lat:.4f}, {lon:.4f}
            </p>
          </div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="cyber-card">
          <div>
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <span class="card-icon">🛡️</span>
              <span class="cyber-badge badge-optimal">SLA ENGINE</span>
            </div>
            <p class="card-label" style="margin-top:12px;">CARGO SLA URGENCY</p>
            <p class="card-value {urgency_color}">{urgency_score:.4f}</p>
          </div>
          <div>
            <p style="font-family:var(--font-tech);font-size:0.78rem;color:var(--text-primary);margin:0;">
              {icon} {cargo_type}
            </p>
          </div>
        </div>
        """, unsafe_allow_html=True)

    energy_card_color = "glow-neon" if route_feasible else "glow-crit"
    with c4:
        st.markdown(f"""
        <div class="cyber-card">
          <div>
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <span class="card-icon">⚡</span>
              <span class="cyber-badge {'badge-optimal' if route_feasible else 'badge-critical'}">
                {'SUFFICIENT' if route_feasible else f'DEFICIT −{deficit:.1f}%'}
              </span>
            </div>
            <p class="card-label" style="margin-top:12px;">REQUIRED VS CURRENT</p>
            <p class="card-value {energy_card_color}" style="font-size:1.4rem;">
              {batt:.1f}% <span style="color:var(--text-muted);font-size:0.9rem;">of</span> {required_batt:.1f}%
            </p>
          </div>
          <div>
            {_batt_bar_html(batt, required_batt)}
            <p style="font-family:var(--font-tech);font-size:0.72rem;color:var(--text-muted);margin:8px 0 0;">
              Route: {dist_km:.1f} km remaining to dest
            </p>
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<hr class="cv-divider" style="margin:24px 0;">', unsafe_allow_html=True)

    # ── SIMULATION BUTTON CONTROLS ──
    btn1, btn2, btn3, _ = st.columns([1, 1, 1.4, 0.6], gap="medium")
    with btn1:
        st.button("▶️ Simulate Energy Step", on_click=_step_energy)
    with btn2:
        st.button("🔄 Reset Vehicle Energy", on_click=_reset_energy)
    with btn3:
        st.button("📉 Drain Battery to 45% (Test 50% Threshold)", on_click=_drain_to_alert)

    st.markdown('<hr class="cv-divider" style="margin:24px 0;">', unsafe_allow_html=True)



    # ── AUCTION / ROUTE STATUS BANNER (Explicit Threshold Enforcement) ──

    if (batt <= 50.0 or (act_sid and act_ev_req and act_ev_req.get("status") != "CHARGING_COMPLETED")) and st.session_state.get("alert_active", False):
        winner   = st.session_state.winning_station
        all_bids = st.session_state.auction_results or []
        sla_pl   = st.session_state.sla_payload or {}

        top3_ids = st.session_state.get("top3_stations", []) or []
        top3_names = [STATIONS_DEFAULTS[sid]["name"] for sid in top3_ids if sid in STATIONS_DEFAULTS]
        top3_str = ", ".join(top3_names) if top3_names else "Top 3 Stations"

        db_store = _load_stations_db()
        active_req = db_store.get("active_requests", {}).get("EV-CV-001") or {}
        deal_status = active_req.get("status", "PENDING") if isinstance(active_req, dict) else "NORMAL"
        accepted_by_sid = active_req.get("accepted_by") if isinstance(active_req, dict) else None
        accepted_name = STATIONS_DEFAULTS.get(accepted_by_sid, {}).get("name", accepted_by_sid) if accepted_by_sid else None

        if deal_status in ["ACCEPTED", "APPROVED_GATE_PASS", "CHARGING_IN_PROGRESS", "CHARGING_COMPLETED"] and accepted_name:
            status_banner_html = f'<div style="margin-top:12px;padding:10px 16px;background:rgba(16,185,129,0.15);border:1.5px solid #10B981;border-radius:12px;color:#10B981;font-weight:700;font-size:0.88rem;">🔒 DEAL CONFIRMED &amp; LOCKED BY {accepted_name.upper()} (Passcode: #808-GATE-PASS)</div>'
        else:
            status_banner_html = f'<div style="margin-top:12px;padding:10px 16px;background:rgba(245,158,11,0.12);border:1.5px solid #F59E0B;border-radius:12px;color:#F59E0B;font-weight:700;font-size:0.88rem;">⏳ Broadcast alert sent to {len(top3_names)} nearby stations: <b style="color:#F59E0B;">{top3_str}</b>. Awaiting acceptance from a station host...</div>'

        st.markdown(f"""
        <div class="banner-emergency">
          <p class="banner-emergency-title">🚨 INSUFFICIENT ROUTE ENERGY — Top-3 Multi-Agent Auction Triggered!</p>
          <div class="charger-card">
            <div><p class="charger-row-label">Vehicle ID</p><p class="charger-row-value glow-neon">EV-CV-001</p></div>
            <div><p class="charger-row-label">Energy Deficit</p><p class="charger-row-value glow-crit">−{deficit:.1f}%</p></div>
            <div><p class="charger-row-label">Required SoC</p><p class="charger-row-value glow-warn">{required_batt:.1f}%</p></div>
            <div><p class="charger-row-label">SLA Urgency</p><p class="charger-row-value glow-warn">{urgency_score:.4f}</p></div>
          </div>
          {status_banner_html}
        </div>
        """, unsafe_allow_html=True)


        # ── 🌦️ WEATHER IMPACT AGENT ALERT CARD ──
        _w_pl = st.session_state.get("weather_payload")
        if _w_pl:
            st.markdown(f"""
            <div style="background:linear-gradient(135deg, rgba(0,191,255,0.12) 0%, rgba(14,26,18,0.95) 100%);
                        border:2px solid #00BFFF;border-radius:18px;padding:20px;margin-bottom:20px;
                        box-shadow:0 0 30px rgba(0,191,255,0.20);">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                <div>
                  <p style="font-family:var(--font-heading);font-size:1.0rem;font-weight:900;color:#00BFFF;margin:0;">
                    🌦️ WeatherImpactAgent: Real-Time Environmental Strain Analysis
                  </p>
                  <p style="font-family:var(--font-tech);font-size:0.78rem;color:var(--text-muted);margin:4px 0 0;">
                    Condition Breakdown: <b style="color:#00BFFF;">{_w_pl.weather_condition_summary}</b>
                  </p>
                </div>
                <span class="cyber-badge" style="background:rgba(0,191,255,0.18);border:1.5px solid #00BFFF;color:#00BFFF;font-size:0.82rem;font-weight:900;padding:6px 16px;">
                  🌦️ Weather Impact Factor: +{int((_w_pl.impact_multiplier - 1.0)*100)}% Energy Strain
                </span>
              </div>

              <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:14px;background:rgba(6,16,12,0.65);padding:14px;border-radius:12px;border:1px solid rgba(0,191,255,0.25);">
                <div>
                  <p style="font-size:0.62rem;color:var(--text-dim);text-transform:uppercase;margin:0;">Temperature</p>
                  <p style="font-family:var(--font-heading);font-size:1.1rem;font-weight:800;color:{'#EF4444' if _w_pl.temp_factor > 0 else '#00FF88'};margin:3px 0 0;">{_w_pl.temperature_c:.1f}°C</p>
                </div>
                <div>
                  <p style="font-size:0.62rem;color:var(--text-dim);text-transform:uppercase;margin:0;">Precipitation</p>
                  <p style="font-family:var(--font-heading);font-size:1.1rem;font-weight:800;color:{'#00BFFF' if _w_pl.is_raining else '#00FF88'};margin:3px 0 0;">{'Active Rain (+15%)' if _w_pl.is_raining else 'None (0%)'}</p>
                </div>
                <div>
                  <p style="font-size:0.62rem;color:var(--text-dim);text-transform:uppercase;margin:0;">Wind Drag</p>
                  <p style="font-family:var(--font-heading);font-size:1.1rem;font-weight:800;color:{'#F59E0B' if _w_pl.wind_factor > 0 else '#00FF88'};margin:3px 0 0;">{_w_pl.wind_speed_kmh:.1f} km/h</p>
                </div>
                <div>
                  <p style="font-size:0.62rem;color:var(--text-dim);text-transform:uppercase;margin:0;">kWh Calculation</p>
                  <p style="font-family:var(--font-heading);font-size:1.0rem;font-weight:800;color:#00FF88;margin:3px 0 0;">
                    Base: {_w_pl.base_kwh_needed:.1f} kWh ➔ Adjusted: <span style="color:#00BFFF;font-size:1.1rem;font-weight:900;">{_w_pl.adjusted_kwh_needed:.1f} kWh</span>
                  </p>
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)

        # ── 9-AGENT PIPELINE PROCESS VISUALIZATION & EXPANDERS (Hidden once deal is accepted) ──
        _is_deal_locked = deal_status in ["ACCEPTED", "ACCEPTED_WINNER", "GATE_PASS_ISSUED", "APPROVED_GATE_PASS", "CHARGING_IN_PROGRESS"]

        if not _is_deal_locked:
            _broker_pl       = st.session_state.get("broker_payload") or {}
            _dp_pl           = st.session_state.get("dynamic_pricing_payload") or {}
            _broker_eligible = _broker_pl.get("eligible_count", 0)
            _broker_rejected = _broker_pl.get("rejected_count", 0)
            _dp_tou_mult     = _dp_pl.get("tou_multiplier", 1.0)
            _dp_tier_counts  = _dp_pl.get("tier_counts", {})
            _dp_surge_count  = _dp_tier_counts.get("PEAK_SURGE", 0)
            _dp_disc_count   = _dp_tier_counts.get("OFF_PEAK_DISCOUNT", 0)
            _w_mult          = _w_pl.impact_multiplier if _w_pl else 1.0
            st.markdown(f"""
            <div class="agent-pipeline-box">
              <p style="font-family:var(--font-heading);font-size:1.0rem;color:var(--accent-neon);
                        margin:0 0 16px;letter-spacing:1px;text-transform:uppercase;">
                🤖 AUTONOMOUS 10-AGENT EXECUTION PIPELINE
              </p>
              <div style="display:grid;grid-template-columns:repeat(10, 1fr);gap:5px;">
                <div class="agent-step-card" style="border-color:rgba(0,191,255,0.45);box-shadow:0 0 14px rgba(0,191,255,0.18);">
                  <p style="font-family:var(--font-heading);font-size:0.68rem;color:#00BFFF;margin:0 0 4px;">
                    1️⃣ Weather_Impact
                  </p>
                  <p style="font-family:var(--font-tech);font-size:0.60rem;color:var(--text-muted);margin:0 0 4px;">
                    Env Strain
                  </p>
                  <p style="font-size:0.65rem;color:#00BFFF;margin:0;">×{_w_mult:.2f} Strain</p>
                </div>
                <div class="agent-step-card">
                  <p style="font-family:var(--font-heading);font-size:0.68rem;color:var(--accent-neon);margin:0 0 4px;">
                    2️⃣ Fleet_EV
                  </p>
                  <p style="font-family:var(--font-tech);font-size:0.60rem;color:var(--text-muted);margin:0 0 4px;">
                    Telemetry
                  </p>
                  <p style="font-size:0.65rem;color:var(--crit-red);margin:0;">Deficit −{deficit:.1f}%</p>
                </div>
                <div class="agent-step-card">
                  <p style="font-family:var(--font-heading);font-size:0.68rem;color:var(--warn-gold);margin:0 0 4px;">
                    3️⃣ SLA_Guardian
                  </p>
                  <p style="font-family:var(--font-tech);font-size:0.60rem;color:var(--text-muted);margin:0 0 4px;">
                    Cargo Risk
                  </p>
                  <p style="font-size:0.65rem;color:var(--warn-gold);margin:0;">Score {urgency_score:.2f}</p>
                </div>
                <div class="agent-step-card" style="border-color:rgba(52,211,153,0.45);box-shadow:0 0 14px rgba(52,211,153,0.15);">
                  <p style="font-family:var(--font-heading);font-size:0.68rem;color:#34D399;margin:0 0 4px;">
                    4️⃣ Dyn_Pricing
                  </p>
                  <p style="font-family:var(--font-tech);font-size:0.60rem;color:var(--text-muted);margin:0 0 4px;">
                    ToU Tariff
                  </p>
                  <p style="font-size:0.65rem;color:#34D399;margin:0;">×{_dp_tou_mult:.2f} ToU</p>
                </div>
                <div class="agent-step-card" style="border-color:rgba(0,191,255,0.45);box-shadow:0 0 14px rgba(0,191,255,0.18);">
                  <p style="font-family:var(--font-heading);font-size:0.68rem;color:#00BFFF;margin:0 0 4px;">
                    5️⃣ Broker_Auction
                  </p>
                  <p style="font-family:var(--font-tech);font-size:0.60rem;color:var(--text-muted);margin:0 0 4px;">
                    Clearing
                  </p>
                  <p style="font-size:0.65rem;color:#00BFFF;margin:0;">✅ {_broker_eligible} · ❌ {_broker_rejected}</p>
                </div>
                <div class="agent-step-card" style="border-color:rgba(255,213,79,0.45);box-shadow:0 0 14px rgba(255,213,79,0.18);">
                  <p style="font-family:var(--font-heading);font-size:0.68rem;color:#FFD54F;margin:0 0 4px;">
                    6️⃣ Station_Reputation
                  </p>
                  <p style="font-family:var(--font-tech);font-size:0.60rem;color:var(--text-muted);margin:0 0 4px;">
                    Trust Audit
                  </p>
                  <p style="font-size:0.65rem;color:#FFD54F;margin:0;">⭐ Rating &amp; Uptime</p>
                </div>
                <div class="agent-step-card">
                  <p style="font-family:var(--font-heading);font-size:0.68rem;color:var(--accent-lime);margin:0 0 4px;">
                    7️⃣ Deal_Optimizer
                  </p>
                  <p style="font-family:var(--font-tech);font-size:0.60rem;color:var(--text-muted);margin:0 0 4px;">
                    Auction
                  </p>
                  <p style="font-size:0.65rem;color:var(--accent-lime);margin:0;">Winner Select</p>
                </div>
                <div class="agent-step-card">
                  <p style="font-family:var(--font-heading);font-size:0.68rem;color:var(--accent-primary);margin:0 0 4px;">
                    8️⃣ Yard_Host
                  </p>
                  <p style="font-family:var(--font-tech);font-size:0.60rem;color:var(--text-muted);margin:0 0 4px;">
                    Hardware
                  </p>
                  <p style="font-size:0.65rem;color:var(--accent-primary);margin:0;">Bay Allocated</p>
                </div>
                <div class="agent-step-card" style="border-color:rgba(16,185,129,0.45);box-shadow:0 0 14px rgba(16,185,129,0.18);">
                  <p style="font-family:var(--font-heading);font-size:0.68rem;color:#10B981;margin:0 0 4px;">
                    9️⃣ Security_Pass
                  </p>
                  <p style="font-family:var(--font-tech);font-size:0.60rem;color:var(--text-muted);margin:0 0 4px;">
                    Gate Access
                  </p>
                  <p style="font-size:0.65rem;color:#10B981;margin:0;">QR Verified</p>
                </div>
                <div class="agent-step-card" style="border-color:rgba(245,158,11,0.45);box-shadow:0 0 14px rgba(245,158,11,0.18);">
                  <p style="font-family:var(--font-heading);font-size:0.68rem;color:#F59E0B;margin:0 0 4px;">
                    🔟 FinTech_Escrow
                  </p>
                  <p style="font-family:var(--font-tech);font-size:0.60rem;color:var(--text-muted);margin:0 0 4px;">
                    Escrow &amp; Tax
                  </p>
                  <p style="font-size:0.65rem;color:#F59E0B;margin:0;">18% GST Settled</p>
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)

        # ── 📈 DYNAMIC PRICING AGENT EXPANDER ──
        _dp_pl2 = st.session_state.get("dynamic_pricing_payload") or {}
        if _dp_pl2:
            _dp_stations    = _dp_pl2.get("station_pricing", [])
            _dp_tou         = _dp_pl2.get("tou_multiplier", 1.0)
            _dp_band        = _dp_pl2.get("tou_band", "STANDARD")
            _dp_hour        = _dp_pl2.get("current_hour", 0)
            _dp_floor       = _dp_pl2.get("min_tariff_floor", 8.0)
            _dp_cap         = _dp_pl2.get("max_tariff_cap", 25.0)
            _dp_total       = _dp_pl2.get("total_stations_priced", 0)
            _dp_tc          = _dp_pl2.get("tier_counts", {})
            _dp_surge       = _dp_tc.get("PEAK_SURGE", 0)
            _dp_std         = _dp_tc.get("STANDARD", 0)
            _dp_disc        = _dp_tc.get("OFF_PEAK_DISCOUNT", 0)
            _tou_band_emoji = {"PEAK": "🔴", "OFF_PEAK": "🟢", "STANDARD": "🟡"}.get(_dp_band, "🟡")
            _tou_color      = {"PEAK": "#EF4444", "OFF_PEAK": "#10B981", "STANDARD": "#F59E0B"}.get(_dp_band, "#F59E0B")
            _tou_bg         = {"PEAK": "rgba(239,68,68,0.10)", "OFF_PEAK": "rgba(16,185,129,0.10)", "STANDARD": "rgba(245,158,11,0.08)"}.get(_dp_band, "rgba(245,158,11,0.08)")
            _tou_border     = {"PEAK": "rgba(239,68,68,0.38)", "OFF_PEAK": "rgba(16,185,129,0.35)", "STANDARD": "rgba(245,158,11,0.32)"}.get(_dp_band, "rgba(245,158,11,0.32)")

            with st.expander(
                f"📈 Dynamic Pricing Agent — Real-Time ToU & Congestion Tariff Engine"
                f"  ·  {_tou_band_emoji} {_dp_band}  ·  ×{_dp_tou:.2f} ToU  ·  {_dp_total} Stations Priced",
                expanded=True,
            ):
                st.markdown(f"""
                <div style="background:linear-gradient(135deg,rgba(52,211,153,0.10) 0%,rgba(52,211,153,0.03) 100%);
                            border:1.5px solid rgba(52,211,153,0.38);border-radius:14px;
                            padding:14px 20px;margin-bottom:18px;
                            box-shadow:0 0 22px rgba(52,211,153,0.08);">
                  <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;">
                    <span style="font-size:1.6rem;">📈</span>
                    <div>
                      <p style="font-family:var(--font-heading);font-size:0.95rem;font-weight:900;
                                color:#34D399;margin:0;letter-spacing:0.3px;">
                        Dynamic Pricing Agent: Real-Time ToU &amp; Congestion Tariff Engine
                      </p>
                      <p style="font-family:var(--font-body);font-size:0.72rem;color:var(--text-muted);
                                margin:3px 0 0;letter-spacing:0.8px;text-transform:uppercase;">
                        🕐 Hour {_dp_hour:02d}:00 &nbsp;·&nbsp; ToU Band:
                        <span style="color:{_tou_color};font-weight:700;">{_tou_band_emoji} {_dp_band}</span>
                        &nbsp;·&nbsp; Multiplier: <span style="color:{_tou_color};font-weight:700;">×{_dp_tou:.2f}</span>
                        &nbsp;·&nbsp; Bounds: &#8377;{_dp_floor:.0f} – &#8377;{_dp_cap:.0f}/kWh
                      </p>
                    </div>
                    <div style="margin-left:auto;display:flex;gap:8px;flex-wrap:wrap;">
                      <span style="background:{_tou_bg};border:1px solid {_tou_border};
                                   border-radius:20px;padding:5px 13px;font-family:var(--font-body);
                                   font-size:0.72rem;font-weight:700;color:{_tou_color};">
                        {_tou_band_emoji} {_dp_band} PERIOD
                      </span>
                    </div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

                _dm1, _dm2, _dm3, _dm4, _dm5 = st.columns(5)
                for _dmc, _dico, _dlbl, _dval, _dcol in [
                    (_dm1, "🕐", "ToU Band",          f"{_dp_band}",           _tou_color),
                    (_dm2, "✖️", "ToU Multiplier",  f"×{_dp_tou:.2f}",  _tou_color),
                    (_dm3, "🔴", "Peak Surge",        str(_dp_surge),           "#EF4444"),
                    (_dm4, "🟡", "Standard",          str(_dp_std),             "#F59E0B"),
                    (_dm5, "🟢", "Off-Peak Discount", str(_dp_disc),            "#10B981"),
                ]:
                    _dmc.markdown(
                        f'<div style="background:rgba(14,26,18,0.80);border:1px solid rgba(52,211,153,0.14);'
                        f'border-radius:12px;padding:11px 12px;text-align:center;">'
                        f'<p style="font-size:1.1rem;margin:0;">{_dico}</p>'
                        f'<p style="font-family:var(--font-body);font-size:0.60rem;font-weight:600;'
                        f'text-transform:uppercase;letter-spacing:0.9px;color:var(--text-dim);margin:4px 0 2px;">{_dlbl}</p>'
                        f'<p style="font-family:var(--font-heading);font-size:1.1rem;font-weight:900;'
                        f'color:{_dcol};margin:0;">{_dval}</p>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

                st.markdown(
                    '<p style="font-family:var(--font-heading);font-size:0.84rem;font-weight:900;'
                    'color:#34D399;margin:0 0 10px;letter-spacing:0.5px;">'
                    '📊 Station Tariff Adjustment Table — Base vs Dynamic Price</p>',
                    unsafe_allow_html=True,
                )
                if _dp_stations:
                    _dp_rows_html = ""
                    _rep_scores_dict = st.session_state.get("reputation_scores") or {}

                    for _dp_s in _dp_stations:
                        _sid_cur    = _dp_s["station_id"]
                        _tier       = _dp_s["pricing_tier"]
                        _ft_icon    = "🛡️" if _dp_s["facility_type"] == "PRIVATE_YARD" else "⚡"
                        _ft_label   = "Private Yard" if _dp_s["facility_type"] == "PRIVATE_YARD" else "Public Station"
                        _ft_color   = "#00BFFF" if _dp_s["facility_type"] == "PRIVATE_YARD" else "#10B981"
                        _base       = _dp_s["base_tariff"]
                        _dynamic    = _dp_s["dynamic_tariff"]
                        _surge_val  = _dp_s["congestion_surcharge"]
                        _delta      = _dynamic - _base
                        _delta_str  = f"+{_delta:.4f}" if _delta >= 0 else f"{_delta:.4f}"
                        _delta_col  = "#EF4444" if _delta > 0 else ("#10B981" if _delta < 0 else "#9CA3AF")

                        # Lookup Reputation Score for unified column display
                        _rep_item   = _rep_scores_dict.get(_sid_cur)
                        _r_rating   = _rep_item.user_rating if _rep_item else STATIONS_DEFAULTS.get(_sid_cur, {}).get("rating", 4.2)
                        _r_uptime   = _rep_item.uptime_pct if _rep_item else STATIONS_DEFAULTS.get(_sid_cur, {}).get("uptime_pct", 98.0)
                        _r_mult     = _rep_item.reputation_multiplier if _rep_item else 1.0
                        _r_badge    = _rep_item.badge_label if _rep_item else "STANDARD VERIFIED"
                        _r_color    = "#10B981" if _r_mult > 1.0 else ("#EF4444" if _r_mult < 1.0 else "#F59E0B")

                        _tier_cfg = {
                            "PEAK_SURGE":        ("🔴 PEAK SURGE",        "rgba(239,68,68,0.14)",  "rgba(239,68,68,0.38)",  "#EF4444"),
                            "STANDARD":          ("🟡 STANDARD",          "rgba(245,158,11,0.10)", "rgba(245,158,11,0.35)", "#F59E0B"),
                            "OFF_PEAK_DISCOUNT": ("🟢 OFF-PEAK DISCOUNT", "rgba(16,185,129,0.12)", "rgba(16,185,129,0.38)", "#10B981"),
                        }.get(_tier, ("🟡 STANDARD", "rgba(245,158,11,0.10)", "rgba(245,158,11,0.35)", "#F59E0B"))
                        _tier_label, _tier_bg, _tier_border, _tier_col = _tier_cfg
                        _surge_str = (f"+{_surge_val:.4f}" if _surge_val >= 0 else f"{_surge_val:.4f}") if _surge_val != 0 else "—"
                        _surge_col = "#EF4444" if _surge_val > 0 else ("#10B981" if _surge_val < 0 else "#9CA3AF")

                        _dp_rows_html += f"""
                        <tr>
                          <td style="padding:11px 14px;border-bottom:1px solid rgba(52,211,153,0.08);">
                            <p style="font-family:var(--font-heading);font-size:0.84rem;font-weight:800;color:#F0FDF6;margin:0;">{_dp_s["facility_name"]}</p>
                          </td>
                          <td style="padding:11px 14px;border-bottom:1px solid rgba(52,211,153,0.08);">
                            <span style="font-family:var(--font-body);font-size:0.72rem;font-weight:700;color:{_ft_color};">{_ft_icon} {_ft_label}</span>
                          </td>
                          <td style="padding:11px 14px;border-bottom:1px solid rgba(52,211,153,0.08);text-align:center;">
                            <span style="font-family:var(--font-heading);font-size:0.88rem;font-weight:800;color:#FFD54F;">⭐ {_r_rating:.1f}★</span>
                            <span style="font-size:0.62rem;color:var(--text-dim);display:block;">{_r_uptime:.1f}% Uptime</span>
                          </td>
                          <td style="padding:11px 14px;border-bottom:1px solid rgba(52,211,153,0.08);text-align:center;">
                            <span style="font-family:var(--font-mono);font-size:0.88rem;font-weight:900;color:{_r_color};">×{_r_mult:.2f}</span>
                          </td>
                          <td style="padding:11px 14px;border-bottom:1px solid rgba(52,211,153,0.08);text-align:right;">
                            <span style="font-family:var(--font-heading);font-size:0.88rem;font-weight:700;color:#9CA3AF;">${_base:.4f}</span>
                          </td>
                          <td style="padding:11px 14px;border-bottom:1px solid rgba(52,211,153,0.08);text-align:right;">
                            <span style="font-family:var(--font-heading);font-size:0.92rem;font-weight:900;color:#F59E0B;">${_dynamic:.4f}</span>
                            <span style="font-size:0.62rem;color:{_delta_col};display:block;margin-top:1px;">{_delta_str}/kWh</span>
                          </td>
                          <td style="padding:11px 14px;border-bottom:1px solid rgba(52,211,153,0.08);text-align:center;">
                            <span style="font-family:var(--font-mono);font-size:0.82rem;font-weight:700;color:{_tou_color};">×{_dp_tou:.2f}</span>
                          </td>
                          <td style="padding:11px 14px;border-bottom:1px solid rgba(52,211,153,0.08);text-align:center;">
                            <span style="background:{_tier_bg};border:1px solid {_tier_border};
                                         border-radius:20px;padding:3px 10px;font-size:0.65rem;
                                         font-weight:700;color:{_tier_col};letter-spacing:0.4px;white-space:nowrap;">
                              {_tier_label}
                            </span>
                          </td>
                        </tr>"""
                    st.markdown(f"""
                    <div style="background:rgba(8,20,14,0.85);border:1.5px solid rgba(52,211,153,0.22);
                                border-radius:14px;overflow:hidden;">
                      <table style="width:100%;border-collapse:collapse;">
                        <thead>
                          <tr style="background:rgba(52,211,153,0.07);border-bottom:1.5px solid rgba(52,211,153,0.22);">
                            <th style="padding:10px 14px;text-align:left;font-family:var(--font-body);font-size:0.63rem;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;color:#34D399;">Station</th>
                            <th style="padding:10px 14px;text-align:left;font-family:var(--font-body);font-size:0.63rem;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;color:#34D399;">Type</th>
                            <th style="padding:10px 14px;text-align:center;font-family:var(--font-body);font-size:0.63rem;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;color:#FFD54F;">Rating &amp; Uptime</th>
                            <th style="padding:10px 14px;text-align:center;font-family:var(--font-body);font-size:0.63rem;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;color:#FFD54F;">Trust Multiplier</th>
                            <th style="padding:10px 14px;text-align:right;font-family:var(--font-body);font-size:0.63rem;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;color:#34D399;">Base Tariff</th>
                            <th style="padding:10px 14px;text-align:right;font-family:var(--font-body);font-size:0.63rem;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;color:#34D399;">Dynamic Tariff</th>
                            <th style="padding:10px 14px;text-align:center;font-family:var(--font-body);font-size:0.63rem;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;color:#34D399;">ToU ×</th>
                            <th style="padding:10px 14px;text-align:center;font-family:var(--font-body);font-size:0.63rem;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;color:#34D399;">Pricing Tier</th>
                          </tr>
                        </thead>
                        <tbody>{_dp_rows_html}</tbody>
                      </table>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(
                        '<div style="background:rgba(52,211,153,0.04);border:1px solid rgba(52,211,153,0.15);'
                        'border-radius:10px;padding:14px 18px;">'
                        '<p style="font-size:0.80rem;color:var(--text-muted);margin:0;">No station pricing data available.</p>'
                        '</div>',
                        unsafe_allow_html=True,
                    )


        # ── 🛡️ STATION REPUTATION AGENT EXPANDER ──
        _rep_map = st.session_state.get("reputation_scores") or {}
        if _rep_map:
            with st.expander(
                f"🛡️ Station Reputation & Trust Agent — Historical Quality & Rating Audit  ·  {len(_rep_map)} Hosts Evaluated",
                expanded=True,
            ):
                _rep_rows_html = ""
                for _sid, _rdata in _rep_map.items():
                    _r_rating = _rdata.user_rating
                    _r_uptime = _rdata.uptime_pct
                    _r_mult   = _rdata.reputation_multiplier
                    _r_badge  = _rdata.badge_label
                    _r_desc   = _rdata.explanation
                    _r_name   = _rdata.facility_name
                    
                    _b_color = "#10B981" if _r_mult > 1.0 else ("#EF4444" if _r_mult < 1.0 else "#F59E0B")
                    _b_bg    = "rgba(16,185,129,0.12)" if _r_mult > 1.0 else ("rgba(239,68,68,0.12)" if _r_mult < 1.0 else "rgba(245,158,11,0.10)")

                    _rep_rows_html += f"""
                    <tr>
                      <td style="padding:10px 14px;border-bottom:1px solid rgba(255,213,79,0.10);">
                        <p style="font-family:var(--font-heading);font-size:0.85rem;font-weight:800;color:#F0FDF6;margin:0;">{_r_name}</p>
                      </td>
                      <td style="padding:10px 14px;border-bottom:1px solid rgba(255,213,79,0.10);text-align:center;">
                        <span style="font-family:var(--font-heading);font-size:0.88rem;font-weight:800;color:#FFD54F;">⭐ {_r_rating:.1f}★</span>
                      </td>
                      <td style="padding:10px 14px;border-bottom:1px solid rgba(255,213,79,0.10);text-align:center;">
                        <span style="font-family:var(--font-mono);font-size:0.84rem;font-weight:700;color:#00BFFF;">{_r_uptime:.1f}%</span>
                      </td>
                      <td style="padding:10px 14px;border-bottom:1px solid rgba(255,213,79,0.10);text-align:center;">
                        <span style="font-family:var(--font-mono);font-size:0.88rem;font-weight:900;color:{_b_color};">×{_r_mult:.2f}</span>
                      </td>
                      <td style="padding:10px 14px;border-bottom:1px solid rgba(255,213,79,0.10);">
                        <span style="background:{_b_bg};border:1px solid {_b_color};border-radius:14px;padding:4px 10px;font-size:0.72rem;font-weight:700;color:{_b_color};">
                          {_r_badge}
                        </span>
                      </td>
                    </tr>"""

                st.markdown(f"""
                <div style="background:rgba(18,24,14,0.85);border:1.5px solid rgba(255,213,79,0.28);border-radius:14px;overflow:hidden;">
                  <table style="width:100%;border-collapse:collapse;">
                    <thead>
                      <tr style="background:rgba(255,213,79,0.08);border-bottom:1.5px solid rgba(255,213,79,0.25);">
                        <th style="padding:10px 14px;text-align:left;font-family:var(--font-body);font-size:0.63rem;font-weight:700;text-transform:uppercase;color:#FFD54F;">Station Host</th>
                        <th style="padding:10px 14px;text-align:center;font-family:var(--font-body);font-size:0.63rem;font-weight:700;text-transform:uppercase;color:#FFD54F;">User Rating</th>
                        <th style="padding:10px 14px;text-align:center;font-family:var(--font-body);font-size:0.63rem;font-weight:700;text-transform:uppercase;color:#FFD54F;">Charger Uptime</th>
                        <th style="padding:10px 14px;text-align:center;font-family:var(--font-body);font-size:0.63rem;font-weight:700;text-transform:uppercase;color:#FFD54F;">Trust Multiplier</th>
                        <th style="padding:10px 14px;text-align:left;font-family:var(--font-body);font-size:0.63rem;font-weight:700;text-transform:uppercase;color:#FFD54F;">Reputation Audit Badge</th>
                      </tr>
                    </thead>
                    <tbody>{_rep_rows_html}</tbody>
                  </table>
                </div>
                """, unsafe_allow_html=True)


        # ── 🔐 SECURITY PASS AGENT EXPANDER ──
        _gp = st.session_state.get("gate_pass")
        if _gp:
            _gp_status_color = "#10B981" if _gp.status == "GRANTED" else "#EF4444"
            _gp_badge_label  = "🟢 CLEARANCE GRANTED" if _gp.status == "GRANTED" else "🔴 ACCESS DENIED"

            with st.expander(
                f"🔐 Security Pass Agent — Cryptographic Digital Gate Pass  ·  {_gp_badge_label}  ·  {_gp.pass_id}",
                expanded=True,
            ):
                st.markdown(f"""
                <div style="background:linear-gradient(135deg,rgba(16,185,129,0.10) 0%,rgba(16,185,129,0.03) 100%);
                            border:1.5px solid rgba(16,185,129,0.40);border-radius:14px;
                            padding:14px 20px;margin-bottom:18px;
                            box-shadow:0 0 24px rgba(16,185,129,0.10);">
                  <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;">
                    <span style="font-size:1.6rem;">🔐</span>
                    <div>
                      <p style="font-family:var(--font-heading);font-size:0.95rem;font-weight:900;
                                color:#10B981;margin:0;letter-spacing:0.3px;">
                        Security Pass Agent: Cryptographic Digital Gate Pass Issued
                      </p>
                      <p style="font-family:var(--font-body);font-size:0.72rem;color:var(--text-muted);
                                margin:3px 0 0;letter-spacing:0.8px;text-transform:uppercase;">
                        🛡️ Authenticated EV-CV-001 &nbsp;·&nbsp; Target Station: <span style="color:#10B981;font-weight:700;">{_gp.station_name}</span>
                        &nbsp;·&nbsp; Valid Until: <span style="color:#F59E0B;font-weight:700;">{_gp.valid_until}</span>
                      </p>
                    </div>
                    <div style="margin-left:auto;">
                      <span style="background:rgba(16,185,129,0.14);border:1px solid rgba(16,185,129,0.40);
                                   border-radius:20px;padding:6px 16px;font-family:var(--font-heading);
                                   font-size:0.78rem;font-weight:800;color:{_gp_status_color};letter-spacing:0.5px;">
                        {_gp_badge_label}
                      </span>
                    </div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

                _gpc1, _gpc2 = st.columns([2.5, 1.0])
                with _gpc1:
                    st.markdown(f"""
                    <div style="background:rgba(14,26,18,0.85);border:1px solid rgba(16,185,129,0.20);
                                border-radius:12px;padding:16px;height:100%;">
                      <div style="display:grid;grid-template-columns:repeat(2, 1fr);gap:14px;">
                        <div>
                          <p style="font-size:0.65rem;color:var(--text-dim);text-transform:uppercase;letter-spacing:1px;margin:0;">Pass Identifier</p>
                          <p style="font-family:var(--font-heading);font-size:1.0rem;font-weight:800;color:#10B981;margin:4px 0 0;">{_gp.pass_id}</p>
                        </div>
                        <div>
                          <p style="font-size:0.65rem;color:var(--text-dim);text-transform:uppercase;letter-spacing:1px;margin:0;">Assigned Charger Bay</p>
                          <p style="font-family:var(--font-heading);font-size:1.0rem;font-weight:800;color:#00BFFF;margin:4px 0 0;">⚡ {_gp.assigned_bay}</p>
                        </div>
                        <div>
                          <p style="font-size:0.65rem;color:var(--text-dim);text-transform:uppercase;letter-spacing:1px;margin:0;">SHA-256 Security Token</p>
                          <p style="font-family:var(--font-mono);font-size:0.88rem;font-weight:700;color:#F59E0B;margin:4px 0 0;">{_gp.security_hash}</p>
                        </div>
                        <div>
                          <p style="font-size:0.65rem;color:var(--text-dim);text-transform:uppercase;letter-spacing:1px;margin:0;">Cargo Safety Protocol</p>
                          <p style="font-family:var(--font-body);font-size:0.80rem;font-weight:700;color:#F0FDF6;margin:4px 0 0;">📦 {_gp.cargo_type}</p>
                        </div>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
                with _gpc2:
                    sec_agent_instance = SecurityPassAgent()
                    qr_bytes = sec_agent_instance.generate_qr_code_bytes(f"{_gp.pass_id}|{_gp.vehicle_id}|{_gp.assigned_bay}|{_gp.security_hash}")
                    if qr_bytes:
                        st.image(qr_bytes, caption=f"Scan at Gate barrier: {_gp.assigned_bay}", width=170)

        # ── (Charging action buttons removed from Driver View; controlled by Station Host) ──


        # ── 💳 FINTECH SETTLEMENT AGENT EXPANDER ──
        _inv = st.session_state.get("invoice_ledger")
        if _inv:
            with st.expander(
                f"💳 FinTech Settlement Agent — Digital Escrow & Tax Invoice  ·  🟢 SETTLED_IN_ESCROW  ·  {_inv.transaction_id}",
                expanded=True,
            ):
                st.markdown(f"""
                <div style="background:linear-gradient(135deg,rgba(245,158,11,0.10) 0%,rgba(245,158,11,0.03) 100%);
                            border:1.5px solid rgba(245,158,11,0.40);border-radius:14px;
                            padding:14px 20px;margin-bottom:18px;
                            box-shadow:0 0 24px rgba(245,158,11,0.10);">
                  <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;">
                    <span style="font-size:1.6rem;">💳</span>
                    <div>
                      <p style="font-family:var(--font-heading);font-size:0.95rem;font-weight:900;
                                color:#F59E0B;margin:0;letter-spacing:0.3px;">
                        FinTech Settlement Agent: Digital Escrow &amp; GST Tax Invoice
                      </p>
                      <p style="font-family:var(--font-body);font-size:0.72rem;color:var(--text-muted);
                                margin:3px 0 0;letter-spacing:0.8px;text-transform:uppercase;">
                        💳 Txn: <span style="color:#F59E0B;font-weight:700;">{_inv.transaction_id}</span>
                        &nbsp;·&nbsp; Target Station: <span style="color:#F0FDF6;font-weight:700;">{_inv.station_name}</span>
                        &nbsp;·&nbsp; Timestamp: <span style="color:var(--text-muted);">{_inv.timestamp}</span>
                      </p>
                    </div>
                    <div style="margin-left:auto;">
                      <span style="background:rgba(16,185,129,0.14);border:1px solid rgba(16,185,129,0.40);
                                   border-radius:20px;padding:6px 16px;font-family:var(--font-heading);
                                   font-size:0.78rem;font-weight:800;color:#10B981;letter-spacing:0.5px;">
                        🟢 ESCROW STATUS: SETTLED &amp; LOCKED
                      </span>
                    </div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

                _fcol1, _fcol2 = st.columns([1.2, 2.5])
                with _fcol1:
                    st.metric(
                        label="Fleet Escrow Wallet Balance",
                        value=f"₹{_inv.wallet_balance_remaining:,.2f}",
                        delta=f"-₹{_inv.total_charged:,.2f}",
                        delta_color="normal"
                    )
                with _fcol2:
                    st.markdown(f"""
                    <div style="background:rgba(14,26,18,0.85);border:1.5px solid rgba(245,158,11,0.25);
                                border-radius:14px;overflow:hidden;">
                      <table style="width:100%;border-collapse:collapse;">
                        <thead>
                          <tr style="background:rgba(245,158,11,0.08);border-bottom:1.5px solid rgba(245,158,11,0.25);">
                            <th style="padding:8px 12px;text-align:left;font-family:var(--font-body);font-size:0.62rem;font-weight:700;text-transform:uppercase;color:#F59E0B;">Item Description</th>
                            <th style="padding:8px 12px;text-align:right;font-family:var(--font-body);font-size:0.62rem;font-weight:700;text-transform:uppercase;color:#F59E0B;">Calculation</th>
                            <th style="padding:8px 12px;text-align:right;font-family:var(--font-body);font-size:0.62rem;font-weight:700;text-transform:uppercase;color:#F59E0B;">Amount (₹)</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr>
                            <td style="padding:8px 12px;border-bottom:1px solid rgba(245,158,11,0.08);font-size:0.75rem;color:#F0FDF6;">Base Energy Charge</td>
                            <td style="padding:8px 12px;border-bottom:1px solid rgba(245,158,11,0.08);text-align:right;font-size:0.72rem;color:var(--text-dim);">{_inv.energy_kwh:.1f} kWh × ₹{_inv.tariff_per_kwh:.2f}</td>
                            <td style="padding:8px 12px;border-bottom:1px solid rgba(245,158,11,0.08);text-align:right;font-size:0.78rem;font-weight:700;color:#F0FDF6;">₹{_inv.base_energy_cost:,.2f}</td>
                          </tr>
                          <tr>
                            <td style="padding:8px 12px;border-bottom:1px solid rgba(245,158,11,0.08);font-size:0.75rem;color:#F0FDF6;">Platform Clearing Fee (2%)</td>
                            <td style="padding:8px 12px;border-bottom:1px solid rgba(245,158,11,0.08);text-align:right;font-size:0.72rem;color:var(--text-dim);">2% of base energy</td>
                            <td style="padding:8px 12px;border-bottom:1px solid rgba(245,158,11,0.08);text-align:right;font-size:0.78rem;font-weight:700;color:#00BFFF;">₹{_inv.platform_fee:,.2f}</td>
                          </tr>
                          <tr>
                            <td style="padding:8px 12px;border-bottom:1px solid rgba(245,158,11,0.08);font-size:0.75rem;color:#F0FDF6;">GST Tax (18% Statutory Rate)</td>
                            <td style="padding:8px 12px;border-bottom:1px solid rgba(245,158,11,0.08);text-align:right;font-size:0.72rem;color:var(--text-dim);">18% GST</td>
                            <td style="padding:8px 12px;border-bottom:1px solid rgba(245,158,11,0.08);text-align:right;font-size:0.78rem;font-weight:700;color:#EF4444;">₹{_inv.tax_gst_18_percent:,.2f}</td>
                          </tr>
                          <tr style="background:rgba(245,158,11,0.06);">
                            <td style="padding:10px 12px;font-family:var(--font-heading);font-size:0.80rem;font-weight:800;color:#F59E0B;">Total Pre-Authorized Amount</td>
                            <td style="padding:10px 12px;text-align:right;font-size:0.72rem;color:var(--text-muted);">Sum total</td>
                            <td style="padding:10px 12px;text-align:right;font-family:var(--font-heading);font-size:0.95rem;font-weight:900;color:#F59E0B;">₹{_inv.total_charged:,.2f}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                    """, unsafe_allow_html=True)


        # ── 🔍 9-AGENT JSON PAYLOAD VERIFICATION DRAWER ──
        _pipeline_res = st.session_state.get("pipeline_results") or {}
        if _pipeline_res:
            with st.expander("🔍 End-to-End 9-Agent Pipeline JSON Payloads (Audit Log)", expanded=False):
                st.markdown('<p style="font-family:var(--font-heading);font-size:0.85rem;color:var(--accent-neon);margin:0 0 10px;">📋 Complete Inter-Agent Payload Audit Trace</p>', unsafe_allow_html=True)
                st.json(_pipeline_res)



    else:
        # Hide Red Alert Banner completely
        if active_req.get("status") == "COMPLETED" or batt >= 100.0:
            banner_title = "🟢 CHARGING CONFIRMED & COMPLETED (100%) — Thank you for using ChargeVerse"
            banner_sub = f"Vehicle EV-CV-001 battery fully restored to 100% · Target: {destination}"
        else:
            banner_title = "🟢 ROUTE FEASIBLE — Direct Transit Energy Sufficient"
            banner_sub = f"Current SoC: {batt:.1f}% · Required: {required_batt:.1f}% · Energy Surplus: +{batt - required_batt:.1f}% · Target: {destination}"

        st.markdown(f"""
        <div class="banner-cruise">
          <p class="banner-cruise-title">{banner_title}</p>
          <p class="banner-cruise-sub">{banner_sub}</p>
        </div>
        """, unsafe_allow_html=True)



# ══════════════════════════════════════════════════════════════════════
# VIEW B: STATION ADMIN VIEW
# ══════════════════════════════════════════════════════════════════════
elif st.session_state.role in ["station_a", "station_b", "station_c", "station_d", "station_e", "station_f", "station_g"]:


    target_sid   = st.session_state.role
    station_meta = STATIONS_DEFAULTS[target_sid]
    s_name       = station_meta["name"]
    s_short      = station_meta["short"]

    # ── Load shared state directly from disk so inputs show latest values ──
    shared_disk = _load_shared_station_state()
    p_disk = shared_disk.get(target_sid, {})

    if f"{target_sid}_status" not in st.session_state:
        st.session_state[f"{target_sid}_status"] = p_disk.get("status", station_meta["status"])
    if f"{target_sid}_price_per_kwh" not in st.session_state:
        st.session_state[f"{target_sid}_price_per_kwh"] = float(p_disk.get("price_per_kwh", station_meta["price_per_kwh"]))
    if f"{target_sid}_queue_length" not in st.session_state:
        st.session_state[f"{target_sid}_queue_length"] = int(p_disk.get("queue_length", station_meta["queue_length"]))
    if f"{target_sid}_kw" not in st.session_state:
        st.session_state[f"{target_sid}_kw"] = float(p_disk.get("kw", station_meta["kw"]))
    if f"{target_sid}_safety_buffer" not in st.session_state:
        st.session_state[f"{target_sid}_safety_buffer"] = float(p_disk.get("safety_buffer_percentage", station_meta.get("safety_buffer_percentage", 70.0)))

    # ── CONSOLE VIEW SWITCHER CONTROL ──
    default_facility_type = station_meta.get("facility_type", "PUBLIC_STATION")
    mode_options = ["🛡️ Private Logistics Yard View", "⚡ Public Charging Station View"]
    default_idx = 0 if default_facility_type == "PRIVATE_YARD" else 1

    selected_mode = st.radio(
        "Switch Station Console View Mode:",
        options=mode_options,
        index=default_idx,
        horizontal=True,
        key=f"console_mode_{target_sid}",
    )

    is_private_mode = ("Private" in selected_mode)
    active_facility_type = FacilityType.PRIVATE_YARD if is_private_mode else FacilityType.PUBLIC_STATION

    # Instantiate Pydantic Console State Model
    console_state = StationConsoleState(
        station_id=target_sid,
        facility_name=s_name,
        facility_type=active_facility_type,
        total_capacity_kw=st.session_state[f"{target_sid}_kw"],
        tariff_per_kwh=st.session_state[f"{target_sid}_price_per_kwh"],
        safety_buffer_percent=st.session_state.get(f"{target_sid}_safety_buffer", 70.0),
        queued_vehicles_150m=st.session_state[f"{target_sid}_queue_length"],
    )

    # ── HEADER & FACILITY BADGE ──
    header_badge = (
        '<span style="background:rgba(0,191,255,0.18);border:1px solid #00BFFF;color:#00BFFF;padding:4px 12px;border-radius:12px;font-size:0.75rem;font-weight:800;letter-spacing:1px;">🛡️ PRIVATE YARD - CONTRACT ACCESS ONLY</span>'
        if is_private_mode else
        '<span style="background:rgba(0,255,136,0.18);border:1px solid #00FF88;color:#00FF88;padding:4px 12px;border-radius:12px;font-size:0.75rem;font-weight:800;letter-spacing:1px;">⚡ PUBLIC HUB - OPEN ACCESS</span>'
    )

    st.markdown(f"""
    <div class="cv-header">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <h1>⚡ {s_name.upper()} CONTROL ROOM</h1>
        {header_badge}
      </div>
      <p>Dedicated Station Console · Yard_Host Agent Operations ({s_short})</p>
    </div>
    """, unsafe_allow_html=True)

    # ── HARDWARE & CAPACITY CONTROLS PANEL ──

    # ── VERIFIED GATE PASS ACCESS CLEARANCE CARD ──
    _db_check = _load_stations_db()
    _req_info = _db_check.get("active_requests", {}).get("EV-CV-001", {})
    if isinstance(_req_info, dict) and _req_info.get("accepted_by") == target_sid:
        _gp_id = _req_info.get("gate_pass_id", "#808-GATE-PASS-VERIFIED")
        _bay_id = _req_info.get("assigned_bay", "BAY-01")
        _sec_hash = _req_info.get("security_hash", "VERIFIED")
        _exp_time = _req_info.get("valid_until", "1 HR")
        
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,rgba(16,185,129,0.14) 0%,rgba(16,185,129,0.04) 100%);
                    border:2px solid #10B981;border-radius:14px;padding:18px;margin-top:16px;
                    box-shadow:0 0 26px rgba(16,185,129,0.15);">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
            <p style="font-family:var(--font-heading);font-size:0.95rem;font-weight:900;color:#10B981;margin:0;">
              🔐 SECURITY PASS AGENT: VERIFIED AUTOMATED BARRIER ACCESS
            </p>
            <span style="background:#10B981;color:#06100C;padding:4px 12px;border-radius:12px;font-weight:800;font-size:0.75rem;">
              BARRIER OPEN: {_bay_id}
            </span>
          </div>
          <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;text-align:center;background:rgba(6,16,12,0.60);padding:12px;border-radius:10px;">
            <div>
              <p style="font-size:0.60rem;color:var(--text-dim);text-transform:uppercase;margin:0;">Clearance Code</p>
              <p style="font-family:var(--font-heading);font-size:0.90rem;font-weight:800;color:#10B981;margin:3px 0 0;">{_gp_id}</p>
            </div>
            <div>
              <p style="font-size:0.60rem;color:var(--text-dim);text-transform:uppercase;margin:0;">Assigned Bay</p>
              <p style="font-family:var(--font-heading);font-size:0.90rem;font-weight:800;color:#00BFFF;margin:3px 0 0;">{_bay_id}</p>
            </div>
            <div>
              <p style="font-size:0.60rem;color:var(--text-dim);text-transform:uppercase;margin:0;">Security Hash</p>
              <p style="font-family:var(--font-mono);font-size:0.85rem;font-weight:700;color:#F59E0B;margin:3px 0 0;">{_sec_hash}</p>
            </div>
            <div>
              <p style="font-size:0.60rem;color:var(--text-dim);text-transform:uppercase;margin:0;">Valid Until</p>
              <p style="font-family:var(--font-heading);font-size:0.90rem;font-weight:800;color:#F0FDF6;margin:3px 0 0;">{_exp_time}</p>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="admin-card">', unsafe_allow_html=True)
    st.markdown('<p style="font-family:var(--font-heading);font-size:0.90rem;font-weight:800;color:var(--accent-primary);margin:0 0 14px;letter-spacing:1px;">🎛️ HARDWARE & CAPACITY CONTROLS</p>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4, gap="medium")

    # Differentiated Status Options: Private Yard (ONLINE, MAINTENANCE, OFFLINE) vs Public Hub (ONLINE, BUSY, OFFLINE)
    status_opts = ["ONLINE", "MAINTENANCE", "OFFLINE"] if is_private_mode else ["ONLINE", "BUSY", "OFFLINE"]

    with c1:
        st.markdown('<p class="sb-label">Operational Status</p>', unsafe_allow_html=True)
        st.selectbox(
            f"Status_{target_sid}",
            options=status_opts,
            key=f"{target_sid}_status",
            label_visibility="collapsed",
        )

    with c2:
        tariff_label = "Negotiated Fleet Rate ($/kWh)" if is_private_mode else "Public Tariff Rate ($/kWh)"
        st.markdown(f'<p class="sb-label">{tariff_label}</p>', unsafe_allow_html=True)
        st.number_input(
            f"Price_{target_sid}",
            min_value=0.05,
            max_value=0.99,
            step=0.01,
            format="%.2f",
            key=f"{target_sid}_price_per_kwh",
            label_visibility="collapsed",
        )

    with c3:
        st.markdown('<p class="sb-label">Active Queue Count</p>', unsafe_allow_html=True)
        st.slider(
            f"Queue_{target_sid}",
            min_value=0,
            max_value=station_meta["max_queue"],
            key=f"{target_sid}_queue_length",
            label_visibility="collapsed",
        )

    with c4:
        st.markdown('<p class="sb-label">Charger Capacity Rating (kW)</p>', unsafe_allow_html=True)
        st.number_input(
            f"KW_{target_sid}",
            min_value=50.0,
            max_value=350.0,
            step=10.0,
            key=f"{target_sid}_kw",
            label_visibility="collapsed",
        )

    # ── PRIVATE YARD INTERNAL OPERATIONAL SAFETY BUFFER CONTROL ──
    if is_private_mode:
        st.markdown('<hr style="border:none;border-top:1px solid rgba(0,214,143,0.12);margin:16px 0 12px;">', unsafe_allow_html=True)
        _cur_buf = float(st.session_state.get(f"{target_sid}_safety_buffer", 70.0))
        _cur_idle_pct = max(0.0, 100.0 - _cur_buf)
        st.markdown(f'<p class="sb-label">🛡️ Internal Fleet Operational Safety Buffer (%) &nbsp;·&nbsp; <b style="color:var(--accent-neon);">Public Idle Capacity Listed on Marketplace: {int(_cur_idle_pct)}%</b></p>', unsafe_allow_html=True)
        st.slider(
            f"Buffer_{target_sid}",
            min_value=0.0,
            max_value=90.0,
            step=5.0,
            key=f"{target_sid}_safety_buffer",
            label_visibility="collapsed",
        )

    st.markdown('</div>', unsafe_allow_html=True)

    # ── State Persistence ──
    _yh_status = st.session_state[f"{target_sid}_status"]
    _yh_queue  = int(st.session_state[f"{target_sid}_queue_length"])
    _yh_kw     = float(st.session_state[f"{target_sid}_kw"])
    _yh_price  = float(st.session_state[f"{target_sid}_price_per_kwh"])
    _yh_buf    = float(st.session_state.get(f"{target_sid}_safety_buffer", 70.0))

    # Update Pydantic model properties
    console_state.total_capacity_kw = _yh_kw
    console_state.tariff_per_kwh = _yh_price
    console_state.safety_buffer_percent = _yh_buf
    console_state.queued_vehicles_150m = _yh_queue

    _yh_reserved_kw  = round(_yh_kw * (_yh_buf / 100.0), 1)
    _yh_available_kw = console_state.available_p2p_kw
    p2p_is_active    = console_state.p2p_active

    # ── Auto-Save Admin Updates to stations_db.json ──
    _updated_fields = {
        "status":                   _yh_status,
        "price_per_kwh":            _yh_price,
        "queue_length":              _yh_queue,
        "kw":                       _yh_kw,
        "safety_buffer_percentage": _yh_buf,
        "facility_type":            active_facility_type.value,
    }
    _save_shared_station_state({target_sid: _updated_fields})
    
    # Update st.session_state['stations'] cache
    if "stations" not in st.session_state:
        st.session_state["stations"] = {}
    if target_sid not in st.session_state["stations"]:
        st.session_state["stations"][target_sid] = {}
    st.session_state["stations"][target_sid].update(_updated_fields)
    save_stations_db({"stations": st.session_state["stations"]})

    # ── CONDITIONAL METRICS & PANELS BY FACILITY TYPE ──
    if is_private_mode:
        # 1. LIVE CAPACITY VISUALIZER & P2P INACTIVE CONSTRAINT BADGE
        st.markdown('<div class="admin-card" style="margin-top:16px;">', unsafe_allow_html=True)
        st.markdown('<p style="font-family:var(--font-heading);font-size:0.90rem;font-weight:800;color:#00BFFF;margin:0 0 14px;letter-spacing:1px;">🔋 PRIVATE YARD CAPACITY ALLOCATION & P2P NETWORK LISTING</p>', unsafe_allow_html=True)

        p2p_status_badge = (
            f'<div style="margin-bottom:12px;padding:8px 16px;background:rgba(0,255,136,0.12);border:1px solid #00FF88;border-radius:10px;color:#00FF88;font-weight:700;font-size:0.80rem;">🟢 P2P MARKETPLACE NETWORK LISTING: ACTIVE ({_yh_available_kw} kW Listed)</div>'
            if p2p_is_active else
            f'<div style="margin-bottom:12px;padding:8px 16px;background:rgba(239,68,68,0.12);border:1px solid #EF4444;border-radius:10px;color:#EF4444;font-weight:700;font-size:0.80rem;">🔴 P2P MARKETPLACE NETWORK LISTING: INACTIVE (< 15 kW Minimum Threshold — Current Available: {_yh_available_kw} kW)</div>'
        )
        st.markdown(p2p_status_badge, unsafe_allow_html=True)

        _total_deliv_kwh = float(p_disk.get("total_energy_delivered_kwh", 0.0))

        bc1, bc2, bc3 = st.columns(3, gap="medium")
        with bc1:
            st.markdown(f"""
            <div style="background:rgba(239,68,68,0.08);border:1.5px solid rgba(239,68,68,0.30);border-radius:14px;padding:16px;text-align:center;">
              <p style="font-family:var(--font-tech);font-size:0.70rem;color:var(--text-muted);margin:0;text-transform:uppercase;">🔴 Reserved Fleet Capacity</p>
              <p style="font-family:var(--font-heading);font-size:1.5rem;font-weight:900;color:var(--crit-red);margin:4px 0 0;">{_yh_reserved_kw} kW <span style="font-size:0.85rem;color:var(--text-dim);">({_yh_buf:.0f}%)</span></p>
            </div>
            """, unsafe_allow_html=True)

        with bc2:
            st.markdown(f"""
            <div style="background:rgba(0,255,136,0.08);border:1.5px solid rgba(0,255,136,0.30);border-radius:14px;padding:16px;text-align:center;">
              <p style="font-family:var(--font-tech);font-size:0.70rem;color:var(--text-muted);margin:0;text-transform:uppercase;">🟢 Public / P2P Network Capacity</p>
              <p style="font-family:var(--font-heading);font-size:1.5rem;font-weight:900;color:var(--accent-neon);margin:4px 0 0;">{_yh_available_kw} kW <span style="font-size:0.85rem;color:var(--text-dim);">({100.0 - _yh_buf:.0f}%)</span></p>
            </div>
            """, unsafe_allow_html=True)

        with bc3:
            st.markdown(f"""
            <div style="background:rgba(0,191,255,0.08);border:1.5px solid rgba(0,191,255,0.30);border-radius:14px;padding:16px;text-align:center;">
              <p style="font-family:var(--font-tech);font-size:0.70rem;color:var(--text-muted);margin:0;text-transform:uppercase;">⚡ Cumulative Energy Delivered</p>
              <p style="font-family:var(--font-heading);font-size:1.5rem;font-weight:900;color:#00BFFF;margin:4px 0 0;">{_total_deliv_kwh:.1f} kWh</p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

        # 2. GATE PASS ACCESS REQUEST QUEUE (EXCLUSIVE TO PRIVATE YARD)
        st.markdown('<div class="admin-card" style="margin-top:16px;">', unsafe_allow_html=True)
        st.markdown('<p style="font-family:var(--font-heading);font-size:0.90rem;font-weight:800;color:#00BFFF;margin:0 0 14px;letter-spacing:1px;">🛡️ INBOUND TRUCK GATE PASS ACCESS REQUEST QUEUE</p>', unsafe_allow_html=True)

        db_state = _load_stations_db()
        active_reqs = db_state.get("active_requests", {})
        ev_req = active_reqs.get("EV-CV-001")

        _req_soc = float(ev_req.get("battery_soc", 100.0)) if isinstance(ev_req, dict) else float(st.session_state.get("battery_soc", 100.0))
        _req_deficit = float(ev_req.get("energy_deficit", 0.0)) if isinstance(ev_req, dict) else max(0.0, 100.0 - _req_soc)

        if _req_soc >= 98.0 or _req_deficit <= 0.0:
            st.success(f"✅ Truck {ev_req.get('vehicle_id', 'EV-CV-001') if ev_req else 'EV-CV-001'} is fully charged ({_req_soc:.1f}% SOC). No auction required.")
        elif ev_req and target_sid in ev_req.get("top3_stations", []):
            req_status = ev_req.get("status", "PENDING")
            st.dataframe([
                {
                    "Request ID": "REQ-808-01",
                    "Truck ID": ev_req.get("vehicle_id", "EV-CV-001"),
                    "Cargo Payload": ev_req.get("cargo_type", "Medicines"),
                    "Cargo Weight (W_cargo)": "0.95 (Cold-Chain SLA)",
                    "SLA Urgency (U_SLA)": f"{ev_req.get('sla_urgency', 0.85):.3f}",
                    "Status": req_status,
                }
            ], use_container_width=True, hide_index=True)

            # Check if this station has an active broadcast alert (only if NOT already accepted AND SOC < 95%)
            _st_disk = load_stations_db().get("stations", {}).get(target_sid, {})
            _is_already_accepted = (ev_req.get("accepted_by") == target_sid) or (req_status in ["ACCEPTED_WINNER", "GATE_PASS_ISSUED", "APPROVED_GATE_PASS", "CHARGING_IN_PROGRESS"])
            _is_broadcast_alert = (_req_soc < 95.0 and _req_deficit > 0) and (not _is_already_accepted) and ((_st_disk.get("status") == "AUCTION_ALERT_PENDING") or (req_status == "AUCTION_ALERT_PENDING" and target_sid in ev_req.get("top3_stations", [])))

            if _is_broadcast_alert:
                st.warning("⚠️ INCOMING CHARGING AUCTION BROADCAST ALERT FROM EV TRUCK EV-CV-001")
                col_acc, col_rej = st.columns(2)
                with col_acc:
                    if st.button("✅ Accept Request & Reserve Bay", key=f"accept_{target_sid}"):
                        # 1. Mark this station as accepted winner
                        _db_all = load_stations_db()
                        _stations_all = _db_all.get("stations", {})

                        # Reset remaining 2 stations back to Available / ONLINE
                        for _sid, _sdata in _stations_all.items():
                            if _sid != target_sid and _sdata.get("status") == "AUCTION_ALERT_PENDING":
                                _sdata["status"] = "ONLINE" if "YARD" in _sdata.get("facility_type", "") else "Available"
                                _sdata.pop("pending_request", None)

                        _stations_all[target_sid]["status"] = "ACCEPTED_WINNER"
                        _stations_all[target_sid].pop("pending_request", None)

                        # Generate Gate Pass & Invoice for this winning deal
                        sec_agent_inst = SecurityPassAgent()
                        _w_deal = _stations_all[target_sid]
                        _w_deal["station_id"] = target_sid
                        _w_deal["facility_name"] = _w_deal.get("name", s_name)
                        _gp = sec_agent_inst.issue_gate_pass(_w_deal, cargo_type=ev_req.get("cargo_type", "General Cargo"))

                        fintech_inst = FinTechSettlementAgent(initial_wallet_balance=st.session_state.get("wallet_balance", 15000.00))
                        _inv = fintech_inst.execute_settlement(
                            gate_pass_data=_gp.dict() if hasattr(_gp, 'dict') else {},
                            winning_deal=_w_deal,
                            current_wallet_balance=st.session_state.get("wallet_balance", 15000.00)
                        )

                        # Store in session state for instant global UI sync
                        st.session_state["active_winning_station"] = target_sid
                        st.session_state["gate_pass"] = _gp
                        st.session_state["invoice_ledger"] = _inv
                        st.session_state["winning_station"] = _w_deal

                        # Save updated database state permanently
                        save_stations_db({
                            "stations": _stations_all,
                            "active_requests": {
                                "EV-CV-001": {
                                    "status": "APPROVED_GATE_PASS",
                                    "accepted_by": target_sid,
                                    "battery_soc": round(float(ev_req.get("battery_soc", st.session_state.get("battery_soc", 45.0))), 2),
                                    "gate_pass_id": _gp.pass_id,
                                    "assigned_bay": _gp.assigned_bay,
                                    "security_hash": _gp.security_hash,
                                    "valid_until": _gp.valid_until,
                                    "cargo_type": ev_req.get("cargo_type", "General Cargo"),
                                    "timestamp": round(time.time(), 2)
                                }
                            },
                            "settlement_ledger": {
                                _inv.transaction_id: _inv.dict()
                            }
                        })
                        st.success("Request accepted! Driver dashboard updated with #808-GATE-PASS & Invoice.")
                        st.rerun()

                with col_rej:
                    if st.button("❌ Reject Request", key=f"reject_{target_sid}"):
                        _db_all = load_stations_db()
                        _stations_all = _db_all.get("stations", {})
                        if target_sid in _stations_all:
                            _stations_all[target_sid]["status"] = "ONLINE" if "YARD" in _stations_all[target_sid].get("facility_type", "") else "Available"
                            _stations_all[target_sid].pop("pending_request", None)
                        save_stations_db({"stations": _stations_all})
                        st.info("Broadcast alert rejected.")
                        st.rerun()

            elif req_status in ["ACCEPTED", "APPROVED_GATE_PASS"]:
                st.info("🟡 GATE PASS ISSUED — AWAITING VEHICLE ARRIVAL & PLUG-IN")
                col_act1, col_act2 = st.columns(2)
                with col_act1:
                    if st.button("⚡ Start Charging Session", key=f"btn_start_{target_sid}"):
                        save_stations_db({
                            "active_requests": {
                                "EV-CV-001": {
                                    "status": "CHARGING_IN_PROGRESS",
                                    "accepted_by": target_sid
                                }
                            }
                        })
                        st.rerun()
                with col_act2:
                    if st.button("🟢 Complete Charging & Release Bay", key=f"btn_complete_{target_sid}"):
                        st.session_state["battery_soc"] = 100.0
                        save_stations_db({
                            "active_requests": {
                                "EV-CV-001": {
                                    "status": "CHARGING_COMPLETED",
                                    "accepted_by": target_sid
                                }
                            }
                        })
                        st.balloons()
                        st.success("Charging session completed! Battery restored to 100%.")
                        st.rerun()
            elif req_status == "CHARGING_IN_PROGRESS":
                st.warning("⚡ CHARGING IN PROGRESS — Physical bay occupied and drawing power.")
                if st.button("🟢 Complete Charging & Release Bay", key=f"btn_complete_in_prog_{target_sid}"):
                    st.session_state["battery_soc"] = 100.0
                    _db_cur = load_stations_db()
                    _st_map = _db_cur.get("stations", {})
                    if target_sid in _st_map:
                        _st_map[target_sid]["status"] = "ONLINE" if "YARD" in _st_map[target_sid].get("facility_type", "") else "Available"
                        _st_map[target_sid].pop("pending_request", None)
                        # Deduct delivered energy (kWh) from station capacity tracking log
                        _delivered_kwh = float(ev_req.get("required_kwh", 45.0)) if isinstance(ev_req, dict) else 45.0
                        _st_map[target_sid]["total_energy_delivered_kwh"] = round(float(_st_map[target_sid].get("total_energy_delivered_kwh", 0.0)) + _delivered_kwh, 2)
                    save_stations_db({
                        "stations": _st_map,
                        "active_requests": {
                            "EV-CV-001": {
                                "status": "CHARGING_COMPLETED",
                                "battery_soc": 100.0,
                                "accepted_by": target_sid
                            }
                        }
                    })
                    st.balloons()
                    st.success(f"Charging session completed! Delivered {ev_req.get('required_kwh', 45.0):.1f} kWh. Driver battery restored to 100%.")
                    st.rerun()
            elif req_status == "CHARGING_COMPLETED":
                st.success("🟢 CHARGING COMPLETED — BATTERY RESTORED TO 100%")
            else:
                st.info("No active gate pass access requests currently pending.")
        else:
            st.info("No active gate pass access requests currently pending for this Private Yard.")

        st.markdown('<p style="font-family:var(--font-tech);font-size:0.75rem;color:var(--text-dim);margin:12px 0 0;">⏱️ Private Yard Queue Rule: <b>Queue Delay = 0 Mins</b> (Reserved Pre-Booked Time Slots)</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    else:
        # ⚡ PUBLIC CHARGING STATION DASHBOARD
        st.markdown('<div class="admin-card" style="margin-top:16px;">', unsafe_allow_html=True)
        st.markdown(f'<p style="font-family:var(--font-heading);font-size:0.90rem;font-weight:800;color:var(--accent-neon);margin:0 0 14px;letter-spacing:1px;">⚡ PUBLIC EV HUB DASHBOARD METRICS — {_yh_status.upper()}</p>', unsafe_allow_html=True)

        st.markdown('<div style="margin-bottom:14px;padding:8px 16px;background:rgba(0,255,136,0.12);border:1px solid #00FF88;border-radius:10px;color:#00FF88;font-weight:700;font-size:0.80rem;">🤝 AUTOMATED INSTANT DIGITAL HANDSHAKE ACTIVE (No Manual Gate Pass Required)</div>', unsafe_allow_html=True)

        q_info = get_station_queue_status(target_sid, geofence_radius_meters=150.0)
        est_delay = console_state.estimated_queue_delay_mins

        mc1, mc2, mc3, mc4 = st.columns(4, gap="medium")
        with mc1:
            st.markdown(f"""
            <div style="background:rgba(0,255,136,0.08);border:1px solid rgba(0,255,136,0.25);border-radius:14px;padding:16px;text-align:center;">
              <p style="font-family:var(--font-tech);font-size:0.68rem;color:var(--text-muted);margin:0;text-transform:uppercase;">Active Plug Occupancy</p>
              <p style="font-family:var(--font-heading);font-size:1.5rem;font-weight:900;color:var(--accent-neon);margin:4px 0 0;">{q_info['active_plugs']} / {station_meta['max_queue']} Plugs</p>
            </div>
            """, unsafe_allow_html=True)

        with mc2:
            st.markdown(f"""
            <div style="background:rgba(255,213,79,0.08);border:1px solid rgba(255,213,79,0.25);border-radius:14px;padding:16px;text-align:center;">
              <p style="font-family:var(--font-tech);font-size:0.68rem;color:var(--text-muted);margin:0;text-transform:uppercase;">Queued Vehicles (GPS)</p>
              <p style="font-family:var(--font-heading);font-size:1.5rem;font-weight:900;color:var(--warn-gold);margin:4px 0 0;">{q_info['queued_count']} EVs</p>
            </div>
            """, unsafe_allow_html=True)

        with mc3:
            delay_badge_color = "var(--warn-gold)" if est_delay < 40 else "var(--crit-red)"
            st.markdown(f"""
            <div style="background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.25);border-radius:14px;padding:16px;text-align:center;">
              <p style="font-family:var(--font-tech);font-size:0.68rem;color:var(--text-muted);margin:0;text-transform:uppercase;">Est. Queue Delay</p>
              <p style="font-family:var(--font-heading);font-size:1.5rem;font-weight:900;color:{delay_badge_color};margin:4px 0 0;">🟠 {est_delay:.0f} Mins Delay</p>
            </div>
            """, unsafe_allow_html=True)

        with mc4:
            st.markdown(f"""
            <div style="background:rgba(0,191,255,0.08);border:1px solid rgba(0,191,255,0.25);border-radius:14px;padding:16px;text-align:center;">
              <p style="font-family:var(--font-tech);font-size:0.68rem;color:var(--text-muted);margin:0;text-transform:uppercase;">Dynamic Public Tariff</p>
              <p style="font-family:var(--font-heading);font-size:1.5rem;font-weight:900;color:#00BFFF;margin:4px 0 0;">${_yh_price:.2f} / kWh</p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown('<p style="font-family:var(--font-tech);font-size:0.75rem;color:var(--text-dim);margin:16px 0 8px;">📋 Vehicles Currently Detected Inside 150m Geofence:</p>', unsafe_allow_html=True)
        if q_info['queued_vehicles']:
            st.dataframe(
                q_info['queued_vehicles'],
                column_config={
                    "vehicle_id": "Vehicle ID",
                    "distance_m": "Distance (meters)",
                    "speed_kmh": "Speed (km/h)",
                    "status": "Geofence Queue Status",
                },
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No queued vehicles currently detected inside 150m geofence radius.")

        st.markdown('</div>', unsafe_allow_html=True)




    # ── LIVE STATIONS ──
    live_stations = _get_live_stations()
    my_station    = live_stations[target_sid]

    # ── LIVE TOP-3 SELECTIVE ALERT & DEAL SYNC MONITOR (AUTO-REFRESHING) ──
    @st.fragment(run_every="2s")
    def render_station_alert_panel():
        st.markdown("""
        <p style="font-family:var(--font-heading);font-size:1.1rem;color:var(--accent-neon);
                  margin:20px 0 12px;letter-spacing:1px;text-transform:uppercase;">
          📡 REAL-TIME TOP-3 SELECTIVE ALERT & DEAL LOCK MONITOR
        </p>
        """, unsafe_allow_html=True)

        db_state = _load_stations_db()
        active_reqs = db_state.get("active_requests", {})
        ev_req = active_reqs.get("EV-CV-001")

        if not ev_req or ev_req.get("status") == "EXPIRED":
            st.markdown("""
            <div style="background:rgba(18,40,28,0.50);border:1px dashed rgba(0,255,136,0.25);border-radius:16px;padding:28px;text-align:center;">
              <p style="font-family:var(--font-tech);font-size:0.90rem;color:var(--accent-neon);font-weight:700;margin:0;letter-spacing:1px;">
                🟢 NETWORK MONITORING ACTIVE — AWAITING VEHICLE AUCTIONTRIGGER BROADCASTS...
              </p>
            </div>
            """, unsafe_allow_html=True)
            return

        status = ev_req.get("status", "PENDING")
        accepted_by = ev_req.get("accepted_by")
        top3_stations = ev_req.get("top3_stations", [])
        vid = ev_req.get("vehicle_id", "EV-CV-001")

        top3_names = [STATIONS_DEFAULTS[s_id]["name"] for s_id in top3_stations if s_id in STATIONS_DEFAULTS]
        top3_names_str = ", ".join(top3_names)

        accepted_name = STATIONS_DEFAULTS.get(accepted_by, {}).get("name", accepted_by) if accepted_by else ""
        is_in_top3 = target_sid in top3_stations

        f_type = station_meta.get("facility_type", "PUBLIC_STATION")

        if status == "PENDING":
            if is_in_top3:
                if f_type == "PUBLIC_STATION":
                    st.markdown(f"""
                    <div style="background:rgba(18,40,28,0.92);border:2px solid var(--accent-neon);border-radius:24px;padding:24px;box-shadow:0 0 35px rgba(0,255,136,0.20);margin-bottom:16px;">
                      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
                        <p style="font-family:var(--font-heading);font-size:1.1rem;font-weight:900;color:var(--accent-neon);margin:0;">
                          ⚡ PUBLIC HUB AUTO-HANDSHAKE: VEHICLE {vid}
                        </p>
                        <span class="cyber-badge badge-optimal">⚡ [PUBLIC HUB: OPEN ACCESS]</span>
                      </div>
                      <div style="background:rgba(0,0,0,0.30);border-radius:12px;padding:10px 16px;margin-bottom:16px;">
                        <p style="font-family:var(--font-tech);font-size:0.78rem;color:var(--text-primary);margin:0;">
                          ℹ️ Open Access Public EV Hub. Plug sessions initiate automatically via digital handshake (No manual gate pass required).
                        </p>
                      </div>
                      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;">
                        <div style="background:rgba(7,20,13,0.80);padding:12px;border-radius:12px;border:1px solid rgba(255,82,82,0.30);">
                          <p style="font-family:var(--font-tech);font-size:0.65rem;color:var(--text-muted);margin:0;text-transform:uppercase;">Energy Deficit</p>
                          <p style="font-family:var(--font-heading);font-size:1.3rem;font-weight:900;color:var(--crit-red);margin:4px 0 0;">−{ev_req.get('energy_deficit')}%</p>
                        </div>
                        <div style="background:rgba(7,20,13,0.80);padding:12px;border-radius:12px;border:1px solid rgba(255,213,79,0.30);">
                          <p style="font-family:var(--font-tech);font-size:0.65rem;color:var(--text-muted);margin:0;text-transform:uppercase;">SLA Urgency Score</p>
                          <p style="font-family:var(--font-heading);font-size:1.3rem;font-weight:900;color:var(--warn-gold);margin:4px 0 0;">{ev_req.get('sla_urgency')}</p>
                        </div>
                        <div style="background:rgba(7,20,13,0.80);padding:12px;border-radius:12px;border:1px solid rgba(0,255,136,0.30);">
                          <p style="font-family:var(--font-tech);font-size:0.65rem;color:var(--text-muted);margin:0;text-transform:uppercase;">Cargo Type</p>
                          <p style="font-family:var(--font-heading);font-size:1.3rem;font-weight:900;color:var(--accent-neon);margin:4px 0 0;">{ev_req.get('cargo_type')}</p>
                        </div>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="background:rgba(18,40,28,0.92);border:2px solid var(--warn-amber);border-radius:24px;padding:24px;box-shadow:0 0 35px rgba(245,158,11,0.20);margin-bottom:16px;">
                      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
                        <p style="font-family:var(--font-heading);font-size:1.1rem;font-weight:900;color:var(--warn-amber);margin:0;">
                          🛡️ PRIVATE YARD GATE PASS REQUEST: VEHICLE {vid}
                        </p>
                        <span class="cyber-badge badge-warning">🛡️ [PRIVATE YARD: GATE PASS REQ]</span>
                      </div>
                      <div style="background:rgba(0,0,0,0.30);border-radius:12px;padding:10px 16px;margin-bottom:16px;">
                        <p style="font-family:var(--font-tech);font-size:0.78rem;color:var(--text-primary);margin:0;">
                          🎯 Targeted Top-3 Stations by Deal_Optimizer: <b style="color:var(--accent-primary);">{top3_names_str}</b>
                        </p>
                      </div>
                      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:16px;">
                        <div style="background:rgba(7,20,13,0.80);padding:12px;border-radius:12px;border:1px solid rgba(255,82,82,0.30);">
                          <p style="font-family:var(--font-tech);font-size:0.65rem;color:var(--text-muted);margin:0;text-transform:uppercase;">Energy Deficit</p>
                          <p style="font-family:var(--font-heading);font-size:1.3rem;font-weight:900;color:var(--crit-red);margin:4px 0 0;">−{ev_req.get('energy_deficit')}%</p>
                        </div>
                        <div style="background:rgba(7,20,13,0.80);padding:12px;border-radius:12px;border:1px solid rgba(255,213,79,0.30);">
                          <p style="font-family:var(--font-tech);font-size:0.65rem;color:var(--text-muted);margin:0;text-transform:uppercase;">SLA Urgency Score</p>
                          <p style="font-family:var(--font-heading);font-size:1.3rem;font-weight:900;color:var(--warn-gold);margin:4px 0 0;">{ev_req.get('sla_urgency')}</p>
                        </div>
                        <div style="background:rgba(7,20,13,0.80);padding:12px;border-radius:12px;border:1px solid rgba(0,255,136,0.30);">
                          <p style="font-family:var(--font-tech);font-size:0.65rem;color:var(--text-muted);margin:0;text-transform:uppercase;">Cargo Type</p>
                          <p style="font-family:var(--font-heading);font-size:1.3rem;font-weight:900;color:var(--accent-neon);margin:4px 0 0;">{ev_req.get('cargo_type')}</p>
                        </div>
                      </div>
                      <p style="font-family:var(--font-tech);font-size:0.80rem;color:var(--text-muted);margin:0 0 16px;">
                        📍 Vehicle Position: GPS ({ev_req.get('gps_lat')}, {ev_req.get('gps_lon')})
                      </p>
                    </div>
                    """, unsafe_allow_html=True)

                    if st.button(f"🛡️ ISSUE DIGITAL GATE ACCESS PASS FOR {vid}", key=f"accept_btn_{target_sid}_{vid}"):
                        _db_all = load_stations_db()
                        _stations_all = _db_all.get("stations", {})

                        # Reset remaining stations
                        for _sid, _sdata in _stations_all.items():
                            if _sid != target_sid and _sdata.get("status") == "AUCTION_ALERT_PENDING":
                                _sdata["status"] = "ONLINE" if "YARD" in _sdata.get("facility_type", "") else "Available"
                                _sdata.pop("pending_request", None)

                        _stations_all[target_sid]["status"] = "ACCEPTED_WINNER"
                        _stations_all[target_sid].pop("pending_request", None)

                        sec_agent_inst = SecurityPassAgent()
                        _w_deal = _stations_all[target_sid]
                        _w_deal["station_id"] = target_sid
                        _w_deal["facility_name"] = _w_deal.get("name", s_name)
                        _gp = sec_agent_inst.issue_gate_pass(_w_deal, cargo_type=ev_req.get("cargo_type", "General Cargo"))

                        fintech_inst = FinTechSettlementAgent(initial_wallet_balance=st.session_state.get("wallet_balance", 15000.00))
                        _inv = fintech_inst.execute_settlement(
                            gate_pass_data=_gp.dict() if hasattr(_gp, 'dict') else {},
                            winning_deal=_w_deal,
                            current_wallet_balance=st.session_state.get("wallet_balance", 15000.00)
                        )

                        st.session_state["active_winning_station"] = target_sid
                        st.session_state["gate_pass"] = _gp
                        st.session_state["invoice_ledger"] = _inv
                        st.session_state["winning_station"] = _w_deal

                        save_stations_db({
                            "stations": _stations_all,
                            "active_requests": {
                                vid: {
                                    "status": "ACCEPTED_WINNER",
                                    "accepted_by": target_sid,
                                    "battery_soc": round(float(ev_req.get("battery_soc", st.session_state.get("battery_soc", 45.0))), 2),
                                    "gate_pass_id": _gp.pass_id,
                                    "assigned_bay": _gp.assigned_bay,
                                    "security_hash": _gp.security_hash,
                                    "valid_until": _gp.valid_until,
                                    "cargo_type": ev_req.get("cargo_type", "General Cargo"),
                                    "timestamp": round(time.time(), 2)
                                }
                            },
                            "settlement_ledger": {
                                _inv.transaction_id: _inv.dict()
                            }
                        })
                        st.toast(f"✅ Request accepted & Gate Pass issued for {vid} at {s_name}!")
                        st.rerun()

            else:
                st.markdown(f"""
                <div style="background:rgba(18,40,28,0.50);border:1px dashed rgba(0,255,136,0.25);border-radius:16px;padding:24px;text-align:center;">
                  <p style="font-family:var(--font-tech);font-size:0.88rem;color:var(--text-dim);margin:0;">
                    ℹ️ Vehicle {vid} has an active alert, but Deal_Optimizer targeted other Top-3 stations: <b style="color:var(--accent-primary);">{top3_names_str}</b>
                  </p>
                </div>
                """, unsafe_allow_html=True)

        elif status in ["ACCEPTED", "ACCEPTED_WINNER", "GATE_PASS_ISSUED", "APPROVED_GATE_PASS", "CHARGING", "CHARGING_IN_PROGRESS"]:
            if accepted_by == target_sid:
                st.markdown(f"""
                <div style="background:linear-gradient(135deg, rgba(0,214,143,0.15) 0%, rgba(14,28,20,0.95) 100%);border:2px solid var(--accent-primary);border-radius:24px;padding:26px;box-shadow:0 0 40px rgba(0,214,143,0.25);margin-bottom:16px;">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
                    <div>
                      <p style="font-family:var(--font-tech);font-size:0.75rem;font-weight:700;color:var(--accent-neon);text-transform:uppercase;letter-spacing:2px;margin:0;">
                        ⚡ ACTIVE IN-PROGRESS CHARGING SESSION
                      </p>
                      <p style="font-family:var(--font-heading);font-size:1.5rem;font-weight:900;color:var(--text-primary);margin:4px 0 0;">
                        Vehicle {vid} Charging at {s_name}
                      </p>
                    </div>
                    <span class="cyber-badge badge-optimal">IN PROGRESS</span>
                  </div>

                  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:16px 0;">
                    <div style="background:rgba(7,20,13,0.80);padding:12px;border-radius:12px;border:1px solid rgba(0,255,136,0.30);">
                      <p style="font-family:var(--font-tech);font-size:0.65rem;color:var(--text-muted);margin:0;text-transform:uppercase;">Deficit Remaining</p>
                      <p style="font-family:var(--font-heading);font-size:1.3rem;font-weight:900;color:var(--accent-neon);margin:4px 0 0;">−{ev_req.get('energy_deficit')}%</p>
                    </div>
                    <div style="background:rgba(7,20,13,0.80);padding:12px;border-radius:12px;border:1px solid rgba(255,213,79,0.30);">
                      <p style="font-family:var(--font-tech);font-size:0.65rem;color:var(--text-muted);margin:0;text-transform:uppercase;">SLA Urgency</p>
                      <p style="font-family:var(--font-heading);font-size:1.3rem;font-weight:900;color:var(--warn-gold);margin:4px 0 0;">{ev_req.get('sla_urgency')}</p>
                    </div>
                    <div style="background:rgba(7,20,13,0.80);padding:12px;border-radius:12px;border:1px solid rgba(0,255,136,0.30);">
                      <p style="font-family:var(--font-tech);font-size:0.65rem;color:var(--text-muted);margin:0;text-transform:uppercase;">Cargo Type</p>
                      <p style="font-family:var(--font-heading);font-size:1.3rem;font-weight:900;color:var(--accent-neon);margin:4px 0 0;">{ev_req.get('cargo_type')}</p>
                    </div>
                  </div>

                  <div style="display:flex;justify-content:space-between;align-items:center;border-top:1px solid rgba(0,255,136,0.20);padding-top:16px;">
                    <div class="passcode-pill">🔑 #808-GATE-PASS</div>
                    <p style="font-family:var(--font-tech);font-size:0.85rem;color:var(--accent-neon);margin:0;">
                      Active Charging & Gate Lock Confirmed
                    </p>
                  </div>
                </div>
                """, unsafe_allow_html=True)

                if st.button(f"⚡ COMPLETE BATTERY CHARGE (RESTORE 100%)", key=f"complete_charge_btn_{target_sid}_{vid}"):
                    current_db = _load_stations_db()
                    st_queue = current_db.get("stations", {}).get(target_sid, {}).get("queue_length", 0)
                    new_queue = max(0, st_queue - 1)

                    _save_stations_db({
                        "stations": {
                            target_sid: {
                                "queue_length": new_queue,
                            }
                        },
                        "active_requests": {
                            vid: {
                                "status": "COMPLETED",
                                "battery_soc": 100.0,
                                "energy_deficit": 0.0,
                                "completed_at": round(time.time(), 2),
                            }
                        }
                    })
                    st.toast(f"🎉 Battery charging completed for {vid}! Station slot released.")
                    st.rerun()
            else:
                st.toast(f"Alert for Vehicle {vid} has been accepted by {accepted_name}.")
                st.markdown(f"""
                <div style="background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.30);border-radius:16px;padding:22px;text-align:center;">
                  <p style="font-family:var(--font-heading);font-size:1.0rem;font-weight:700;color:var(--crit-red);margin:0 0 6px;">
                    ℹ️ Alert for Vehicle {vid} Has Been Accepted by Another Station
                  </p>
                  <p style="font-family:var(--font-body);font-size:0.84rem;color:var(--text-dim);margin:0;">
                    Station <b style="color:var(--accent-primary);">{accepted_name}</b> confirmed the deal first. Alert cleared from active panel.
                  </p>
                </div>
                """, unsafe_allow_html=True)

        elif status == "COMPLETED":
            if accepted_by == target_sid:
                st.markdown(f"""
                <div style="background:rgba(16,185,129,0.10);border:1.5px solid #10B981;border-radius:20px;padding:24px;text-align:center;">
                  <p style="font-family:var(--font-heading);font-size:1.1rem;font-weight:900;color:#10B981;margin:0 0 6px;">
                    ✅ CHARGING SESSION COMPLETED FOR VEHICLE {vid} (100% SoC)
                  </p>
                  <p style="font-family:var(--font-body);font-size:0.84rem;color:var(--text-dim);margin:0;">
                    Battery fully restored. Charger slot released on {s_name}.
                  </p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div style="background:rgba(18,40,28,0.50);border:1px dashed rgba(0,255,136,0.25);border-radius:16px;padding:28px;text-align:center;">
                  <p style="font-family:var(--font-tech);font-size:0.90rem;color:var(--accent-neon);font-weight:700;margin:0;letter-spacing:1px;">
                    🟢 NETWORK MONITORING ACTIVE — AWAITING VEHICLE AUCTIONTRIGGER BROADCASTS...
                  </p>
                </div>
                """, unsafe_allow_html=True)


    render_station_alert_panel()



