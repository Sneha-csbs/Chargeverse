"""
ChargeVerse — Route Optimizer Agent
=====================================
Software-only agent that computes the optimal navigation path from an EV
truck's current GPS position to an accepted charging station.

Responsibilities
----------------
* Haversine distance calculation (km) between truck & station.
* ETA estimation in minutes (at assumed 40 km/h average truck speed).
* Intermediate GPS waypoint generation along the route polyline.
* Step-by-step human-readable turn-by-turn navigation directions.
"""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────────────────────
# Pydantic Output Payload
# ──────────────────────────────────────────────────────────────────────────────

class RoutePayload(BaseModel):
    """Output payload returned by RouteOptimizerAgent."""

    vehicle_id: str = Field(default="EV-CV-001", description="Vehicle ID")
    station_id: str = Field(default="station_a",  description="Target station ID")
    station_name: str = Field(default="Charging Station", description="Station display name")

    distance_km: float  = Field(..., description="Straight-line Haversine distance in km")
    eta_minutes: float  = Field(..., description="Estimated travel time in minutes at 40 km/h")

    truck_lat:   float  = Field(..., description="Truck origin latitude")
    truck_lng:   float  = Field(..., description="Truck origin longitude")
    station_lat: float  = Field(..., description="Station destination latitude")
    station_lng: float  = Field(..., description="Station destination longitude")

    path: list[list[float]] = Field(
        default_factory=list,
        description="List of [lng, lat] coordinate pairs forming the route polyline"
    )
    navigation_steps: list[str] = Field(
        default_factory=list,
        description="Human-readable turn-by-turn navigation directions"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Route Optimizer Agent
# ──────────────────────────────────────────────────────────────────────────────

class RouteOptimizerAgent:
    """
    Software-only Route & Navigation Agent for ChargeVerse.

    Calculates the route from a truck's current GPS position to an accepted
    charging station.  Uses the Haversine formula for accurate great-circle
    distance and generates interpolated GPS waypoints for map rendering.

    Parameters
    ----------
    avg_speed_kmh : float
        Assumed average truck speed in km/h (default: 40 km/h).
    waypoint_count : int
        Number of intermediate GPS waypoints to generate along the route
        (default: 8).
    """

    _EARTH_RADIUS_KM: float = 6371.0

    def __init__(
        self,
        avg_speed_kmh: float = 40.0,
        waypoint_count: int = 8,
    ) -> None:
        self._speed   = max(5.0, avg_speed_kmh)
        self._n_wpts  = max(2, waypoint_count)

    # ── public API ─────────────────────────────────────────────────────────────

    def calculate_route(
        self,
        truck_lat: float,
        truck_lng: float,
        station_lat: float,
        station_lng: float,
        vehicle_id:   str = "EV-CV-001",
        station_id:   str = "station_a",
        station_name: str = "Charging Station",
    ) -> RoutePayload:
        """
        Compute the route from the truck to the charging station.

        Returns a :class:`RoutePayload` containing distance, ETA, path
        coordinates, and navigation steps.
        """
        distance_km  = self._haversine(truck_lat, truck_lng, station_lat, station_lng)
        eta_minutes  = self._estimate_eta(distance_km)
        path         = self._build_waypoints(truck_lat, truck_lng, station_lat, station_lng)
        nav_steps    = self._generate_nav_steps(
            truck_lat, truck_lng, station_lat, station_lng,
            distance_km, eta_minutes, station_name
        )

        return RoutePayload(
            vehicle_id   = vehicle_id,
            station_id   = station_id,
            station_name = station_name,
            distance_km  = round(distance_km, 2),
            eta_minutes  = round(eta_minutes, 1),
            truck_lat    = truck_lat,
            truck_lng    = truck_lng,
            station_lat  = station_lat,
            station_lng  = station_lng,
            path         = path,
            navigation_steps = nav_steps,
        )

    # ── private helpers ────────────────────────────────────────────────────────

    def _haversine(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float,
    ) -> float:
        """Return the Haversine great-circle distance in km."""
        φ1, φ2     = math.radians(lat1), math.radians(lat2)
        Δφ         = math.radians(lat2 - lat1)
        Δλ         = math.radians(lon2 - lon1)
        a = (math.sin(Δφ / 2) ** 2
             + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2)
        return self._EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _estimate_eta(self, distance_km: float) -> float:
        """Estimate ETA in minutes at the configured average speed."""
        return (distance_km / self._speed) * 60.0

    def _build_waypoints(
        self,
        lat1: float, lng1: float,
        lat2: float, lng2: float,
    ) -> list[list[float]]:
        """
        Generate interpolated GPS waypoints between truck and station.

        Returns a list of [lng, lat] pairs for PyDeck PathLayer rendering
        (PyDeck expects [longitude, latitude] ordering).
        """
        points: list[list[float]] = []
        steps = self._n_wpts + 1
        for i in range(steps + 1):
            t = i / steps
            # Add slight curvature to make the path feel realistic
            curve_factor = math.sin(math.pi * t) * 0.003
            lat = lat1 + t * (lat2 - lat1) + curve_factor
            lng = lng1 + t * (lng2 - lng1) + curve_factor * 0.5
            points.append([round(lng, 6), round(lat, 6)])
        return points

    def _bearing_label(self, lat1: float, lon1: float, lat2: float, lon2: float) -> str:
        """Return cardinal bearing direction (N / NE / E / SE / S / SW / W / NW)."""
        Δλ = math.radians(lon2 - lon1)
        φ1, φ2 = math.radians(lat1), math.radians(lat2)
        x  = math.sin(Δλ) * math.cos(φ2)
        y  = math.cos(φ1) * math.sin(φ2) - math.sin(φ1) * math.cos(φ2) * math.cos(Δλ)
        θ  = (math.degrees(math.atan2(x, y)) + 360) % 360
        dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        return dirs[round(θ / 45) % 8]

    def _generate_nav_steps(
        self,
        truck_lat: float, truck_lng: float,
        station_lat: float, station_lng: float,
        distance_km: float,
        eta_minutes: float,
        station_name: str,
    ) -> list[str]:
        """
        Build a realistic step-by-step navigation instruction list.
        """
        bearing = self._bearing_label(truck_lat, truck_lng, station_lat, station_lng)

        # Determine turn direction for intermediate steps
        lat_diff = station_lat - truck_lat
        lng_diff = station_lng - truck_lng
        turn_1   = "left" if lng_diff < 0 else "right"
        turn_2   = "right" if lat_diff < 0 else "left"

        seg1_km = round(distance_km * 0.35, 1)
        seg2_km = round(distance_km * 0.40, 1)
        seg3_km = round(distance_km * 0.25, 1)

        steps = [
            f"🚦 Start: Head {bearing} from your current location toward the charging corridor.",
            f"↕️  Continue straight for {seg1_km:.1f} km on the main freight route.",
            f"↪️  Turn {turn_1} at the intersection — follow EV charging route markers.",
            f"➡️  Continue for {seg2_km:.1f} km — maintain lane discipline on freight road.",
            f"↩️  Turn {turn_2} — EV Station signage will appear on {turn_2} side of road.",
            f"🏁 Continue final {seg3_km:.1f} km — charging station is now visible ahead.",
            f"🅿️  Enter facility gate — scan your Digital Gate Pass QR code at the barrier.",
            f"⚡ Proceed to assigned charging bay — plug-in connector to begin session.",
            f"✅ ARRIVED: {station_name} — ETA was {eta_minutes:.0f} min over {distance_km:.1f} km.",
        ]

        return steps
